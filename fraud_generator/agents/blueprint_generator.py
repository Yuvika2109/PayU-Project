"""
agents/blueprint_generator.py
Uses an LLM to convert interpreted scenario parameters into a full
Fraud Blueprint JSON.
"""

from __future__ import annotations

import json
from typing import Any, Dict, Optional

from config.model_config import MAX_BLUEPRINT_RETRIES, PRIMARY_MODEL
from core.llm_interface import generate_response
from prompts.blueprint_prompt import BLUEPRINT_FIX_PROMPT_TEMPLATE, build_blueprint_prompt
from utils.json_parser import extract_json
from utils.logger import get_logger

logger = get_logger("agents.blueprint_generator")


class BlueprintGeneratorAgent:
    """
    Calls an LLM to produce a structured Fraud Blueprint JSON from
    scenario parameters returned by the ScenarioInterpreterAgent.
    """

    def __init__(self, model_key: Optional[str] = None):
        self.model_key = model_key or PRIMARY_MODEL

    def generate(self, scenario_params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate a blueprint for the given scenario parameters.

        Parameters
        ----------
        scenario_params : Output of ScenarioInterpreterAgent.interpret()

        Returns
        -------
        dict: Parsed blueprint JSON.

        Raises
        ------
        RuntimeError: If the LLM fails to produce parseable JSON after retries.
        """
        logger.info(
            "Generating blueprint for scenario: %s",
            scenario_params.get("scenario_name"),
        )

        prompt = build_blueprint_prompt(
            scenario_name=scenario_params["scenario_name"],
            description=scenario_params.get("description", ""),
            fraud_type=scenario_params.get("fraud_type", ""),
            total_rows=scenario_params["rows"],
            fraud_ratio=scenario_params["fraud_ratio"],
            output_format=scenario_params["output_format"],
        )

        for attempt in range(1, MAX_BLUEPRINT_RETRIES + 1):
            logger.info("Blueprint generation attempt %d/%d", attempt, MAX_BLUEPRINT_RETRIES)
            try:
                raw = generate_response(prompt, model_key=self.model_key)
                blueprint = extract_json(raw)

                if blueprint is None:
                    logger.warning(
                        "Attempt %d: LLM did not return parseable JSON – retrying", attempt
                    )
                    prompt = self._build_retry_prompt(prompt, raw)
                    continue

                logger.info("Blueprint generated successfully on attempt %d", attempt)
                return blueprint

            except Exception as exc:  # noqa: BLE001
                logger.error("Attempt %d failed: %s", attempt, exc)
                if attempt == MAX_BLUEPRINT_RETRIES:
                    raise RuntimeError(
                        f"Blueprint generation failed after {MAX_BLUEPRINT_RETRIES} attempts: {exc}"
                    ) from exc

        raise RuntimeError("Blueprint generation exhausted all retries")

    def fix(self, blueprint: Dict[str, Any], errors: list[str]) -> Dict[str, Any]:
        """
        Ask the LLM to fix a blueprint that failed validation.

        Parameters
        ----------
        blueprint : The invalid blueprint dict.
        errors    : List of human-readable validation error strings.

        Returns
        -------
        dict: Fixed blueprint (may still be invalid – caller validates again).
        """
        logger.info("Requesting LLM blueprint fix for %d error(s)", len(errors))

        prompt = BLUEPRINT_FIX_PROMPT_TEMPLATE.format(
            errors="\n".join(f"  - {e}" for e in errors),
            blueprint_json=json.dumps(blueprint, indent=2),
        )

        raw = generate_response(prompt, model_key=self.model_key)
        fixed = extract_json(raw)

        if fixed is None:
            logger.error("LLM fix attempt returned non-JSON response")
            return blueprint  # return original; validator will catch it again

        return fixed

    # ─── Private ─────────────────────────────────────────────────────────────

    @staticmethod
    def _build_retry_prompt(original_prompt: str, bad_response: str) -> str:
        return (
            original_prompt
            + f"\n\n[PREVIOUS ATTEMPT FAILED – non-JSON response received]\n"
            f"Previous response (first 200 chars): {bad_response[:200]}\n"
            "Please respond with ONLY a valid JSON object this time."
        )
