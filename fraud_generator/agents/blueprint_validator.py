"""
agents/blueprint_validator.py  (v5 — EMVCo 3DS)
Validates a v2/v3 Fraud Blueprint with EMVCo 3DS column awareness.

v5 changes vs v4:
  - _check_anomaly_signals() validates that Anomaly_Signals use EMVCo column names.
  - _check_column_definitions() verifies Column_Definitions references EMVCo element IDs.
  - Amount floor/range checks preserved from v4.
  - currency_weights validated to use ISO 4217 alpha-3 codes.
  - New 3DS-specific pattern params validated (challenge_bypass_prob, cross_border_prob, etc.).
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

from schemas.blueprint_schema import (
    BLUEPRINT_SCHEMA,
    QUANTITATIVE_CHECKS,
    REQUIRED_TOP_LEVEL_KEYS,
)
from schemas.emvco_3ds_schema import CORE_COLUMNS, COLUMN_NAMES
from utils.logger import get_logger

logger = get_logger("agents.blueprint_validator")

try:
    import jsonschema
    _HAS_JSONSCHEMA = True
except ImportError:
    _HAS_JSONSCHEMA = False
    logger.warning("jsonschema not installed – using lightweight validation only")

# Valid ISO 4217 alpha-3 currency codes accepted in currency_weights
_VALID_CURRENCY_CODES = {
    "USD", "EUR", "GBP", "JPY", "AUD", "CAD", "CHF",
    "SGD", "INR", "BRL", "MXN", "CNY", "HKD", "NZD",
    "SEK", "NOK", "DKK", "ZAR", "AED", "SAR",
}

# EMVCo 3DS column names that MUST appear in Anomaly_Signals thresholds
# (at least one per fraud pattern)
_REQUIRED_ANOMALY_COLS = {"velocity_1h", "purchase_amount", "trans_status"}

# Valid 3DS-specific pattern param names (floats 0–1)
_3DS_PROB_PARAMS = {
    "challenge_bypass_prob", "cross_border_prob",
    "aci_new_acct_prob", "high_risk_mcc_prob", "gift_card_prob",
}


class BlueprintValidatorAgent:
    """
    Validate a v2/v3 blueprint dict with EMVCo 3DS awareness.
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
        errors.extend(self._check_anomaly_signals(blueprint))
        errors.extend(self._check_column_definitions(blueprint))

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

        # transaction_amount sub-fields
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
            mn = ta.get("min")
            if isinstance(mn, (int, float)) and mn < 0.01:
                errors.append(
                    f"Normal_User_Profile.transaction_amount.min must be >= 0.01, got: {mn}"
                )

        # merchant_category_weights
        mcw = prof.get("merchant_category_weights", {})
        if isinstance(mcw, dict):
            non_numeric = [k for k, v in mcw.items() if not isinstance(v, (int, float))]
            if non_numeric:
                errors.append(
                    f"Normal_User_Profile.merchant_category_weights non-numeric keys: {non_numeric}"
                )

        # currency_weights — ISO 4217 alpha-3 check (warn, not error, for unknown codes)
        cw = prof.get("currency_weights", {})
        if not isinstance(cw, dict) or len(cw) == 0:
            errors.append(
                'Normal_User_Profile.currency_weights must be a non-empty dict '
                'e.g. {"USD": 0.85, "EUR": 0.10, "GBP": 0.05}'
            )
        elif isinstance(cw, dict):
            non_numeric_cw = [k for k, v in cw.items() if not isinstance(v, (int, float))]
            if non_numeric_cw:
                errors.append(
                    f"Normal_User_Profile.currency_weights values must be numeric. "
                    f"Non-numeric keys: {non_numeric_cw}"
                )
            # Warn about unrecognised currency codes (soft check — don't block)
            unknown_codes = [k for k in cw if k.upper() not in _VALID_CURRENCY_CODES]
            if unknown_codes:
                logger.warning(
                    "currency_weights contains non-standard ISO 4217 codes: %s "
                    "(these may not map to a valid purchase_currency numeric code)",
                    unknown_codes,
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
                # Standard params must be numeric/boolean/list-of-numbers
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
                        f"{bad_params}. All params must be numbers, booleans, or arrays of numbers."
                    )

                # Amount floor and mean-range checks
                amn   = params.get("amount_min")
                amx   = params.get("amount_max")
                amean = params.get("amount_mean")

                if isinstance(amn, (int, float)) and amn < 0.01:
                    errors.append(
                        f"Fraud_Patterns[{i}].params.amount_min must be >= 0.01, got: {amn}"
                    )
                if isinstance(amx, (int, float)) and isinstance(amn, (int, float)) and amx <= amn:
                    errors.append(
                        f"Fraud_Patterns[{i}].params.amount_max ({amx}) must be > amount_min ({amn})"
                    )
                if (isinstance(amean, (int, float)) and isinstance(amn, (int, float))
                        and isinstance(amx, (int, float))):
                    if amean < amn:
                        errors.append(
                            f"Fraud_Patterns[{i}].params.amount_mean ({amean}) must be >= amount_min ({amn})"
                        )
                    if amean > amx:
                        errors.append(
                            f"Fraud_Patterns[{i}].params.amount_mean ({amean}) must be <= amount_max ({amx})"
                        )

                # Burst range
                bmn = params.get("burst_min_txns")
                bmx = params.get("burst_max_txns")
                if isinstance(bmn, (int, float)) and isinstance(bmx, (int, float)):
                    if bmn < 1:
                        errors.append(
                            f"Fraud_Patterns[{i}].params.burst_min_txns ({bmn}) must be >= 1"
                        )
                    if bmn > bmx:
                        errors.append(
                            f"Fraud_Patterns[{i}].params.burst_min_txns ({bmn}) must be "
                            f"<= burst_max_txns ({bmx})"
                        )

                # EMVCo 3DS-specific probability params — must be 0-1 floats
                for prob_key in _3DS_PROB_PARAMS:
                    val = params.get(prob_key)
                    if val is not None:
                        if not isinstance(val, (int, float)):
                            errors.append(
                                f"Fraud_Patterns[{i}].params.{prob_key} must be numeric, got: {val!r}"
                            )
                        elif not 0 <= float(val) <= 1:
                            errors.append(
                                f"Fraud_Patterns[{i}].params.{prob_key} must be in [0,1], got: {val}"
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
        """Cross-field numeric sanity checks."""
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

    def _check_anomaly_signals(self, bp: Dict) -> List[str]:
        """
        Verify Anomaly_Signals block:
          1. Exists and is non-empty.
          2. Each entry maps to a dict of column thresholds.
          3. At least one signal per pattern uses EMVCo 3DS column names.
          4. Warns (not errors) if a signal column is not in COLUMN_NAMES.
        """
        errors = []
        signals = bp.get("Anomaly_Signals", {})
        if not isinstance(signals, dict) or len(signals) == 0:
            errors.append(
                "Anomaly_Signals must be a non-empty object mapping pattern names "
                "to EMVCo 3DS column thresholds."
            )
            return errors

        patterns = bp.get("Fraud_Patterns", [])
        pattern_names = {p.get("pattern_name", "") for p in patterns if isinstance(p, dict)}

        for pattern_name, thresholds in signals.items():
            if not isinstance(thresholds, dict) or len(thresholds) == 0:
                errors.append(
                    f"Anomaly_Signals['{pattern_name}'] must be a non-empty dict of column thresholds"
                )
                continue

            # Check at least one threshold uses a required EMVCo column
            cols_used = set(thresholds.keys())
            if not cols_used & _REQUIRED_ANOMALY_COLS:
                errors.append(
                    f"Anomaly_Signals['{pattern_name}'] must include at least one of "
                    f"{sorted(_REQUIRED_ANOMALY_COLS)} (EMVCo 3DS columns). "
                    f"Found: {sorted(cols_used)}"
                )

            # Soft-warn on unrecognised column names
            unknown_cols = cols_used - set(COLUMN_NAMES)
            if unknown_cols:
                logger.warning(
                    "Anomaly_Signals['%s'] references columns not in EMVCo 3DS schema: %s",
                    pattern_name, sorted(unknown_cols)
                )

        return errors

    def _check_column_definitions(self, bp: Dict) -> List[str]:
        """
        Verify Column_Definitions exists and references at least a few
        EMVCo 3DS element IDs.
        This is a soft check — missing Column_Definitions doesn't block
        generation (the engine has a hardcoded fallback), but warns loudly.
        """
        col_defs = bp.get("Column_Definitions")
        if col_defs is None:
            logger.warning(
                "Column_Definitions missing from blueprint. "
                "The engine will use the default EMVCo 3DS schema. "
                "Add Column_Definitions for full spec compliance."
            )
            return []

        if not isinstance(col_defs, dict) or len(col_defs) == 0:
            return ["Column_Definitions must be a non-empty object when present"]

        # Check at least a few core columns are defined
        expected_sample = {"purchase_amount", "trans_status", "eci", "merchant_id"}
        missing_core = expected_sample - set(col_defs.keys())
        if len(missing_core) == len(expected_sample):
            return [
                f"Column_Definitions appears unrelated to EMVCo 3DS spec. "
                f"Expected at least one of: {sorted(expected_sample)}"
            ]

        return []

    def _jsonschema_validate(self, bp: Dict) -> List[str]:
        try:
            jsonschema.validate(instance=bp, schema=BLUEPRINT_SCHEMA)
            return []
        except jsonschema.ValidationError as exc:
            return [f"JSON Schema: {exc.message}"]
        except jsonschema.SchemaError as exc:
            logger.error("Internal schema error: %s", exc)
            return []