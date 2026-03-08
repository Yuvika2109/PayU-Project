"""
core/pipeline.py  (v2)
Orchestration pipeline — now uses DatasetEngine directly for generation.
The LLM is only used for blueprint creation; no LLM-generated code is executed.
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

    def run(self, raw_input: str) -> PipelineResult:
        start = time.time()
        result = PipelineResult(success=False)

        try:
            # ── Step 1: Interpret scenario ────────────────────────────────────
            logger.info("═" * 60)
            logger.info("STEP 1 ▸ Interpreting scenario")
            scenario_params = self.interpreter.interpret(raw_input)
            result.scenario_params = scenario_params
            logger.info("Scenario: %s", json.dumps(scenario_params, indent=2))

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

            result.output_path   = output_path
            result.rows_generated= len(df)
            result.fraud_rows    = int(df["fraud_label"].sum())
            result.success       = True
            result.duration_seconds = time.time() - start

            logger.info("═" * 60)
            logger.info(
                "✅ Pipeline COMPLETE in %.1fs | rows=%d fraud=%d (%.1f%%) | output=%s",
                result.duration_seconds,
                result.rows_generated,
                result.fraud_rows,
                100 * result.fraud_rows / max(result.rows_generated, 1),
                output_path,
            )

        except Exception as exc:
            result.error = str(exc)
            result.duration_seconds = time.time() - start
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
            blueprint = self.bp_generator.fix(blueprint, errors)

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