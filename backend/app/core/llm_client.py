# """
# Ollama LLM client.

# Recommended models (set OLLAMA_MODEL in .env):
#   • gpt-oss:20b          – your current model, good quality/speed tradeoff
#   • llama3:8b-instruct   – faster, less VRAM (~6 GB)
#   • llama3:70b-instruct  – best quality, ~40 GB VRAM
#   • mixtral:8x7b-instruct – MoE, fast & high quality
#   • mistral:7b-instruct  – lightweight option

# Pull a model:  ollama pull llama3:8b-instruct
# """
# from __future__ import annotations

# import json
# import re
# import logging
# from typing import Any

# import httpx

# from app.core.config import get_settings

# logger = logging.getLogger(__name__)
# settings = get_settings()


# class OllamaClient:
#     def __init__(self) -> None:
#         self.base_url = settings.OLLAMA_BASE_URL
#         self.model    = settings.OLLAMA_MODEL
#         self.timeout  = settings.OLLAMA_TIMEOUT
#         self.max_tokens = settings.OLLAMA_MAX_TOKENS

#     # ── low-level call ────────────────────────────────────────────────────────

#     async def chat(
#         self,
#         system: str,
#         user: str,
#         temperature: float = 0.2,
#         json_mode: bool = True,
#     ) -> str:
#         """
#         Send a chat request to Ollama /api/chat.
#         Returns the raw text content of the assistant turn.
#         """
#         payload: dict[str, Any] = {
#             "model": self.model,
#             "stream": False,
#             "options": {
#                 "temperature": temperature,
#                 "num_predict": self.max_tokens,
#             },
#             "messages": [
#                 {"role": "system", "content": system},
#                 {"role": "user",   "content": user},
#             ],
#         }
#         if json_mode:
#             payload["format"] = "json"

#         async with httpx.AsyncClient(timeout=self.timeout) as client:
#             try:
#                 resp = await client.post(
#                     f"{self.base_url}/api/chat",
#                     json=payload,
#                 )
#                 resp.raise_for_status()
#             except httpx.ConnectError:
#                 raise RuntimeError(
#                     f"Cannot connect to Ollama at {self.base_url}. "
#                     "Make sure Ollama is running: `ollama serve`"
#                 )
#             except httpx.HTTPStatusError as exc:
#                 raise RuntimeError(
#                     f"Ollama returned HTTP {exc.response.status_code}: "
#                     f"{exc.response.text[:400]}"
#                 )

#         data = resp.json()
#         return data["message"]["content"]

#     # ── JSON extraction ───────────────────────────────────────────────────────

#     async def chat_json(
#         self,
#         system: str,
#         user: str,
#         temperature: float = 0.2,
#         retries: int = 2,
#     ) -> dict:
#         """
#         Call chat() and parse the response as JSON.
#         Strips markdown fences if the model wraps the output.
#         Retries up to `retries` times on parse failure.
#         """
#         last_error: Exception | None = None
#         for attempt in range(retries + 1):
#             raw = await self.chat(system, user, temperature=temperature)
#             try:
#                 return self._parse_json(raw)
#             except (json.JSONDecodeError, ValueError) as exc:
#                 last_error = exc
#                 logger.warning("JSON parse attempt %d failed: %s", attempt + 1, exc)
#                 if attempt < retries:
#                     # nudge the model to fix itself
#                     user = (
#                         user
#                         + "\n\nIMPORTANT: Your previous response could not be parsed as JSON. "
#                         "Return ONLY a valid JSON object with no additional text."
#                     )

#         raise ValueError(
#             f"LLM did not return valid JSON after {retries + 1} attempts. "
#             f"Last error: {last_error}"
#         )

#     @staticmethod
#     def _parse_json(raw: str) -> dict:
#         """Strip markdown fences and parse JSON."""
#         text = raw.strip()
#         # remove ```json ... ``` or ``` ... ```
#         text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
#         text = re.sub(r"\s*```$", "", text)
#         text = text.strip()
#         return json.loads(text)

#     # ── health check ─────────────────────────────────────────────────────────

#     async def health(self) -> dict:
#         async with httpx.AsyncClient(timeout=10) as client:
#             try:
#                 resp = await client.get(f"{self.base_url}/api/tags")
#                 resp.raise_for_status()
#                 data = resp.json()
#                 model_names = [m["name"] for m in data.get("models", [])]
#                 return {
#                     "status": "ok",
#                     "ollama_url": self.base_url,
#                     "configured_model": self.model,
#                     "model_available": self.model in model_names,
#                     "available_models": model_names,
#                 }
#             except Exception as exc:
#                 return {"status": "error", "detail": str(exc)}


# # singleton
# _client: OllamaClient | None = None


# def get_llm_client() -> OllamaClient:
#     global _client
#     if _client is None:
#         _client = OllamaClient()
#     return _client


"""
Ollama LLM client.

Recommended models (set OLLAMA_MODEL in .env):
  • gpt-oss:20b           – good quality/speed tradeoff
  • llama3:8b-instruct    – faster, less VRAM (~6 GB)
  • llama3:70b-instruct   – best quality, ~40 GB VRAM
  • mixtral:8x7b-instruct – MoE, fast & high quality
  • mistral:7b-instruct   – lightweight option

Pull a model:  ollama pull llama3:8b-instruct
"""
from __future__ import annotations

import json
import re
import logging
from typing import Any, Dict

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class OllamaClient:
    def __init__(self) -> None:
        self.base_url = settings.OLLAMA_BASE_URL
        self.model = settings.OLLAMA_MODEL
        self.timeout = settings.OLLAMA_TIMEOUT
        self.max_tokens = settings.OLLAMA_MAX_TOKENS

    # ── low-level call ────────────────────────────────────────────────────────

    async def chat(
        self,
        system: str,
        user: str,
        temperature: float = 0.2,
        json_mode: bool = True,
    ) -> str:
        """
        Send a chat request to Ollama /api/chat.
        Returns the raw text content of the assistant turn.
        """
        payload: Dict[str, Any] = {
            "model": self.model,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": self.max_tokens,
            },
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        if json_mode:
            # Enables Ollama's structured JSON output mode
            payload["format"] = "json"  # or a JSON schema for even stricter control

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                resp = await client.post(
                    f"{self.base_url}/api/chat",
                    json=payload,
                )
                resp.raise_for_status()
            except httpx.ConnectError:
                raise RuntimeError(
                    f"Cannot connect to Ollama at {self.base_url}. "
                    "Make sure Ollama is running: `ollama serve`"
                )
            except httpx.HTTPStatusError as exc:
                raise RuntimeError(
                    f"Ollama returned HTTP {exc.response.status_code}: "
                    f"{exc.response.text[:400]}"
                )

        data = resp.json()
        # Ollama returns: {"message": {"role": "assistant", "content": "..."}}
        content = data.get("message", {}).get("content")
        if content is None:
            raise RuntimeError(f"Ollama response missing message.content: {data}")
        return content

    # ── JSON extraction ───────────────────────────────────────────────────────

    async def chat_json(
        self,
        system: str,
        user: str,
        temperature: float = 0.2,
        retries: int = 2,
    ) -> Dict[str, Any]:
        """
        Call chat() and parse the response as JSON.
        Strips markdown fences if the model wraps the output.
        Retries up to `retries` times on parse failure.
        """
        last_error: Exception | None = None
        last_raw: str | None = None

        for attempt in range(retries + 1):
            raw = await self.chat(system, user, temperature=temperature, json_mode=True)
            last_raw = raw
            try:
                parsed = self._parse_json(raw)
                if not isinstance(parsed, dict):
                    raise ValueError(f"Expected JSON object, got {type(parsed)}")
                return parsed
            except (json.JSONDecodeError, ValueError) as exc:
                last_error = exc
                logger.warning(
                    "JSON parse attempt %d failed: %s", attempt + 1, exc
                )
                if attempt < retries:
                    # Nudge the model to fix itself
                    user = (
                        user
                        + "\n\nIMPORTANT: Your previous response could not be parsed as JSON. "
                        "Return ONLY a valid JSON object with no additional text."
                    )

        # Final failure: log truncated raw output for inspection
        truncated = (last_raw or "")[:2000]
        logger.error(
            "LLM JSON parsing failed after %d attempts. Last error=%s, raw (truncated)=%r",
            retries + 1,
            last_error,
            truncated,
        )
        raise ValueError(
            f"LLM did not return valid JSON after {retries + 1} attempts. "
            f"Last error: {last_error}"
        )

    @staticmethod
    def _parse_json(raw: str) -> Any:
        """Strip markdown fences and parse JSON."""
        text = raw.strip()
        # remove ```json ... ``` or ``` ... ``` around the whole response
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)
        text = text.strip()
        return json.loads(text)

    # ── health check ─────────────────────────────────────────────────────────

    async def health(self) -> Dict[str, Any]:
        async with httpx.AsyncClient(timeout=10) as client:
            try:
                resp = await client.get(f"{self.base_url}/api/tags")
                resp.raise_for_status()
                data = resp.json()
                model_names = [m["name"] for m in data.get("models", [])]
                return {
                    "status": "ok",
                    "ollama_url": self.base_url,
                    "configured_model": self.model,
                    "model_available": self.model in model_names,
                    "available_models": model_names,
                }
            except Exception as exc:
                return {"status": "error", "detail": str(exc)}


# singleton
_client: OllamaClient | None = None


def get_llm_client() -> OllamaClient:
    global _client
    if _client is None:
        _client = OllamaClient()
    return _client