"""
agents/error_fix_agent.py
Calls the LLM to repair generated code that failed during execution.
"""

from __future__ import annotations

import re
from typing import Any, Dict

from config.model_config import CODE_MODEL, MAX_CODE_RETRIES
from core.llm_interface import generate_code_response
from prompts.error_fix_prompt import build_error_fix_prompt
from utils.logger import get_logger

logger = get_logger("agents.error_fix_agent")


class ErrorFixAgent:
    """
    Accepts a blueprint, failing code, and error message.
    Returns corrected Python code via an LLM call.
    Maintains an internal attempt counter for prompt context.
    """

    def __init__(self, model_key: str | None = None):
        self.model_key = model_key or CODE_MODEL
        self._attempt = 0

    def fix(
        self,
        blueprint: Dict[str, Any],
        broken_code: str,
        error_message: str,
    ) -> str:
        """
        Request a fix from the LLM.

        Parameters
        ----------
        blueprint     : Validated Fraud Blueprint dict.
        broken_code   : The Python source that raised an error.
        error_message : Full traceback string.

        Returns
        -------
        str: Corrected Python source code.

        Raises
        ------
        RuntimeError: If the maximum number of fix attempts has been exceeded.
        """
        self._attempt += 1

        if self._attempt > MAX_CODE_RETRIES:
            raise RuntimeError(
                f"Error fix agent exceeded maximum retries ({MAX_CODE_RETRIES}). "
                "Cannot recover from persistent execution errors."
            )

        logger.info(
            "Error fix attempt %d/%d | error snippet: %.120s …",
            self._attempt,
            MAX_CODE_RETRIES,
            error_message.replace("\n", " "),
        )

        prompt = build_error_fix_prompt(
            blueprint=blueprint,
            broken_code=broken_code,
            error_message=error_message,
            attempt=self._attempt,
        )

        raw = generate_code_response(prompt, model_key=self.model_key)
        fixed_code = self._clean_code(raw)

        logger.info("Fixed code received: %d lines", fixed_code.count("\n"))
        return fixed_code

    def reset(self) -> None:
        """Reset attempt counter (call when starting a new pipeline run)."""
        self._attempt = 0

    @property
    def attempts_used(self) -> int:
        return self._attempt

    # ─── Private ─────────────────────────────────────────────────────────────

    @staticmethod
    def _clean_code(raw: str) -> str:
        raw = re.sub(r"^```(?:python)?\s*\n?", "", raw.strip(), flags=re.IGNORECASE)
        raw = re.sub(r"\n?```\s*$", "", raw.strip())
        return raw.strip()
