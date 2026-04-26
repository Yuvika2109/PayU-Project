"""
Schema detection for uploaded fraud datasets.

Two supported schemas
─────────────────────
EMVCO      – Classic card-transaction dataset
             Key columns: transaction_id, card_number, bin_number,
                          transaction_amount, merchant_category, foreign_ip_flag …

EMVCO_3DS  – EMVCo 3-D Secure authentication dataset (money-laundering variant)
             Key columns: threeds_server_trans_id, acs_trans_id, acct_number,
                          purchase_amount, velocity_1h, velocity_24h,
                          amount_vs_avg_ratio, cross_border_flag …
"""

from __future__ import annotations
from app.models.schemas import SchemaType

# Columns that unambiguously identify the 3DS schema
_3DS_SIGNATURE = {
    "threeds_server_trans_id",
    "acs_trans_id",
    "acct_number",
    "purchase_amount",
    "velocity_1h",
    "velocity_24h",
    "amount_vs_avg_ratio",
    "cross_border_flag",
    "three_ds_requestor_id",
}

# Columns that unambiguously identify the EMVCo transaction schema
_EMVCO_SIGNATURE = {
    "transaction_id",
    "bin_number",
    "card_number",
    "transaction_amount",
    "foreign_ip_flag",
    "amount_log",
}


def detect_schema(columns: list[str]) -> SchemaType:
    """Return the most likely schema type given the column list."""
    col_set = {c.lower().strip() for c in columns}
    score_3ds   = len(col_set & _3DS_SIGNATURE)
    score_emvco = len(col_set & _EMVCO_SIGNATURE)

    if score_3ds >= 3 and score_3ds >= score_emvco:
        return SchemaType.EMVCO_3DS
    return SchemaType.EMVCO


def get_id_column(schema: SchemaType) -> str:
    if schema == SchemaType.EMVCO_3DS:
        return "threeds_server_trans_id"
    return "transaction_id"


def get_amount_column(schema: SchemaType) -> str:
    if schema == SchemaType.EMVCO_3DS:
        return "purchase_amount_decimal"
    return "transaction_amount"


def get_schema_context(schema: SchemaType, columns: list[str]) -> str:
    """Return a textual description of the schema for the LLM prompt."""
    col_list = ", ".join(columns)
    if schema == SchemaType.EMVCO_3DS:
        return (
            "EMVCo 3-D Secure dataset (card-not-present / authentication logs). "
            f"Available columns: {col_list}. "
            "Key risk features: velocity_1h, velocity_24h, amount_vs_avg_ratio, "
            "new_device_flag, new_shipping_addr_flag, cross_border_flag, "
            "high_risk_mcc_flag, time_since_acct_open_days, trans_status, "
            "acs_challenge_mandated, challenge_completed, acct_info_txn_activity_day."
        )
    return (
        "EMVCo card transaction dataset. "
        f"Available columns: {col_list}. "
        "Key risk features: transaction_amount, bin_number, foreign_ip_flag, "
        "hour_of_day, is_weekend, merchant_category, device_id, ip_address, "
        "amount_log, user_id, merchant_id."
    )
