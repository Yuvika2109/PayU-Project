"""
core/pipeline.py  (v3)
Orchestration pipeline — uses DatasetEngine directly for generation.
The LLM is only used for blueprint creation; no LLM-generated code is executed.

v3 change: added run_from_params() so main.py can interpret the scenario
first, echo the parsed params to the user immediately, and then hand the
pre-parsed params to the pipeline — avoiding a duplicate interpret() call
and ensuring "INTERPRETED AS" prints BEFORE the slow blueprint LLM call.
run() is preserved unchanged for any callers that pass raw text directly.

v3 fix (rows/ratio): _generate_and_validate_blueprint() now passes
scenario_params to bp_generator.fix() so _enforce_user_values() re-runs
after every fix round — prevents the LLM from resetting user's rows/ratio
values during the validation loop.
Change: one argument added to the existing fix() call on line ~114.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

from agents.blueprint_generator import BlueprintGeneratorAgent
from agents.blueprint_validator import BlueprintValidatorAgent
from agents.scenario_interpreter import ScenarioInterpreterAgent
from config.model_config import MAX_BLUEPRINT_RETRIES, OUTPUT_DIR
from core.dataset_engine import DatasetEngine, save_dataset
from utils.logger import get_logger

logger = get_logger("core.pipeline")


@dataclass
class PipelineResult:
    success: bool
    scenario_params: Dict[str, Any]  = field(default_factory=dict)
    blueprint: Dict[str, Any]        = field(default_factory=dict)
    output_path: str                 = ""
    error: str                       = ""
    duration_seconds: float          = 0.0
    rows_generated: int              = 0
    fraud_rows: int                  = 0


class FraudDataPipeline:
    """
    Full agentic pipeline:

    1. ScenarioInterpreterAgent  – parse user text
    2. BlueprintGeneratorAgent   – LLM → quantitative blueprint JSON
    3. BlueprintValidatorAgent   – validate / loop-fix blueprint
    4. DatasetEngine             – static deterministic generation (no LLM code)
    5. Save dataset + artifacts
    """

    def __init__(self):
        self.interpreter  = ScenarioInterpreterAgent()
        self.bp_generator = BlueprintGeneratorAgent()
        self.bp_validator = BlueprintValidatorAgent()
        os.makedirs(OUTPUT_DIR, exist_ok=True)

    # ─── Public entry points ──────────────────────────────────────────────────

    def run(self, raw_input: str) -> PipelineResult:
        """
        Original entry point — interprets raw text then runs the full pipeline.
        Preserved unchanged so any existing callers continue to work.
        """
        start = time.time()
        result = PipelineResult(success=False)

        try:
            # ── Step 1: Interpret scenario ────────────────────────────────────
            logger.info("═" * 60)
            logger.info("STEP 1 ▸ Interpreting scenario")
            scenario_params = self.interpreter.interpret(raw_input)
            result.scenario_params = scenario_params
            logger.info("Scenario: %s", json.dumps(scenario_params, indent=2))

            # ── Steps 2-5: delegate to run_from_params ────────────────────────
            inner = self._run_pipeline(scenario_params)
            # Merge inner result fields into result, preserving start time
            result.blueprint        = inner.blueprint
            result.output_path      = inner.output_path
            result.error            = inner.error
            result.rows_generated   = inner.rows_generated
            result.fraud_rows       = inner.fraud_rows
            result.success          = inner.success

        except Exception as exc:
            result.error = str(exc)
            logger.error("❌ Pipeline FAILED: %s", exc, exc_info=True)

        result.duration_seconds = time.time() - start
        return result

    def run_from_params(self, scenario_params: Dict[str, Any]) -> PipelineResult:
        """
        NEW (v3) — accepts already-interpreted scenario params and runs
        steps 2-5 (blueprint generation, validation, dataset generation, save).

        Called by main.py when the caller has already run interpreter.interpret()
        and printed the params to the user — this avoids a second interpret() call
        and ensures the console echo happens before the slow LLM blueprint call.
        """
        start  = time.time()
        result = self._run_pipeline(scenario_params)
        result.duration_seconds = time.time() - start
        return result

    # ─── Core pipeline (steps 2-5) ────────────────────────────────────────────

    def _run_pipeline(self, scenario_params: Dict[str, Any]) -> PipelineResult:
        """
        Steps 2-5: blueprint generation + validation, dataset generation, save.
        Returns a PipelineResult (duration_seconds not yet set by this method).
        """
        result = PipelineResult(success=False, scenario_params=scenario_params)

        try:
            # ── Step 2 + 3: Generate & validate blueprint ─────────────────────
            logger.info("═" * 60)
            logger.info("STEP 2 ▸ Generating blueprint")
            blueprint = self._generate_and_validate_blueprint(scenario_params)
            result.blueprint = blueprint
            blueprint_path = self._save_blueprint(blueprint, scenario_params)
            logger.info("Blueprint saved: %s", blueprint_path)

            # ── Step 4: Generate dataset via static engine ────────────────────
            logger.info("═" * 60)
            logger.info("STEP 3 ▸ Generating dataset via DatasetEngine")
            engine = DatasetEngine(blueprint, seed=42)
            df = engine.generate()

            # ── Step 5: Save ──────────────────────────────────────────────────
            output_path = self._build_output_path(scenario_params)
            fmt = scenario_params.get("output_format", "csv")
            save_dataset(df, output_path, fmt)

            result.output_path    = output_path
            result.rows_generated = len(df)
            result.fraud_rows     = int(df["fraud_label"].sum())
            result.success        = True

            logger.info("═" * 60)
            logger.info(
                "✅ Pipeline COMPLETE | rows=%d fraud=%d (%.1f%%) | output=%s",
                result.rows_generated,
                result.fraud_rows,
                100 * result.fraud_rows / max(result.rows_generated, 1),
                output_path,
            )

        except Exception as exc:
            result.error = str(exc)
            logger.error("❌ Pipeline FAILED: %s", exc, exc_info=True)

        return result

    # ─── Private ─────────────────────────────────────────────────────────────

    def _generate_and_validate_blueprint(
        self, scenario_params: Dict[str, Any]
    ) -> Dict[str, Any]:
        blueprint = self.bp_generator.generate(scenario_params)

        for fix_round in range(MAX_BLUEPRINT_RETRIES):
            logger.info("STEP 2.%d ▸ Validating blueprint", fix_round + 1)
            is_valid, errors = self.bp_validator.validate(blueprint)

            if is_valid:
                logger.info("Blueprint valid ✓")
                return blueprint

            logger.warning(
                "Blueprint invalid (%d errors) – requesting LLM fix", len(errors)
            )
            # Pass scenario_params so _enforce_user_values re-runs after fix ←v3 fix
            blueprint = self.bp_generator.fix(blueprint, errors, scenario_params)

        is_valid, errors = self.bp_validator.validate(blueprint)
        if not is_valid:
            raise RuntimeError(
                f"Blueprint still invalid after {MAX_BLUEPRINT_RETRIES} fix rounds. "
                f"Errors: {errors}"
            )
        return blueprint

    def _build_output_path(self, scenario_params: Dict[str, Any]) -> str:
        safe = (
            scenario_params.get("scenario_name", "fraud")
            .lower().replace(" ", "_").replace("-", "_")
        )
        fmt = scenario_params.get("output_format", "csv")
        return str(Path(OUTPUT_DIR) / f"{safe}_synthetic_dataset.{fmt}")

    def _save_blueprint(
        self, blueprint: Dict[str, Any], scenario_params: Dict[str, Any]
    ) -> str:
        safe = (
            scenario_params.get("scenario_name", "fraud")
            .lower().replace(" ", "_")
        )
        path = str(Path(OUTPUT_DIR) / f"{safe}_blueprint.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(blueprint, fh, indent=2, ensure_ascii=False)
        return path