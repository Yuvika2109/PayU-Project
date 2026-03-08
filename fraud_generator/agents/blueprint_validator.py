"""
agents/blueprint_validator.py  (v2)
Validates a v2 Fraud Blueprint — checks quantitative fields specifically.
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

from schemas.blueprint_schema import (
    BLUEPRINT_SCHEMA,
    QUANTITATIVE_CHECKS,
    REQUIRED_TOP_LEVEL_KEYS,
)
from utils.logger import get_logger

logger = get_logger("agents.blueprint_validator")

try:
    import jsonschema
    _HAS_JSONSCHEMA = True
except ImportError:
    _HAS_JSONSCHEMA = False
    logger.warning("jsonschema not installed – using lightweight validation only")


class BlueprintValidatorAgent:
    """
    Validate a v2 blueprint dict.
    Returns (is_valid: bool, errors: List[str]).
    """

    def validate(self, blueprint: Dict[str, Any]) -> Tuple[bool, List[str]]:
        errors: List[str] = []

        errors.extend(self._check_required_keys(blueprint))
        errors.extend(self._check_dataset_specs(blueprint))
        errors.extend(self._check_normal_profile(blueprint))
        errors.extend(self._check_fraud_patterns(blueprint))
        errors.extend(self._check_injection_rules(blueprint))
        errors.extend(self._check_sequence_rules(blueprint))
        errors.extend(self._check_quantitative_fields(blueprint))

        if _HAS_JSONSCHEMA:
            errors.extend(self._jsonschema_validate(blueprint))

        if errors:
            logger.warning("Blueprint INVALID — %d error(s)", len(errors))
            for e in errors:
                logger.debug("  ✗ %s", e)
        else:
            logger.info("Blueprint VALID ✓")

        return len(errors) == 0, errors

    # ─── Checks ──────────────────────────────────────────────────────────────

    def _check_required_keys(self, bp: Dict) -> List[str]:
        return [
            f"Missing required key: '{k}'"
            for k in REQUIRED_TOP_LEVEL_KEYS
            if k not in bp
        ]

    def _check_dataset_specs(self, bp: Dict) -> List[str]:
        errors = []
        specs = bp.get("Dataset_Specifications", {})
        if not isinstance(specs, dict):
            return ["Dataset_Specifications must be an object"]

        for field in ("total_rows", "fraud_ratio", "output_format",
                      "date_range_start", "date_range_end",
                      "num_users", "num_merchants"):
            if field not in specs:
                errors.append(f"Dataset_Specifications missing: '{field}'")

        if "total_rows" in specs:
            if not isinstance(specs["total_rows"], int) or specs["total_rows"] < 1:
                errors.append("Dataset_Specifications.total_rows must be a positive integer")

        if "fraud_ratio" in specs:
            try:
                r = float(specs["fraud_ratio"])
                if not 0 < r < 1:
                    errors.append(f"Dataset_Specifications.fraud_ratio must be in (0,1), got {r}")
            except (TypeError, ValueError):
                errors.append("Dataset_Specifications.fraud_ratio must be numeric")

        return errors

    def _check_normal_profile(self, bp: Dict) -> List[str]:
        errors = []
        prof = bp.get("Normal_User_Profile", {})
        if not isinstance(prof, dict):
            return ["Normal_User_Profile must be an object"]

        required = [
            "transaction_amount", "transactions_per_day",
            "active_hours", "active_days",
            "merchant_category_weights", "currency_weights",
        ]
        for f in required:
            if f not in prof:
                errors.append(f"Normal_User_Profile missing: '{f}'")

        # transaction_amount must have numeric sub-fields
        ta = prof.get("transaction_amount", {})
        if isinstance(ta, dict):
            for sub in ("min", "max", "mean", "std"):
                if sub not in ta:
                    errors.append(f"Normal_User_Profile.transaction_amount missing: '{sub}'")
                elif not isinstance(ta[sub], (int, float)):
                    errors.append(
                        f"Normal_User_Profile.transaction_amount.{sub} must be numeric, "
                        f"got: {ta[sub]!r}"
                    )
            if "distribution" in ta and ta["distribution"] not in (
                "normal", "lognormal", "uniform", "pareto"
            ):
                errors.append(
                    f"Normal_User_Profile.transaction_amount.distribution must be one of "
                    f"normal/lognormal/uniform/pareto, got: {ta['distribution']!r}"
                )

        # merchant_category_weights must have at least one numeric value
        mcw = prof.get("merchant_category_weights", {})
        if isinstance(mcw, dict):
            non_numeric = [k for k, v in mcw.items() if not isinstance(v, (int, float))]
            if non_numeric:
                errors.append(
                    f"Normal_User_Profile.merchant_category_weights values must be numeric. "
                    f"Non-numeric keys: {non_numeric}"
                )

        return errors

    def _check_fraud_patterns(self, bp: Dict) -> List[str]:
        errors = []
        patterns = bp.get("Fraud_Patterns", [])
        if not isinstance(patterns, list) or len(patterns) == 0:
            return ["Fraud_Patterns must be a non-empty array"]

        valid_seq_types = {"independent", "burst", "chain", "network"}

        for i, p in enumerate(patterns):
            if not isinstance(p, dict):
                errors.append(f"Fraud_Patterns[{i}] must be an object")
                continue

            for f in ("pattern_name", "description", "weight", "params", "sequence_type"):
                if f not in p:
                    errors.append(f"Fraud_Patterns[{i}] missing field: '{f}'")

            if "weight" in p and not isinstance(p["weight"], (int, float)):
                errors.append(f"Fraud_Patterns[{i}].weight must be numeric")

            if "sequence_type" in p and p["sequence_type"] not in valid_seq_types:
                errors.append(
                    f"Fraud_Patterns[{i}].sequence_type must be one of {valid_seq_types}, "
                    f"got: {p['sequence_type']!r}"
                )

            params = p.get("params", {})
            if not isinstance(params, dict):
                errors.append(f"Fraud_Patterns[{i}].params must be an object")
            else:
                # All params values must be numeric, boolean, or list of ints
                bad_params = []
                for pk, pv in params.items():
                    if isinstance(pv, list):
                        if not all(isinstance(x, (int, float)) for x in pv):
                            bad_params.append(pk)
                    elif not isinstance(pv, (int, float, bool)):
                        bad_params.append(pk)
                if bad_params:
                    errors.append(
                        f"Fraud_Patterns[{i}].params — non-numeric values for keys: "
                        f"{bad_params}. All params must be numbers, booleans, "
                        f"or arrays of numbers."
                    )

        return errors

    def _check_injection_rules(self, bp: Dict) -> List[str]:
        errors = []
        inj = bp.get("Fraud_Injection_Rules", {})
        if not isinstance(inj, dict):
            return ["Fraud_Injection_Rules must be an object"]

        for f in ("strategy", "fraud_user_ratio",
                  "max_fraud_txns_per_user", "contaminate_normal_users"):
            if f not in inj:
                errors.append(f"Fraud_Injection_Rules missing: '{f}'")

        if "strategy" in inj and inj["strategy"] not in (
            "dedicated_fraudsters", "mixed"
        ):
            errors.append(
                f"Fraud_Injection_Rules.strategy must be 'dedicated_fraudsters' or 'mixed', "
                f"got: {inj['strategy']!r}"
            )

        return errors

    def _check_sequence_rules(self, bp: Dict) -> List[str]:
        errors = []
        seq = bp.get("Sequence_Rules", {})
        if not isinstance(seq, dict):
            return ["Sequence_Rules must be an object"]

        for f in ("enabled", "max_chain_length", "inter_txn_gap_seconds"):
            if f not in seq:
                errors.append(f"Sequence_Rules missing: '{f}'")

        gap = seq.get("inter_txn_gap_seconds", {})
        if isinstance(gap, dict):
            for sub in ("min", "max"):
                if sub not in gap:
                    errors.append(f"Sequence_Rules.inter_txn_gap_seconds missing: '{sub}'")
                elif not isinstance(gap[sub], (int, float)):
                    errors.append(
                        f"Sequence_Rules.inter_txn_gap_seconds.{sub} must be numeric"
                    )
        return errors

    def _check_quantitative_fields(self, bp: Dict) -> List[str]:
        """Extra cross-field numeric sanity checks."""
        errors = []
        prof = bp.get("Normal_User_Profile", {})
        ta   = prof.get("transaction_amount", {}) if isinstance(prof, dict) else {}

        if isinstance(ta, dict):
            mn   = ta.get("min")
            mx   = ta.get("max")
            mean = ta.get("mean")
            if all(isinstance(x, (int, float)) for x in (mn, mx, mean) if x is not None):
                if mn is not None and mx is not None and mn >= mx:
                    errors.append(
                        f"Normal_User_Profile.transaction_amount: min ({mn}) >= max ({mx})"
                    )
                if mean is not None and mn is not None and mean < mn:
                    errors.append(
                        f"Normal_User_Profile.transaction_amount: mean ({mean}) < min ({mn})"
                    )
                if mean is not None and mx is not None and mean > mx:
                    errors.append(
                        f"Normal_User_Profile.transaction_amount: mean ({mean}) > max ({mx})"
                    )

        return errors

    def _jsonschema_validate(self, bp: Dict) -> List[str]:
        try:
            jsonschema.validate(instance=bp, schema=BLUEPRINT_SCHEMA)
            return []
        except jsonschema.ValidationError as exc:
            return [f"JSON Schema: {exc.message}"]
        except jsonschema.SchemaError as exc:
            logger.error("Internal schema error: %s", exc)
            return []