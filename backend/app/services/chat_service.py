"""
Conversational assistant over a reviewed codebase.

Given the uploaded source files and the issues the reviewer found, this answers
free-form developer questions ("what does this do?", "how do I fix the SQL
injection?", "which file is riskiest?"). It reuses the same multi-provider
configuration as the analyzer (Anthropic / Ollama / OpenAI-compatible / Gemini).
"""

import os
import json
import asyncio
import logging
from typing import List, Dict

import httpx

logger = logging.getLogger(__name__)

CHAT_SYSTEM_PROMPT = """You are CodeInspect Assistant, an expert software engineer helping a developer understand a codebase that was just analyzed by an automated code review.

You are given, in the context below:
1. The list of files in the codebase.
2. The issues the automated review found (severity, file, description).
3. The full source code of those files.

Answer the developer's questions about THIS specific codebase — what the code does, how it works, why an issue matters, how to fix it, and security / performance / architecture questions.

Rules:
- Base every answer ONLY on the provided code and issues. If something is not in the context, say you can't see it rather than guessing.
- Be concise and practical. Use Markdown: short paragraphs, bullet lists, and fenced ``` code blocks for code.
- Reference concrete file paths, and line numbers when you can infer them.
- When asked to fix something, give a minimal, correct code snippet.
"""

# Character budget for the source code we inline into the prompt.
MAX_CONTEXT_CHARS = 60_000


def build_context(files: List[Dict], issues: List[Dict]) -> str:
    """Assemble a single text block: file tree + issues summary + source code."""
    paths = [f.get("path", "") for f in files]
    tree = "\n".join(f"- {p}" for p in paths) or "(no files available)"

    if issues:
        issue_lines = [
            f"- [{i.get('severity', '?')}] {i.get('file', '?')}: {i.get('issue', '')}"
            for i in issues
        ]
        issues_block = "\n".join(issue_lines)
    else:
        issues_block = "No issues were found by the automated review."

    budget = MAX_CONTEXT_CHARS
    parts: List[str] = []
    for f in files:
        content = f.get("content") or ""
        header = f"### FILE: {f.get('path', 'unknown')}\n"
        if budget <= 0:
            parts.append(f"{header}```\n... [omitted — context budget reached] ...\n```")
            continue
        snippet = content
        if len(snippet) > budget:
            snippet = snippet[:budget] + "\n... [truncated for context] ..."
        block = f"{header}```\n{snippet}\n```"
        parts.append(block)
        budget -= len(block)

    code_block = "\n\n".join(parts) if parts else "(no source available)"

    return (
        f"## Files in this codebase ({len(files)})\n{tree}\n\n"
        f"## Issues found by the review ({len(issues)})\n{issues_block}\n\n"
        f"## Source code\n{code_block}"
    )


# ── Provider back-ends (mirror ai_analyzer's configuration) ────────────────────

def _provider() -> str:
    return os.environ.get("LLM_PROVIDER", "anthropic").lower().strip()


def _chat_anthropic(system: str, messages: List[Dict]) -> str:
    import anthropic as _anthropic

    api_key = os.environ.get("ANTHROPIC_API_KEY", "not-required")
    base_url = os.environ.get("ANTHROPIC_BASE_URL", "").strip() or None
    model = os.environ.get("CLAUDE_MODEL", "claude-opus-4-7")

    extra_headers: dict = {}
    raw = os.environ.get("GATEWAY_EXTRA_HEADERS", "").strip()
    if raw:
        try:
            extra_headers = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("GATEWAY_EXTRA_HEADERS is not valid JSON — ignoring.")

    kwargs: dict = {"api_key": api_key}
    if base_url:
        kwargs["base_url"] = base_url
        if os.environ.get("GATEWAY_VERIFY_SSL", "true").lower() == "false":
            kwargs["http_client"] = httpx.Client(verify=False)
    if extra_headers:
        kwargs["default_headers"] = extra_headers

    client = _anthropic.Anthropic(**kwargs)
    msg = client.messages.create(
        model=model,
        max_tokens=2048,
        system=system,
        messages=messages,
    )
    return msg.content[0].text


def _chat_openai_compat(system: str, messages: List[Dict]) -> str:
    from openai import OpenAI

    base_url = os.environ.get("OPENAI_BASE_URL", "http://localhost:11434/v1").strip()
    api_key = os.environ.get("OPENAI_API_KEY", "ollama")
    model = os.environ.get("OPENAI_MODEL", "qwen2.5-coder:7b")

    client = OpenAI(base_url=base_url, api_key=api_key)
    response = client.chat.completions.create(
        model=model,
        max_tokens=2048,
        messages=[{"role": "system", "content": system}, *messages],
    )
    return response.choices[0].message.content


def _chat_ollama(system: str, messages: List[Dict]) -> str:
    os.environ.setdefault("OPENAI_BASE_URL", "http://localhost:11434/v1")
    os.environ.setdefault("OPENAI_API_KEY", "ollama")
    os.environ.setdefault("OPENAI_MODEL", "qwen2.5-coder:7b")
    return _chat_openai_compat(system, messages)


def _chat_gemini(system: str, messages: List[Dict]) -> str:
    import google.generativeai as genai

    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set.")

    model_name = os.environ.get("GEMINI_MODEL", "gemini-1.5-flash")
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(model_name=model_name, system_instruction=system)
    # Gemini uses "model" for the assistant role.
    contents = [
        {"role": "model" if m["role"] == "assistant" else "user", "parts": [m["content"]]}
        for m in messages
    ]
    response = model.generate_content(contents)
    return response.text


_CHAT_PROVIDERS = {
    "anthropic": _chat_anthropic,
    "ollama": _chat_ollama,
    "openai_compat": _chat_openai_compat,
    "gemini": _chat_gemini,
}


async def answer_question(
    question: str,
    history: List[Dict],
    files: List[Dict],
    issues: List[Dict],
) -> str:
    """Answer a question about the reviewed codebase, with short conversation memory."""
    system = CHAT_SYSTEM_PROMPT + "\n\n# CODEBASE CONTEXT\n" + build_context(files, issues)

    # Keep recent turns; ensure the sequence starts with a user message.
    hist = [
        {"role": m["role"], "content": m["content"]}
        for m in history
        if m.get("role") in ("user", "assistant") and m.get("content")
    ][-8:]
    while hist and hist[0]["role"] == "assistant":
        hist.pop(0)

    messages = [*hist, {"role": "user", "content": question}]

    provider = _provider()
    fn = _CHAT_PROVIDERS.get(provider)
    if fn is None:
        raise ValueError(
            f"Unknown LLM_PROVIDER='{provider}'. Valid options: {', '.join(_CHAT_PROVIDERS)}"
        )

    logger.info("Chat dispatch to provider=%s (%d files, %d issues)", provider, len(files), len(issues))
    return await asyncio.to_thread(fn, system, messages)
