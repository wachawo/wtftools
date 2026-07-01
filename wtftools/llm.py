#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Optional LLM bridges for `wtf explain --llm …`.

Each backend is best-effort: it returns the model's text on success or None
when the backend isn't available (binary missing, SDK not installed, no API
key, network error, …). The caller is expected to fall back gracefully.

Supported backends:
    ollama   subprocess: ollama run <model>
    claude   anthropic Python SDK + ANTHROPIC_API_KEY env
    openai   openai Python SDK + OPENAI_API_KEY env
    auto     local ollama only — remote backends must be named explicitly so
             data never leaves the host implicitly

All backends accept the same `prompt` string. We pass `wtf explain --prompt`
output verbatim; the model is expected to produce per-finding diagnoses.
"""

import logging
import os
import shutil
import subprocess
import traceback
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

# Sensible defaults; can be overridden via --llm-model.
DEFAULT_OLLAMA_MODEL = os.environ.get("WTFTOOLS_OLLAMA_MODEL", "llama3.1")
DEFAULT_CLAUDE_MODEL = os.environ.get("WTFTOOLS_CLAUDE_MODEL", "claude-haiku-4-5-20251001")
DEFAULT_OPENAI_MODEL = os.environ.get("WTFTOOLS_OPENAI_MODEL", "gpt-4o-mini")


def call_ollama(prompt: str, model: Optional[str] = None, timeout: int = 60) -> Tuple[Optional[str], Optional[str]]:
    """Run a local model via the ollama CLI. Returns (text, error)."""
    if not shutil.which("ollama"):
        return None, "ollama binary not found in PATH"
    chosen = model or DEFAULT_OLLAMA_MODEL
    try:
        result = subprocess.run(
            ["ollama", "run", chosen],
            input=prompt,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return None, f"ollama timed out after {timeout}s"
    except Exception as exc:
        return None, f"ollama exec failed: {type(exc).__name__}: {exc}"
    if result.returncode != 0:
        err = (result.stderr or "").strip()[:200]
        return None, f"ollama exit {result.returncode}: {err}"
    return result.stdout, None


def call_claude(prompt: str, model: Optional[str] = None, timeout: int = 30) -> Tuple[Optional[str], Optional[str]]:
    """Use Anthropic SDK if installed and ANTHROPIC_API_KEY is set."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None, "ANTHROPIC_API_KEY not set"
    try:
        import anthropic  # type: ignore
    except ImportError:
        return None, "anthropic SDK not installed (pip install anthropic)"
    chosen = model or DEFAULT_CLAUDE_MODEL
    try:
        client = anthropic.Anthropic(api_key=api_key, timeout=timeout)
        response = client.messages.create(
            model=chosen,
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}],
        )
        text = "".join(getattr(b, "text", "") for b in response.content)
        return text, None
    except Exception as exc:
        logger.debug(f"claude call failed: {type(exc).__name__}: {exc}\n" f"{traceback.format_exc()}")
        return None, f"claude API error: {type(exc).__name__}: {exc}"


def call_openai(prompt: str, model: Optional[str] = None, timeout: int = 30) -> Tuple[Optional[str], Optional[str]]:
    """Use OpenAI SDK if installed and OPENAI_API_KEY is set."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return None, "OPENAI_API_KEY not set"
    try:
        from openai import OpenAI  # type: ignore
    except ImportError:
        return None, "openai SDK not installed (pip install openai)"
    chosen = model or DEFAULT_OPENAI_MODEL
    try:
        client = OpenAI(api_key=api_key, timeout=timeout)
        response = client.chat.completions.create(
            model=chosen,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.choices[0].message.content, None
    except Exception as exc:
        logger.debug(f"openai call failed: {type(exc).__name__}: {exc}\n" f"{traceback.format_exc()}")
        return None, f"openai API error: {type(exc).__name__}: {exc}"


_BACKENDS = {
    "ollama": call_ollama,
    "claude": call_claude,
    "openai": call_openai,
}

# Backends that send data off the host. The CLI discloses egress and asks for
# confirmation before invoking one of these.
REMOTE_BACKENDS = frozenset({"claude", "openai"})


def call_llm(backend: str, prompt: str, model: Optional[str] = None, timeout: Optional[int] = None) -> Tuple[Optional[str], Optional[str]]:
    """Dispatch to the named backend, or try them all when backend == 'auto'."""
    if backend == "auto":
        # Local only: never send data off-box implicitly. Remote backends
        # (claude/openai) must be requested by name so egress is explicit.
        kwargs = {"model": model}
        if timeout is not None:
            kwargs["timeout"] = timeout
        text, err = _BACKENDS["ollama"](prompt, **kwargs)
        if text is not None:
            return text, "via ollama"
        return None, f"no local LLM available ({err}); run --llm claude or --llm openai to use a remote model"
    fn = _BACKENDS.get(backend)
    if fn is None:
        return None, f"unknown backend: {backend!r} (use ollama/claude/openai/auto)"
    kwargs = {"model": model}
    if timeout is not None:
        kwargs["timeout"] = timeout
    return fn(prompt, **kwargs)
