"""
core/llm_interface.py  (v3)
Unified LLM interface supporting Ollama (Llama3, Qwen2.5-Coder) and any
OpenAI-compatible endpoint.  All calls go through `generate_response()`.

v3 change: fixed Ollama timeout
---------------------------------
The blueprint prompt is ~7800 chars.  On modest hardware llama3 can take
8–12 minutes to generate the full JSON response.  Two fixes applied:

  1. timeout raised from 300 s → OLLAMA_REQUEST_TIMEOUT (default 900 s, ~15 min)
  2. num_ctx capped at OLLAMA_NUM_CTX (default 4096) so Ollama doesn't allocate
     a huge KV-cache that dramatically slows time-to-first-token.
he
Both values are env-var overridable in .env / environment.
"""

from __future__ import annotations

import json
import time
from typing import Optional

import requests

from config.model_config import (
    AVAILABLE_MODELS,
    CODE_MODEL,
    LLM_BACKEND,
    LLM_MAX_TOKENS,
    LLM_TEMPERATURE,
    OLLAMA_BASE_URL,
    OLLAMA_NUM_CTX,           # NEW (v3)
    OLLAMA_REQUEST_TIMEOUT,   # NEW (v3)
    PRIMARY_MODEL,
)
from utils.logger import get_logger

logger = get_logger("core.llm_interface")


# ─── Public API ───────────────────────────────────────────────────────────────

def generate_response(
    prompt: str,
    model_key: Optional[str] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    retries: int = 3,
    retry_delay: float = 2.0,
) -> str:
    """
    Send *prompt* to the configured LLM and return the text response.

    Parameters
    ----------
    prompt:      The full prompt string.
    model_key:   Key from AVAILABLE_MODELS.  Defaults to PRIMARY_MODEL.
    temperature: Sampling temperature (defaults to LLM_TEMPERATURE).
    max_tokens:  Max new tokens (defaults to LLM_MAX_TOKENS).
    retries:     Number of retry attempts on transient errors.
    retry_delay: Seconds between retries (exponential back-off × 2).

    Returns
    -------
    str: The model's text response.

    Raises
    ------
    RuntimeError: If all retry attempts are exhausted.
    """
    model_key = model_key or PRIMARY_MODEL
    temperature = temperature if temperature is not None else LLM_TEMPERATURE
    max_tokens = max_tokens or LLM_MAX_TOKENS

    model_name = AVAILABLE_MODELS.get(model_key, model_key)
    logger.info("LLM call | model=%s | prompt_len=%d chars", model_name, len(prompt))

    last_error: Exception = RuntimeError("No attempts made")

    for attempt in range(1, retries + 1):
        try:
            if LLM_BACKEND == "ollama":
                response = _call_ollama(prompt, model_name, temperature, max_tokens)
            else:
                response = _call_openai_compatible(
                    prompt, model_name, temperature, max_tokens
                )

            logger.debug(
                "LLM response | model=%s | response_len=%d chars",
                model_name,
                len(response),
            )
            return response

        except Exception as exc:  # noqa: BLE001
            last_error = exc
            wait = retry_delay * (2 ** (attempt - 1))
            logger.warning(
                "LLM call failed (attempt %d/%d): %s – retrying in %.1fs",
                attempt,
                retries,
                exc,
                wait,
            )
            time.sleep(wait)

    raise RuntimeError(
        f"LLM call failed after {retries} attempts: {last_error}"
    ) from last_error


def generate_code_response(prompt: str, **kwargs) -> str:
    """Convenience wrapper that uses CODE_MODEL by default.

    Callers may override the model by passing model_key as a keyword argument.
    If model_key is already in kwargs (e.g. from CodeGeneratorAgent), it takes
    precedence over the default CODE_MODEL.
    """
    kwargs.setdefault("model_key", CODE_MODEL)
    return generate_response(prompt, **kwargs)


# ─── Backend Implementations ─────────────────────────────────────────────────

def _call_ollama(
    prompt: str, model: str, temperature: float, max_tokens: int
) -> str:
    """
    Call a local Ollama instance via its REST API.

    v3 changes vs original
    ----------------------
    timeout : raised from hard-coded 300 s to OLLAMA_REQUEST_TIMEOUT (900 s default).
              The blueprint prompt (~7800 chars) can take 8-12 min on a mid-range GPU.
    num_ctx : capped at OLLAMA_NUM_CTX (4096 default).  Without this, Ollama may
              allocate a 32k+ KV-cache, dramatically increasing time-to-first-token.
              Raise to 8192 in .env only if you see blueprint JSON getting cut off.
    """
    url = f"{OLLAMA_BASE_URL}/api/generate"
    payload = {
        "model":  model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": temperature,
            "num_predict": max_tokens,
            "num_ctx":     OLLAMA_NUM_CTX,    # NEW (v3): cap context window
        },
    }

    resp = requests.post(url, json=payload, timeout=OLLAMA_REQUEST_TIMEOUT)  # raised (v3)
    resp.raise_for_status()
    data = resp.json()

    if "response" not in data:
        raise ValueError(f"Unexpected Ollama response structure: {list(data.keys())}")

    return data["response"].strip()


def _call_openai_compatible(
    prompt: str, model: str, temperature: float, max_tokens: int
) -> str:
    """
    Call any OpenAI-compatible endpoint (e.g. LM Studio, vLLM, Together AI).
    Reads OPENAI_BASE_URL / OPENAI_API_KEY from environment.
    """
    import os

    base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    api_key  = os.getenv("OPENAI_API_KEY", "")

    url = f"{base_url}/chat/completions"
    headers = {
        "Content-Type":  "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    payload = {
        "model":       model,
        "messages":    [{"role": "user", "content": prompt}],
        "temperature": temperature,
        "max_tokens":  max_tokens,
    }

    resp = requests.post(url, headers=headers, json=payload,
                         timeout=OLLAMA_REQUEST_TIMEOUT)   # raised (v3)
    resp.raise_for_status()
    data = resp.json()
    return data["choices"][0]["message"]["content"].strip()