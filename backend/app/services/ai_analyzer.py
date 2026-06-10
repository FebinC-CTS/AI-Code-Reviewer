import json
import logging
import asyncio
import os
from typing import List, Callable, Optional

import httpx

from app.models.schemas import ReviewIssue, SeverityLevel, FileInfo
from app.utils.helpers import extract_json_from_response, chunk_files

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an expert code reviewer. Analyze the provided source code files and return a JSON array of issues found.

For EACH issue found, return an object with EXACTLY these fields:
- "file": the file path (string)
- "issue": brief one-line description (string)
- "severity": exactly one of "Low", "Medium", or "High" (string)
- "explanation": detailed explanation of why this is a problem (string)
- "fix": concrete code snippet or step-by-step fix instructions (string)
- "recommendation": best practice recommendation (string)
- "insights": additional maintainability or performance insights (string)

Check for ALL of the following:
1. Bugs: logic errors, null dereferences, off-by-one errors, race conditions
2. Security: SQL injection, XSS, command injection, insecure deserialization, hardcoded secrets, improper auth
3. Performance: unnecessary loops, missing indexes, inefficient algorithms, memory leaks
4. Maintainability: code duplication, poor naming, missing error handling, lack of types
5. Best practices: language-specific idioms, framework conventions, SOLID principles

IMPORTANT:
- Return ONLY a valid JSON array. No markdown, no prose, no explanation outside the JSON.
- If no issues are found in a file, return an empty array [].
- Do not skip any file provided.
- Provide actionable, specific fixes with real code examples where possible.
"""

# ──────────────────────────────────────────────
#  Provider back-ends
# ──────────────────────────────────────────────

def _get_provider() -> str:
    """
    LLM_PROVIDER controls which back-end is used:
      anthropic        → Anthropic SDK  (default, corporate gateway or direct key)
      ollama           → Ollama local server  (http://localhost:11434)
      gemini           → Google Gemini REST API
      openai_compat    → Any OpenAI-compatible endpoint (Groq, OpenRouter, etc.)
    """
    return os.environ.get("LLM_PROVIDER", "anthropic").lower().strip()


# ── Anthropic (original path) ──────────────────

def _call_anthropic(user_message: str) -> str:
    import anthropic as _anthropic

    api_key = os.environ.get("ANTHROPIC_API_KEY", "not-required")
    base_url = os.environ.get("ANTHROPIC_BASE_URL", "").strip() or None
    extra_headers_raw = os.environ.get("GATEWAY_EXTRA_HEADERS", "").strip()
    model = os.environ.get("CLAUDE_MODEL", "claude-opus-4-7")

    extra_headers = {}
    if extra_headers_raw:
        try:
            extra_headers = json.loads(extra_headers_raw)
        except json.JSONDecodeError:
            logger.warning("GATEWAY_EXTRA_HEADERS is not valid JSON — ignoring.")

    kwargs: dict = {"api_key": api_key}
    if base_url:
        kwargs["base_url"] = base_url
        if os.environ.get("GATEWAY_VERIFY_SSL", "true").lower() == "false":
            kwargs["http_client"] = httpx.Client(verify=False)
            logger.warning("TLS verification disabled.")
    if extra_headers:
        kwargs["default_headers"] = extra_headers

    client = _anthropic.Anthropic(**kwargs)
    msg = client.messages.create(
        model=model,
        max_tokens=8192,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )
    return msg.content[0].text


# ── OpenAI-compatible (Ollama, Groq, OpenRouter, etc.) ───

def _call_openai_compat(user_message: str) -> str:
    from openai import OpenAI

    base_url = os.environ.get("OPENAI_BASE_URL", "http://localhost:11434/v1").strip()
    api_key = os.environ.get("OPENAI_API_KEY", "ollama")  # Ollama ignores the key value
    model = os.environ.get("OPENAI_MODEL", "qwen2.5-coder:7b")

    client = OpenAI(base_url=base_url, api_key=api_key)
    response = client.chat.completions.create(
        model=model,
        max_tokens=8192,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
    )
    return response.choices[0].message.content


# ── Ollama (convenience alias — same as openai_compat with preset defaults) ──

def _call_ollama(user_message: str) -> str:
    # Ollama exposes an OpenAI-compatible endpoint at /v1
    os.environ.setdefault("OPENAI_BASE_URL", "http://localhost:11434/v1")
    os.environ.setdefault("OPENAI_API_KEY", "ollama")
    os.environ.setdefault("OPENAI_MODEL", "qwen2.5-coder:7b")
    return _call_openai_compat(user_message)


# ── Google Gemini ──────────────────────────────

def _call_gemini(user_message: str) -> str:
    import google.generativeai as genai

    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set.")

    model_name = os.environ.get("GEMINI_MODEL", "gemini-1.5-flash")
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(
        model_name=model_name,
        system_instruction=SYSTEM_PROMPT,
    )
    response = model.generate_content(user_message)
    return response.text


# ── Dispatcher ────────────────────────────────

_PROVIDERS = {
    "anthropic": _call_anthropic,
    "ollama": _call_ollama,
    "openai_compat": _call_openai_compat,
    "gemini": _call_gemini,
}


def _dispatch(user_message: str) -> str:
    provider = _get_provider()
    fn = _PROVIDERS.get(provider)
    if fn is None:
        raise ValueError(
            f"Unknown LLM_PROVIDER='{provider}'. "
            f"Valid options: {', '.join(_PROVIDERS)}"
        )
    logger.debug("Dispatching to provider: %s", provider)
    return fn(user_message)


# ──────────────────────────────────────────────
#  AIAnalyzer class
# ──────────────────────────────────────────────

class AIAnalyzer:
    def __init__(self):
        self.max_retries = 3
        self.base_delay = 2.0

    async def analyze_batch(
        self,
        files: List[FileInfo],
        progress_callback: Optional[Callable] = None,
    ) -> List[ReviewIssue]:
        file_payload = self._build_file_payload(files)
        user_message = (
            f"Please review the following {len(files)} file(s) "
            f"and return a JSON array of all issues found:\n\n"
            f"{file_payload}\n\n"
            "Return ONLY a valid JSON array. Example format:\n"
            '[\n  {\n    "file": "src/app.js",\n    "issue": "Missing input validation",\n'
            '    "severity": "High",\n    "explanation": "User input used directly.",\n'
            '    "fix": "const s = validator.escape(input);",\n'
            '    "recommendation": "Validate all inputs.",\n'
            '    "insights": "Consider Joi or Zod."\n  }\n]'
        )

        response_text = await self._call_with_retry(user_message)
        issues = self._parse_response(response_text, files)

        if progress_callback:
            await progress_callback(len(files))

        return issues

    def _build_file_payload(self, files: List[FileInfo]) -> str:
        parts = []
        for f in files:
            note = " [TRUNCATED]" if f.truncated else ""
            parts.append(f"### FILE: {f.path}{note}\n```\n{f.content}\n```")
        return "\n\n".join(parts)

    async def _call_with_retry(self, user_message: str) -> str:
        last_error: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                return await asyncio.to_thread(_dispatch, user_message)
            except Exception as e:
                # Rate-limit / transient errors worth retrying
                err_str = str(e).lower()
                is_retryable = any(k in err_str for k in (
                    "rate limit", "429", "503", "502", "connection", "timeout", "overloaded"
                ))
                if is_retryable and attempt < self.max_retries - 1:
                    wait = self.base_delay * (2 ** attempt)
                    logger.warning(
                        "Retryable error (attempt %d/%d), waiting %.1fs: %s",
                        attempt + 1, self.max_retries, wait, e,
                    )
                    await asyncio.sleep(wait)
                    last_error = e
                else:
                    logger.error("LLM call failed: %s", e)
                    raise
        raise last_error or RuntimeError("LLM call failed after retries")

    def _parse_response(self, response_text: str, files: List[FileInfo]) -> List[ReviewIssue]:
        issues = []
        try:
            json_str = extract_json_from_response(response_text)
            raw_list = json.loads(json_str)
            if not isinstance(raw_list, list):
                logger.error("LLM response is not a JSON array")
                return []
            for item in raw_list:
                try:
                    severity_raw = item.get("severity", "Medium")
                    try:
                        severity = SeverityLevel(severity_raw)
                    except ValueError:
                        severity = SeverityLevel.MEDIUM
                    issues.append(ReviewIssue(
                        file=item.get("file", "unknown"),
                        issue=item.get("issue", ""),
                        severity=severity,
                        explanation=item.get("explanation", ""),
                        fix=item.get("fix", ""),
                        recommendation=item.get("recommendation", ""),
                        insights=item.get("insights", ""),
                        source="ai",
                    ))
                except Exception as e:
                    logger.warning("Skipping malformed item: %s — %s", item, e)
        except json.JSONDecodeError as e:
            logger.error("Failed to parse JSON response: %s\nRaw: %.500s", e, response_text)
        return issues

    async def analyze_all_files(
        self,
        file_infos: List[FileInfo],
        batch_size: int = 10,
        progress_callback: Optional[Callable] = None,
    ) -> List[ReviewIssue]:
        all_issues: List[ReviewIssue] = []
        batches = chunk_files(file_infos, batch_size)
        for batch_idx, batch in enumerate(batches):
            logger.info("Batch %d/%d (%d files)", batch_idx + 1, len(batches), len(batch))
            try:
                all_issues.extend(await self.analyze_batch(batch, progress_callback))
            except Exception as e:
                logger.error("Batch %d failed: %s", batch_idx + 1, e)
                for f in batch:
                    all_issues.append(ReviewIssue(
                        file=f.path,
                        issue="Analysis failed",
                        severity=SeverityLevel.LOW,
                        explanation=f"AI analysis failed: {e}",
                        fix="Retry the analysis",
                        recommendation="Check your LLM_PROVIDER config",
                        insights="",
                        source="error",
                    ))
        return all_issues
