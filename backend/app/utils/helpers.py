import os
import re
import logging
import hashlib
from pathlib import Path
from typing import List

logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {
    ".js", ".ts", ".jsx", ".tsx",
    ".css", ".scss", ".sass",
    ".html",
    ".json",
    ".py", ".java"
}

EXCLUDED_DIRS = {
    "node_modules", ".git", "dist", "build", ".next",
    "__pycache__", ".venv", "venv", "env", ".env",
    "coverage", ".nyc_output", "target", "out"
}

MAX_FILE_SIZE_BYTES = 100 * 1024 * 1024  # 100 MB
MAX_TOKEN_CHARS = 150_000               # ~50k tokens at ~3 chars/token


def is_allowed_extension(filename: str) -> bool:
    ext = Path(filename).suffix.lower()
    return ext in ALLOWED_EXTENSIONS


def sanitize_path(base_dir: str, file_path: str) -> str | None:
    """Prevent path traversal attacks by ensuring file_path stays within base_dir."""
    try:
        base = Path(base_dir).resolve()
        target = Path(base_dir, file_path).resolve()
        if not str(target).startswith(str(base)):
            logger.warning("Path traversal attempt detected: %s", file_path)
            return None
        return str(target)
    except Exception as e:
        logger.error("Path sanitization error: %s", e)
        return None


def should_exclude_dir(dir_name: str) -> bool:
    return dir_name in EXCLUDED_DIRS


def collect_files(root_dir: str) -> List[str]:
    """Recursively collect all allowed files, skipping excluded directories."""
    collected = []
    root_path = Path(root_dir)

    for dirpath, dirnames, filenames in os.walk(root_path):
        # Prune excluded directories in-place so os.walk skips them
        dirnames[:] = [d for d in dirnames if not should_exclude_dir(d)]

        for filename in filenames:
            if is_allowed_extension(filename):
                full_path = os.path.join(dirpath, filename)
                rel_path = os.path.relpath(full_path, root_dir)
                # Normalize to forward slashes
                rel_path = rel_path.replace("\\", "/")
                collected.append(rel_path)

    return sorted(collected)


def read_file_safe(file_path: str, max_chars: int = MAX_TOKEN_CHARS) -> tuple[str, bool]:
    """Read a file and truncate if it exceeds max_chars. Returns (content, was_truncated)."""
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        if len(content) > max_chars:
            truncated_content = content[:max_chars]
            truncated_content += f"\n\n... [FILE TRUNCATED: exceeded {max_chars} characters] ..."
            return truncated_content, True
        return content, False
    except Exception as e:
        logger.error("Error reading file %s: %s", file_path, e)
        return f"[Error reading file: {e}]", False


def compute_session_id(content: bytes) -> str:
    """Generate a unique session ID based on upload content hash + timestamp."""
    import time
    hash_input = content + str(time.time()).encode()
    return hashlib.sha256(hash_input).hexdigest()[:16]


def compute_files_hash(file_data: list[tuple]) -> str:
    """Stable hash of file contents — same files always produce the same hash."""
    h = hashlib.sha256()
    for filename, content in sorted(file_data, key=lambda x: x[0]):
        h.update(filename.encode())
        h.update(content if isinstance(content, bytes) else content.encode())
    return h.hexdigest()[:24]


def chunk_files(files: List[dict], batch_size: int = 10) -> List[List[dict]]:
    """Split file list into batches for processing."""
    return [files[i:i + batch_size] for i in range(0, len(files), batch_size)]


def extract_json_from_response(text: str) -> str:
    """Extract JSON array from Claude's response, handling markdown code blocks."""
    # Try to find JSON array in markdown code block
    pattern = r"```(?:json)?\s*(\[[\s\S]*?\])\s*```"
    match = re.search(pattern, text, re.DOTALL)
    if match:
        return match.group(1)

    # Try to find raw JSON array
    pattern2 = r"(\[[\s\S]*\])"
    match2 = re.search(pattern2, text, re.DOTALL)
    if match2:
        return match2.group(1)

    return text
