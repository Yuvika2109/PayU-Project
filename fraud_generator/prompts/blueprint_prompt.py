"""
prompts/blueprint_prompt.py  (v7 — lean, small-LLM optimised)

Produces the same blueprint structure as v6 but with a drastically reduced
prompt size (~3,500–4,500 chars vs ~18,000 chars in v6).

Key changes vs v6:
  - Column reference table removed from main prompt (engine handles column
    generation internally; LLM only needs to set numeric params).
  - REASONING_FRAMEWORK collapsed to a single scenario-lookup table.
  - _SKELETON stripped to the minimum keys the DatasetEngine actually reads.
  - Column_Definitions and Validation_Constraints removed from blueprint
    prompt entirely — they are static schema constants, not LLM outputs.
  - BLUEPRINT_FIX_PROMPT_TEMPLATE similarly trimmed.
"""

from __future__ import annotations


# ── Per-scenario parameter hints (replaces the verbose reasoning framework) ───
# LLM only needs to look up its scenario and copy the right numbers.

_SCENARIO_HINTS = """\
SCENARIO QUICK-REFERENCE (use the row matching your fraud type):
Scenario             | amt_min | amt_max | amt_mean | velocity_1h | foreign_ip | seq_type
---------------------|---------|---------|----------|-------------|------------|----------
BIN Attack           | 0.01    | 2.00    | 0.50     | 30          | 0.7        | burst
Card Testing         | 0.01    | 5.00    | 1.00     | 25          | 0.6        | burst
Account Takeover     | 200     | 5000    | 800      | 8           | 0.8        | chain
Money Laundering     | 100     | 9999    | 2000     | 3           | 0.5        | network
Phishing             | 50      | 2000    | 400      | 5           | 0.6        | chain
Friendly Fraud       | 50      | 500     | 150      | 2           | 0.1        | independent
Synthetic Identity   | 500     | 5000    | 1200     | 4           | 0.3        | chain
Refund Abuse         | 30      | 400     | 120      | 2           | 0.1        | independent
Triangulation Fraud  | 50      | 1500    | 300      | 6           | 0.4        | burst
Corporate Card Abuse | 300     | 8000    | 1200     | 3           | 0.5        | chain

MCC by scenario:
BIN Attack/Card Testing → 5999,5045,7372
Account Takeover        → 5732,5311,5094,7011,4511
Money Laundering        → 6051,4829,6011
Phishing                → 4829,6051,5999
Synthetic Identity      → 5311,5732,5651
Friendly/Refund         → 5812,5999,5651
Triangulation           → 5999,5045,5732
Corporate               → 7011,4511,5812

Normal user amounts: retail mean=$85, travel mean=$450, corporate mean=$500
purchase_amount in dataset = decimal × 100 (minor units). e.g. $0.50 → 50, $85 → 8500.
"""


# ── Minimal skeleton — only keys DatasetEngine actually reads ─────────────────

_SKELETON = """\
{
  "Fraud_Scenario_Name": "<string>",
  "Fraud_Type": "<string>",
  "Dataset_Specifications": {
    "total_rows": <int>,
    "fraud_ratio": <float>,
    "output_format": "<csv|json|parquet>",
    "date_range_start": "<YYYY-MM-DD>",
    "date_range_end": "<YYYY-MM-DD>",
    "num_users": <int>,
    "num_merchants": <int>
  },
  "Normal_User_Profile": {
    "transaction_amount": {
      "distribution": "lognormal",
      "min": <float >=0.01>, "max": <float>, "mean": <float>, "std": <float>
    },
    "transactions_per_day": {"mean": <float>, "std": <float>, "max": <int>},
    "active_hours": {"peak_start": <0-23>, "peak_end": <0-23>, "off_peak_weight": <float>},
    "active_days": {"weekday_weight": <float>, "weekend_weight": <float>},
    "merchant_category_weights": {"<Category>": <float>},
    "currency_weights": {"USD": <float>},
    "location_change_prob": <float>,
    "device_change_prob": <float>
  },
  "Fraud_Patterns": [
    {
      "pattern_name": "<string>",
      "weight": <float>,
      "sequence_type": "<burst|chain|network|independent>",
      "params": {
        "amount_min": <float >=0.01>,
        "amount_max": <float>,
        "amount_mean": <float>,
        "amount_std": <float>,
        "burst_min_txns": <int>,
        "burst_max_txns": <int>,
        "burst_window_mins": <int>,
        "num_merchants": <int>,
        "preferred_hours": [<int>, <int>],
        "same_device_prob": <float>,
        "same_location_prob": <float>,
        "foreign_ip_prob": <float>,
        "velocity_txns_per_hour": <int>,
        "challenge_bypass_prob": <float>,
        "cross_border_prob": <float>,
        "aci_new_acct_prob": <float>,
        "high_risk_mcc_prob": <float>
      }
    }
  ],
  "Fraud_Injection_Rules": {
    "fraud_user_ratio": <float>,
    "max_fraud_txns_per_user": <int>,
    "contaminate_normal_users": <bool>,
    "contamination_prob": <float>
  },
  "Sequence_Rules": {
    "inter_txn_gap_seconds": {"min": <int>, "max": <int>}
  },
  "Anomaly_Signals": {
    "<pattern_name>": {
      "velocity_1h": "> <int>",
      "purchase_amount": "< <int> (minor units)",
      "acct_info_open_acct_ind": "== <01|02|03|04>",
      "trans_status": "in [Y, A]"
    }
  }
}"""


def build_blueprint_prompt(
    scenario_name: str,
    description: str,
    fraud_type: str,
    total_rows: int,
    fraud_ratio: float,
    output_format: str,
    user_context: str = "",
) -> str:
    fraud_count  = int(total_rows * fraud_ratio)
    normal_count = total_rows - fraud_count

    user_block = ""
    if user_context and user_context.strip():
        user_block = f'\nUSER REQUEST: "{user_context.strip()}"\n'

    return f"""You are a fraud-data architect. Output a JSON blueprint for a 3DS synthetic dataset generator.

SCENARIO: {scenario_name} | TYPE: {fraud_type}
ROWS: {total_rows} total ({fraud_count} fraud / {normal_count} normal) | FORMAT: {output_format}{user_block}

{_SCENARIO_HINTS}
Fill this skeleton with realistic numbers for "{scenario_name}".
Rules:
- Fraud_Patterns MUST be a JSON array (list) with at least 2 pattern objects.
- All params fields must be numbers, booleans, or arrays of integers — no strings.
- Normal_User_Profile amounts are DECIMAL (engine converts to minor units internally).
- amount_min >= 0.01, amount_mean must be between amount_min and amount_max.
- date_range_start/end should span 1-2 years ending near today.
- num_users >= total_rows / 10, num_merchants >= 50.
- Sequence_Rules.inter_txn_gap_seconds: burst → min=1 max=60; chain → min=30 max=600; network → min=3600 max=86400.

{_SKELETON}

Respond with ONLY the JSON object. No markdown fences, no comments, no prose.
"""


# ── Fix prompt (also trimmed) ─────────────────────────────────────────────────

BLUEPRINT_FIX_PROMPT_TEMPLATE = """\
This fraud blueprint JSON failed validation. Fix every error listed below.

ERRORS:
{errors}

RULES (apply to fix):
- Fraud_Patterns must be a JSON ARRAY (list), not a dict/object.
- Each pattern needs: pattern_name (str), weight (float), sequence_type (str), params (object).
- All params values must be numbers, booleans, or integer arrays — no strings.
- amount_min >= 0.01, amount_mean between amount_min and amount_max.
- Anomaly_Signals keys must match pattern_name values.

ORIGINAL:
{blueprint_json}

Return ONLY the corrected JSON. No markdown, no prose.
"""