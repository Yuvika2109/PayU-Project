"""
agents/blueprint_generator.py  (v3)
Uses an LLM to convert interpreted scenario parameters into a full
Fraud Blueprint JSON.

v3 fix: _enforce_user_values() overwrites Dataset_Specifications with the
exact values the user specified immediately after every successful JSON parse
and after every fix round.  The LLM frequently ignores the TARGET SCENARIO
rows/ratio in the prompt and writes its own defaults (10000 rows, 5% fraud).
scenario_params is always authoritative over whatever the LLM wrote.
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


# ── User-value enforcement (new in v3) ────────────────────────────────────────

def _enforce_user_values(
    blueprint: Dict[str, Any], scenario_params: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Overwrite Dataset_Specifications with the exact values the user specified.

    The LLM often ignores the TARGET SCENARIO block in the prompt and writes
    its own defaults (10000 rows, 0.05 fraud ratio).  This function is called
    immediately after every successful JSON parse and after every fix round,
    so user values are always authoritative.

    Also scales num_users and num_merchants proportionally to the actual
    row count if the LLM set them for a different scale.
    """
    specs = blueprint.setdefault("Dataset_Specifications", {})

    user_rows  = scenario_params["rows"]
    user_ratio = scenario_params["fraud_ratio"]
    user_fmt   = scenario_params["output_format"]

    # Log when LLM ignored user values
    llm_rows  = specs.get("total_rows")
    llm_ratio = specs.get("fraud_ratio")
    if llm_rows is not None and llm_rows != user_rows:
        logger.warning(
            "LLM wrote total_rows=%s — overriding with user value %d",
            llm_rows, user_rows,
        )
    if llm_ratio is not None and llm_ratio != user_ratio:
        logger.warning(
            "LLM wrote fraud_ratio=%s — overriding with user value %.4f",
            llm_ratio, user_ratio,
        )

    # Enforce the three values that must always match user input
    specs["total_rows"]    = user_rows
    specs["fraud_ratio"]   = user_ratio
    specs["output_format"] = user_fmt

    # Scale num_users / num_merchants proportionally to the actual row count.
    # If the LLM calibrated pools for 10k rows but user wants 50k, scale up.
    llm_scale    = max(llm_rows or user_rows, 1)
    scale_factor = user_rows / llm_scale

    for key, fallback_ratio in [("num_users", 0.067), ("num_merchants", 0.01)]:
        existing = specs.get(key)
        if existing and existing > 0 and scale_factor != 1.0:
            specs[key] = max(10, int(existing * scale_factor))
        elif not existing or existing < 1:
            specs[key] = max(10, int(user_rows * fallback_ratio))

    return blueprint


# ── Agent ─────────────────────────────────────────────────────────────────────

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
        dict: Parsed blueprint JSON with Dataset_Specifications enforced
              to match user-specified rows, fraud_ratio, and output_format.

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
            user_context=scenario_params.get("user_context", ""),
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

                # ── Enforce user values — LLM may have ignored them ───────
                blueprint = _enforce_user_values(blueprint, scenario_params)

                logger.info("Blueprint generated successfully on attempt %d", attempt)
                return blueprint

            except Exception as exc:  # noqa: BLE001
                logger.error("Attempt %d failed: %s", attempt, exc)
                if attempt == MAX_BLUEPRINT_RETRIES:
                    raise RuntimeError(
                        f"Blueprint generation failed after {MAX_BLUEPRINT_RETRIES} attempts: {exc}"
                    ) from exc

        raise RuntimeError("Blueprint generation exhausted all retries")

    def fix(
        self,
        blueprint: Dict[str, Any],
        errors: list[str],
        scenario_params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Ask the LLM to fix a blueprint that failed validation.

        Parameters
        ----------
        blueprint       : The invalid blueprint dict.
        errors          : List of human-readable validation error strings.
        scenario_params : Original user params — if provided, user values are
                          re-enforced after the fix so the LLM cannot reset
                          rows/ratio during a validation fix round.
                          Optional so existing callers without this arg
                          continue to work unchanged.

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

        # Re-enforce user values after fix — LLM may have reset them
        if scenario_params:
            fixed = _enforce_user_values(fixed, scenario_params)

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