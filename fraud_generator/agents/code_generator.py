"""
agents/code_generator.py
Uses an LLM to produce executable Python code from a Fraud Blueprint.
"""

from __future__ import annotations

import re
from typing import Any, Dict, Optional

from config.model_config import CODE_MODEL
from core.llm_interface import generate_code_response
from prompts.code_generation_prompt import build_code_generation_prompt
from utils.logger import get_logger

logger = get_logger("agents.code_generator")


class CodeGeneratorAgent:
    """
    Transforms a validated Fraud Blueprint into runnable Python code
    that generates a synthetic dataset.
    """

    def __init__(self, model_key: Optional[str] = None):
        self.model_key = model_key or CODE_MODEL

    def generate(self, blueprint: Dict[str, Any], output_path: str) -> str:
        """
        Generate Python source code from the blueprint.

        Parameters
        ----------
        blueprint   : Validated Fraud Blueprint dict.
        output_path : Where the generated script should write its output file.

        Returns
        -------
        str: Python source code as a string.
        """
        scenario = blueprint.get("Fraud_Scenario_Name", "Unknown")
        logger.info("Generating code for scenario: %s → %s", scenario, output_path)

        prompt = build_code_generation_prompt(blueprint, output_path)
        raw_code = generate_code_response(prompt, model_key=self.model_key)
        code = self._clean_code(raw_code)

        logger.info("Code generated: %d lines", code.count("\n"))
        return code

    # ─── Private ─────────────────────────────────────────────────────────────

    @staticmethod
    def _clean_code(raw: str) -> str:
        """
        Strip markdown fences and leading/trailing whitespace from LLM output.
        Handles both  ```python ... ```  and  ``` ... ```  variants.
        """
        # Remove opening fence (with optional language tag)
        raw = re.sub(r"^```(?:python)?\s*\n?", "", raw.strip(), flags=re.IGNORECASE)
        # Remove closing fence
        raw = re.sub(r"\n?```\s*$", "", raw.strip())
        return raw.strip()
