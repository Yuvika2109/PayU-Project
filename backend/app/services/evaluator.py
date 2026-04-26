"""
Dataset Validation & Metrics Engine
─────────────────────────────────────
Evaluates a list of FraudRules against a pandas DataFrame and
computes per-rule and aggregate metrics.

Supported operators: gt, gte, lt, lte, eq, neq, in, not_in, contains
Each rule contains one or more RuleConditions.
Conditions are ANDed by default; set rule.match_any=True for OR logic.
"""
from __future__ import annotations

import logging
from typing import Optional

import numpy as np
import pandas as pd

from app.models.schemas import (
    DatasetSummary,
    EvaluationMetrics,
    FraudRule,
    OperatorType,
    RuleResult,
    SchemaType,
)
from app.core.schema_detector import get_id_column

logger = logging.getLogger(__name__)

# ─── Condition evaluator ─────────────────────────────────────────────────────

def _apply_condition(df: pd.DataFrame, field: str, operator: OperatorType, value) -> pd.Series:
    """
    Return a boolean Series: True where the condition holds.
    Handles type coercion gracefully (e.g. numeric column stored as object).
    """
    if field not in df.columns:
        logger.debug("Column %r not in dataset; condition returns False for all rows", field)
        return pd.Series(False, index=df.index)

    col = df[field]

    # Try numeric coercion for numeric operators
    numeric_ops = {OperatorType.GT, OperatorType.GTE, OperatorType.LT, OperatorType.LTE}
    if operator in numeric_ops:
        col = pd.to_numeric(col, errors="coerce")
        try:
            val = float(value)
        except (TypeError, ValueError):
            return pd.Series(False, index=df.index)
        if   operator == OperatorType.GT:  return col > val
        elif operator == OperatorType.GTE: return col >= val
        elif operator == OperatorType.LT:  return col < val
        elif operator == OperatorType.LTE: return col <= val

    # String / categorical operators
    col_str = col.astype(str).str.strip()

    if operator == OperatorType.EQ:
        try:
            return pd.to_numeric(col, errors="coerce") == float(value)
        except (TypeError, ValueError):
            return col_str == str(value)

    if operator == OperatorType.NEQ:
        try:
            return pd.to_numeric(col, errors="coerce") != float(value)
        except (TypeError, ValueError):
            return col_str != str(value)

    if operator == OperatorType.IN:
        values = [str(v) for v in (value if isinstance(value, list) else [value])]
        return col_str.isin(values)

    if operator == OperatorType.NOT_IN:
        values = [str(v) for v in (value if isinstance(value, list) else [value])]
        return ~col_str.isin(values)

    if operator == OperatorType.CONTAINS:
        return col_str.str.contains(str(value), case=False, na=False)

    return pd.Series(False, index=df.index)


# ─── Rule evaluator ──────────────────────────────────────────────────────────

def _evaluate_rule(df: pd.DataFrame, rule: FraudRule) -> pd.Series:
    """
    Return a boolean mask: True for rows flagged by this rule.
    Falls back to logic_expression heuristics when no structured conditions exist.
    """
    if rule.conditions:
        masks = [
            _apply_condition(df, c.field, c.operator, c.value)
            for c in rule.conditions
        ]
        combined = masks[0]
        for m in masks[1:]:
            combined = combined | m if rule.match_any else combined & m
        return combined

    # ── Heuristic fallback: parse logic_expression ───────────────────────────
    return _heuristic_eval(df, rule.logic_expression)


def _heuristic_eval(df: pd.DataFrame, expr: str) -> pd.Series:
    """
    Best-effort evaluation of a human-readable logic expression.
    Covers the patterns the LLM commonly emits.
    """
    expr_lc = expr.lower()
    result   = pd.Series(False, index=df.index)

    def _flag(col: str, op, val):
        nonlocal result
        if col in df.columns:
            result = result | _apply_condition(df, col, op, val)

    # velocity
    if "velocity_24h" in expr_lc:
        _flag("velocity_24h", OperatorType.GT, _extract_number(expr_lc, "velocity_24h", 5))
    if "velocity_1h" in expr_lc:
        _flag("velocity_1h",  OperatorType.GT, _extract_number(expr_lc, "velocity_1h",  3))

    # amount
    if "amount_vs_avg_ratio" in expr_lc:
        _flag("amount_vs_avg_ratio", OperatorType.GT, _extract_number(expr_lc, "amount_vs_avg_ratio", 3.0))
    if "transaction_amount" in expr_lc or "purchase_amount" in expr_lc:
        col = "transaction_amount" if "transaction_amount" in df.columns else "purchase_amount_decimal"
        threshold = _extract_number(expr_lc, col, None)
        if threshold is not None:
            op = OperatorType.LT if "<" in expr_lc else OperatorType.GT
            _flag(col, op, threshold)

    # binary flag columns
    for flag_col in [
        "foreign_ip_flag", "new_device_flag", "new_shipping_addr_flag",
        "cross_border_flag", "high_risk_mcc_flag", "is_weekend",
    ]:
        if flag_col in expr_lc:
            _flag(flag_col, OperatorType.EQ, 1)

    # off-hours
    if "hour" in expr_lc and "hour_of_day" in df.columns:
        hour_col = pd.to_numeric(df["hour_of_day"], errors="coerce")
        result = result | ((hour_col >= 0) & (hour_col <= 5))

    # BIN concentration
    if "bin" in expr_lc and "bin_number" in df.columns:
        bin_counts = df["bin_number"].value_counts()
        top_bins   = bin_counts[bin_counts > len(df) * 0.05].index
        result = result | df["bin_number"].isin(top_bins)

    # multi-merchant velocity per user
    if "merchant" in expr_lc and ("multiple" in expr_lc or "count" in expr_lc):
        uid_col = "user_id" if "user_id" in df.columns else "acct_id"
        if uid_col in df.columns and "merchant_id" in df.columns:
            merchant_counts = (
                df.groupby(uid_col)["merchant_id"].nunique().rename("_merchant_count")
            )
            df2 = df.join(merchant_counts, on=uid_col)
            result = result | (df2["_merchant_count"] > 5)

    return result


def _extract_number(text: str, field: str, default):
    """Try to pull the numeric threshold after a field name in the expression."""
    import re
    pattern = rf"{re.escape(field)}\s*[><=!]+\s*([\d.]+)"
    m = re.search(pattern, text.lower())
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            pass
    return default


# ─── Metrics computation ─────────────────────────────────────────────────────

def _compute_rule_metrics(
    df: pd.DataFrame,
    rule: FraudRule,
    id_col: str,
    fraud_col: str = "fraud_label",
) -> RuleResult:
    flagged_mask = _evaluate_rule(df, rule)
    flagged_df   = df[flagged_mask]
    n_flagged    = int(flagged_mask.sum())
    n_total      = len(df)

    # ground-truth columns may not exist in all datasets
    if fraud_col in df.columns:
        fraud_actual   = pd.to_numeric(df[fraud_col], errors="coerce").fillna(0).astype(int)
        fraud_flagged  = pd.to_numeric(flagged_df[fraud_col], errors="coerce").fillna(0).astype(int)
        tp = int((fraud_flagged == 1).sum())
        fp = int((fraud_flagged == 0).sum())
        fn = int(((fraud_actual == 1) & ~flagged_mask).sum())

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall    = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1        = (
            2 * precision * recall / (precision + recall)
            if (precision + recall) > 0 else 0.0
        )
    else:
        tp = fp = fn = 0
        precision = recall = f1 = 0.0

    # sample flagged IDs (up to 10)
    sample_ids: list[str] = []
    if id_col in flagged_df.columns:
        sample_ids = flagged_df[id_col].astype(str).head(10).tolist()

    return RuleResult(
        rule_id=rule.id,
        rule_name=rule.name,
        severity=rule.severity,
        category=rule.category,
        flagged_count=n_flagged,
        flag_rate=round(n_flagged / n_total, 6) if n_total else 0.0,
        true_positive_count=tp,
        false_positive_count=fp,
        precision=round(precision, 4),
        recall=round(recall, 4),
        f1=round(f1, 4),
        logic_expression=rule.logic_expression,
        sample_flagged_ids=sample_ids,
    )


def _dataset_summary(df: pd.DataFrame, schema: SchemaType) -> DatasetSummary:
    fraud_col   = "fraud_label"
    fraud_count = 0
    if fraud_col in df.columns:
        fraud_series = pd.to_numeric(df[fraud_col], errors="coerce").fillna(0)
        fraud_count  = int((fraud_series == 1).sum())

    missing = {c: int(df[c].isna().sum()) for c in df.columns if df[c].isna().sum() > 0}

    return DatasetSummary(
        total_rows=len(df),
        fraud_rows=fraud_count,
        non_fraud_rows=len(df) - fraud_count,
        fraud_rate=round(fraud_count / len(df), 6) if len(df) else 0.0,
        schema_type=schema,
        columns=list(df.columns),
        missing_value_counts=missing,
    )


# ─── Public API ──────────────────────────────────────────────────────────────

def evaluate_dataset(
    df: pd.DataFrame,
    rules: list[FraudRule],
    schema: SchemaType,
    selected_rule_ids: Optional[list[str]] = None,
    max_sample_rows: int = 20,
) -> EvaluationMetrics:
    """
    Evaluate selected rules against df and return aggregated metrics.
    """
    active_rules = rules
    if selected_rule_ids is not None:
        id_set       = set(selected_rule_ids)
        active_rules = [r for r in rules if r.id in id_set]

    if not active_rules:
        raise ValueError("No rules selected for evaluation.")

    id_col    = get_id_column(schema)
    fraud_col = "fraud_label"

    # per-rule metrics
    rule_results: list[RuleResult] = []
    union_mask = pd.Series(False, index=df.index)

    for rule in active_rules:
        mask = _evaluate_rule(df, rule)
        union_mask = union_mask | mask
        result = _compute_rule_metrics(df, rule, id_col, fraud_col)
        rule_results.append(result)

    # aggregate metrics
    flagged_df      = df[union_mask]
    total_flagged   = int(union_mask.sum())
    overall_flag_rate = round(total_flagged / len(df), 6) if len(df) else 0.0

    if fraud_col in df.columns:
        fraud_actual = pd.to_numeric(df[fraud_col], errors="coerce").fillna(0).astype(int)
        fraud_flagged = pd.to_numeric(flagged_df[fraud_col], errors="coerce").fillna(0).astype(int)
        agg_tp = int((fraud_flagged == 1).sum())
        agg_fp = int((fraud_flagged == 0).sum())
        agg_fn = int(((fraud_actual == 1) & ~union_mask).sum())
        fraud_captured = agg_tp
        agg_prec = agg_tp / (agg_tp + agg_fp) if (agg_tp + agg_fp) > 0 else 0.0
        agg_rec  = agg_tp / (agg_tp + agg_fn) if (agg_tp + agg_fn) > 0 else 0.0
        agg_f1   = (
            2 * agg_prec * agg_rec / (agg_prec + agg_rec)
            if (agg_prec + agg_rec) > 0 else 0.0
        )
    else:
        fraud_captured = agg_prec = agg_rec = agg_f1 = 0.0

    # sample flagged rows (convert NaN → None for JSON serialisation)
    sample_rows = (
        flagged_df.head(max_sample_rows)
        .replace({np.nan: None})
        .to_dict(orient="records")
    )

    return EvaluationMetrics(
        total_records=len(df),
        total_flagged=total_flagged,
        overall_flag_rate=overall_flag_rate,
        fraud_captured=int(fraud_captured),
        overall_precision=round(float(agg_prec), 4),
        overall_recall=round(float(agg_rec), 4),
        overall_f1=round(float(agg_f1), 4),
        rule_results=rule_results,
        dataset_summary=_dataset_summary(df, schema),
        flagged_sample=sample_rows,
    )
