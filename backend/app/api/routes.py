import os
import logging
import asyncio
import json
from typing import Dict, List, Any

from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.responses import Response, StreamingResponse
import aiofiles
import tempfile

from app.models.schemas import ReviewIssue, AnalysisResponse, SeverityLevel
from app.services.file_processor import FileProcessor
from app.services.ai_analyzer import AIAnalyzer
from app.services.static_analyzer import StaticAnalyzer
from app.services.export_service import ExportService
from app.utils.helpers import compute_session_id, compute_files_hash, is_allowed_extension

logger = logging.getLogger(__name__)

router = APIRouter()

_sessions: Dict[str, Dict[str, Any]] = {}

# ── Disk cache ────────────────────────────────────────────────────────────────
_CACHE_DIR = os.path.join(os.path.dirname(__file__), "..", "..", ".cache")
os.makedirs(_CACHE_DIR, exist_ok=True)

def _cache_path(files_hash: str) -> str:
    return os.path.join(_CACHE_DIR, f"{files_hash}.json")

def _load_cache(files_hash: str) -> list | None:
    path = _cache_path(files_hash)
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning("Cache read failed for %s: %s", files_hash, e)
    return None

def _save_cache(files_hash: str, issues: list) -> None:
    try:
        with open(_cache_path(files_hash), "w", encoding="utf-8") as f:
            json.dump(issues, f)
        logger.info("Results cached: %s", files_hash)
    except Exception as e:
        logger.warning("Cache write failed: %s", e)

ALLOWED_MIME_TYPES = {
    "application/zip",
    "application/x-zip-compressed",
    "application/octet-stream",
    "text/plain",
    "text/javascript",
    "text/typescript",
    "text/css",
    "text/html",
    "application/json",
    "text/x-python",
}

MAX_UPLOAD_SIZE = 100 * 1024 * 1024  # 100 MB


def _check_gateway_config():
    """Validate that the selected LLM provider has the required config."""
    provider = os.environ.get("LLM_PROVIDER", "anthropic").lower()

    if provider == "gemini":
        if not os.environ.get("GEMINI_API_KEY", "").strip():
            raise HTTPException(status_code=500, detail="GEMINI_API_KEY is not set in .env")

    elif provider in ("ollama", "openai_compat"):
        # Ollama works with no key; openai_compat needs a base URL
        if provider == "openai_compat" and not os.environ.get("OPENAI_BASE_URL", "").strip():
            raise HTTPException(status_code=500, detail="OPENAI_BASE_URL is not set for openai_compat provider")

    else:  # anthropic (default)
        base_url = os.environ.get("ANTHROPIC_BASE_URL", "").strip()
        api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
        if not base_url and not api_key:
            raise HTTPException(
                status_code=500,
                detail=(
                    "No AI connection configured. Set ANTHROPIC_BASE_URL (corporate gateway) "
                    "or ANTHROPIC_API_KEY (direct Anthropic) in the .env file. "
                    "To use a free local model instead, set LLM_PROVIDER=ollama"
                ),
            )


@router.post("/upload", response_model=dict)
async def upload_files(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
):
    """Upload one or more files (or a single ZIP) for analysis."""
    if not files:
        raise HTTPException(status_code=400, detail="No files provided.")
    if len(files) > 50:
        raise HTTPException(status_code=400, detail="Too many files. Maximum 50 files per upload.")

    # Read all file contents into memory first to validate sizes
    file_data = []
    total_size = 0
    for upload in files:
        content = await upload.read()
        total_size += len(content)
        if total_size > MAX_UPLOAD_SIZE:
            raise HTTPException(status_code=413, detail="Total upload size exceeds 100MB limit.")
        file_data.append((upload.filename or "unknown", content))

    # Generate session ID from combined content
    combined = b"".join(c for _, c in file_data)
    session_id = compute_session_id(combined)

    if session_id in _sessions:
        return {"session_id": session_id, "status": "already_exists", "message": "Session already exists."}

    # ── Cache check: same file contents → return instantly ──────────────────
    files_hash = compute_files_hash(file_data)
    cached_issues = _load_cache(files_hash)
    if cached_issues is not None:
        logger.info("Cache hit for hash %s — skipping AI analysis.", files_hash)
        _sessions[session_id] = {
            "status": "complete",
            "progress": {"total": len(file_data), "processed": len(file_data), "current": ""},
            "issues": cached_issues,
            "errors": [],
            "file_count": len(file_data),
            "cached": True,
        }
        return {"session_id": session_id, "status": "cached", "message": "Loaded from cache."}

    _sessions[session_id] = {
        "status": "uploading",
        "progress": {"total": 0, "processed": 0, "current": ""},
        "issues": [],
        "errors": [],
        "file_count": 0,
        "cached": False,
        "_files_hash": files_hash,
    }

    _check_gateway_config()

    background_tasks.add_task(_run_analysis, session_id, file_data)

    return {"session_id": session_id, "status": "processing", "message": "Analysis started."}


@router.get("/status/{session_id}")
async def get_status(session_id: str):
    """Get the current status of an analysis session."""
    session = _sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")

    return {
        "session_id": session_id,
        "status": session["status"],
        "progress": session["progress"],
        "issue_count": len(session["issues"]),
        "file_count": session["file_count"],
        "errors": session["errors"][:10],
        "cached": session.get("cached", False),
    }


@router.get("/results/{session_id}")
async def get_results(session_id: str):
    """Get the full analysis results for a session."""
    session = _sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")
    if session["status"] not in ("complete", "error"):
        raise HTTPException(status_code=202, detail="Analysis still in progress.")

    return {
        "session_id": session_id,
        "status": session["status"],
        "issues": session["issues"],
        "file_count": session["file_count"],
        "errors": session["errors"],
    }


@router.get("/export/{session_id}/{format}")
async def export_results(session_id: str, format: str):
    """Export analysis results as Excel or Markdown."""
    if format not in ("excel", "markdown"):
        raise HTTPException(status_code=400, detail="Format must be 'excel' or 'markdown'.")

    session = _sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")
    if session["status"] not in ("complete", "error"):
        raise HTTPException(status_code=202, detail="Analysis still in progress.")

    issues = [ReviewIssue(**i) for i in session["issues"]]
    exporter = ExportService()

    if format == "excel":
        try:
            data = exporter.export_excel(issues)
            return Response(
                content=data,
                media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                headers={"Content-Disposition": f"attachment; filename=code-review-{session_id[:8]}.xlsx"},
            )
        except Exception as e:
            logger.error("Excel export failed: %s", e)
            raise HTTPException(status_code=500, detail=f"Excel export failed: {e}")

    else:  # markdown
        try:
            md = exporter.export_markdown(issues)
            return Response(
                content=md.encode("utf-8"),
                media_type="text/markdown",
                headers={"Content-Disposition": f"attachment; filename=code-review-{session_id[:8]}.md"},
            )
        except Exception as e:
            logger.error("Markdown export failed: %s", e)
            raise HTTPException(status_code=500, detail=f"Markdown export failed: {e}")


@router.delete("/session/{session_id}")
async def delete_session(session_id: str):
    """Delete a session and its data."""
    if session_id in _sessions:
        del _sessions[session_id]
        return {"message": "Session deleted."}
    raise HTTPException(status_code=404, detail="Session not found.")


async def _run_analysis(session_id: str, file_data: List[tuple]):
    """Background task: process files and run AI + static analysis."""
    session = _sessions[session_id]
    processor = FileProcessor()
    temp_dir = processor.create_temp_dir()

    try:
        session["status"] = "extracting"

        # Save uploaded files to temp dir and collect relative paths
        all_relative_paths = []

        for filename, content in file_data:
            dest = os.path.join(temp_dir, filename)
            with open(dest, "wb") as f:
                f.write(content)

            # Handle ZIP files
            if filename.lower().endswith(".zip"):
                try:
                    rel_paths = processor.extract_zip(dest, temp_dir)
                    all_relative_paths.extend(rel_paths)
                    os.remove(dest)
                except ValueError as e:
                    session["errors"].append(f"ZIP error ({filename}): {e}")
            elif is_allowed_extension(filename):
                all_relative_paths.append(filename)
            else:
                session["errors"].append(f"Skipped unsupported file: {filename}")

        if not all_relative_paths:
            session["status"] = "complete"
            session["errors"].append("No supported files found to analyze.")
            return

        # Deduplicate
        all_relative_paths = list(dict.fromkeys(all_relative_paths))
        session["file_count"] = len(all_relative_paths)
        session["progress"]["total"] = len(all_relative_paths)
        session["status"] = "analyzing"

        logger.info("Session %s: analyzing %d files", session_id, len(all_relative_paths))

        # Load file contents
        file_infos = processor.load_file_contents(temp_dir, all_relative_paths)

        # Static analysis
        session["status"] = "static_analysis"
        static_analyzer = StaticAnalyzer()
        static_issues = await asyncio.to_thread(
            static_analyzer.run_all, all_relative_paths, temp_dir
        )

        processed_count = 0

        async def progress_cb(n: int):
            nonlocal processed_count
            processed_count += n
            session["progress"]["processed"] = processed_count
            session["progress"]["current"] = f"Batch complete ({processed_count}/{len(all_relative_paths)})"

        # AI analysis
        session["status"] = "ai_analysis"
        ai_analyzer = AIAnalyzer()
        ai_issues = await ai_analyzer.analyze_all_files(
            file_infos,
            batch_size=10,
            progress_callback=progress_cb,
        )

        all_issues = static_issues + ai_issues

        serialized = [i.model_dump() for i in all_issues]
        session["issues"] = serialized
        session["progress"]["processed"] = len(all_relative_paths)
        session["status"] = "complete"
        logger.info("Session %s complete: %d issues found.", session_id, len(all_issues))

        # Save to disk cache so identical uploads return instantly next time
        files_hash = session.get("_files_hash")
        if files_hash:
            _save_cache(files_hash, serialized)

    except Exception as e:
        logger.exception("Analysis failed for session %s: %s", session_id, e)
        session["status"] = "error"
        session["errors"].append(str(e))
    finally:
        processor.cleanup_temp_dir(temp_dir)
