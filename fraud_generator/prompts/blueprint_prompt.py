"""
prompts/blueprint_prompt.py  (v2)
Forces the LLM to produce machine-readable, quantitative blueprints.
"""

import json


def build_blueprint_prompt(
    scenario_name: str,
    description: str,
    fraud_type: str,
    total_rows: int,
    fraud_ratio: float,
    output_format: str,
) -> str:
    fraud_count  = int(total_rows * fraud_ratio)
    normal_count = total_rows - fraud_count

    # Provide a complete worked example so the LLM knows exactly what shape
    # each field must take.  Using BIN Attack as the canonical example.
    EXAMPLE = {
        "Fraud_Scenario_Name": "BIN Attack",
        "Description": "Attacker tests BIN ranges with micro-transactions to find valid cards.",
        "Fraud_Type": "Card-Not-Present Fraud",
        "Dataset_Specifications": {
            "total_rows": 10000,
            "fraud_ratio": 0.05,
            "output_format": "csv",
            "date_range_start": "2023-01-01",
            "date_range_end": "2023-12-31",
            "num_users": 800,
            "num_merchants": 120
        },
        "Normal_User_Profile": {
            "transaction_amount": {
                "distribution": "lognormal",
                "min": 5.0,
                "max": 3000.0,
                "mean": 85.0,
                "std": 120.0
            },
            "transactions_per_day": {"mean": 1.8, "std": 1.2, "max": 12},
            "active_hours": {"peak_start": 9, "peak_end": 21, "off_peak_weight": 0.05},
            "active_days": {"weekday_weight": 0.75, "weekend_weight": 0.25},
            "merchant_category_weights": {
                "Grocery": 0.30, "Retail": 0.25, "Restaurant": 0.20,
                "Gas": 0.10, "Travel": 0.08, "Entertainment": 0.07
            },
            "currency_weights": {"USD": 0.85, "EUR": 0.10, "GBP": 0.05},
            "location_change_prob": 0.05,
            "device_change_prob": 0.02
        },
        "Fraud_Patterns": [
            {
                "pattern_name": "Micro-transaction BIN Probe",
                "description": "Attacker fires many $0.01–$2.00 charges against the same BIN in a tight burst.",
                "weight": 0.6,
                "sequence_type": "burst",
                "params": {
                    "amount_min": 0.01,
                    "amount_max": 2.00,
                    "amount_mean": 0.50,
                    "amount_std": 0.40,
                    "burst_min_txns": 15,
                    "burst_max_txns": 80,
                    "burst_window_mins": 10,
                    "num_merchants": 1,
                    "preferred_hours": [1, 2, 3, 4],
                    "preferred_days": [5, 6],
                    "same_device_prob": 0.95,
                    "same_location_prob": 0.99,
                    "foreign_ip_prob": 0.90,
                    "round_amount_prob": 0.05,
                    "velocity_txns_per_hour": 40.0
                }
            },
            {
                "pattern_name": "Graduated BIN Test",
                "description": "Small escalating amounts to validate card limits before large purchase.",
                "weight": 0.4,
                "sequence_type": "chain",
                "params": {
                    "amount_min": 1.00,
                    "amount_max": 50.00,
                    "amount_mean": 15.0,
                    "amount_std": 12.0,
                    "burst_min_txns": 3,
                    "burst_max_txns": 8,
                    "burst_window_mins": 30,
                    "num_merchants": 3,
                    "preferred_hours": [0, 1, 2, 3],
                    "preferred_days": [5, 6],
                    "same_device_prob": 0.80,
                    "same_location_prob": 0.70,
                    "foreign_ip_prob": 0.75,
                    "round_amount_prob": 0.30,
                    "velocity_txns_per_hour": 10.0
                }
            }
        ],
        "Fraud_Injection_Rules": {
            "strategy": "dedicated_fraudsters",
            "fraud_user_ratio": 0.03,
            "max_fraud_txns_per_user": 120,
            "contaminate_normal_users": False,
            "contamination_prob": 0.0
        },
        "Sequence_Rules": {
            "enabled": True,
            "max_chain_length": 80,
            "inter_txn_gap_seconds": {"min": 5, "max": 120},
            "reuse_card_in_chain": True,
            "reuse_merchant_in_chain": True
        },
        "Anomaly_Signals": {
            "Micro-transaction BIN Probe": {
                "transaction_amount": "< 2.00 (extremely low)",
                "velocity_per_hour": "> 30 transactions",
                "unique_cards_per_ip": "> 20",
                "foreign_ip_flag": "= 1",
                "hour_of_day": "0–4 (off-hours)"
            },
            "Graduated BIN Test": {
                "transaction_amount": "1–50, escalating sequence",
                "merchant_repeat": "same merchant 3–8x",
                "foreign_ip_flag": "= 1"
            }
        },
        "Column_Definitions": {
            "transaction_id": {"type": "uuid"},
            "timestamp": {"type": "datetime", "range": ["2023-01-01", "2023-12-31"]},
            "user_id": {"type": "string", "cardinality": 800},
            "card_number": {"type": "string", "format": "16-digit"},
            "bin_number": {"type": "string", "format": "first-6-digits-of-card"},
            "merchant_id": {"type": "string", "cardinality": 120},
            "merchant_category": {"type": "categorical",
                                   "values": ["Grocery", "Retail", "Restaurant", "Gas",
                                              "Travel", "Entertainment"]},
            "transaction_amount": {"type": "float", "min": 0.01, "max": 3000.0},
            "currency": {"type": "categorical", "values": ["USD", "EUR", "GBP"]},
            "location": {"type": "string"},
            "device_id": {"type": "string"},
            "ip_address": {"type": "ipv4"},
            "foreign_ip_flag": {"type": "integer", "values": [0, 1]},
            "fraud_label": {"type": "integer", "values": [0, 1]}
        },
        "Validation_Constraints": {
            "transaction_amount": {"min": 0.01, "max": 50000.0},
            "fraud_ratio_actual": {"min": 0.01, "max": 0.99},
            "required_columns": [
                "transaction_id", "timestamp", "user_id", "card_number",
                "bin_number", "merchant_id", "merchant_category",
                "transaction_amount", "currency", "location",
                "device_id", "ip_address", "fraud_label"
            ]
        }
    }

    example_json = json.dumps(EXAMPLE, indent=2)

    return f"""You are a senior fraud-data architect specialising in synthetic dataset design.

## TASK
Produce a machine-readable JSON fraud blueprint for a synthetic dataset generator.
Every field that influences data generation MUST contain numeric or boolean values.
String descriptions are allowed ALONGSIDE numeric fields but never INSTEAD of them.

## TARGET SCENARIO
- Fraud Scenario  : {scenario_name}
- Description     : {description}
- Fraud Type      : {fraud_type}
- Total Rows      : {total_rows:,}
- Fraud Ratio     : {fraud_ratio:.1%}  ({fraud_count:,} fraud / {normal_count:,} normal)
- Output Format   : {output_format}

## COMPLETE WORKED EXAMPLE (BIN Attack — study this structure carefully)
{example_json}

## YOUR TASK
Generate a blueprint for "{scenario_name}" following EXACTLY the same JSON structure.

CRITICAL RULES:
1. Every field in Fraud_Patterns.params MUST be a number, integer, boolean, or array of integers.
   No strings like "multiple transactions" — use numbers like burst_min_txns=5, burst_window_mins=15.

2. Normal_User_Profile.transaction_amount MUST have: distribution, min, max, mean, std
   (all numeric). Choose values realistic for legitimate {fraud_type} victims.

3. Fraud_Patterns MUST have at least 2 patterns, each with a different sequence_type
   ("burst", "chain", "network", or "independent") matching how {scenario_name} actually works.

4. Fraud_Injection_Rules.strategy must be "dedicated_fraudsters" if fraudsters are
   separate identities, or "mixed" if they hijack existing accounts.

5. Anomaly_Signals must map each pattern_name to measurable column deviations
   (specific column names + threshold values, not prose descriptions).

6. Dataset_Specifications must include:
   - date_range_start / date_range_end (ISO dates covering ~1–2 years)
   - num_users: realistic pool size for {total_rows:,} transactions
   - num_merchants: realistic merchant pool for the scenario

7. Normal_User_Profile.merchant_category_weights must use realistic category names
   for the scenario context, with weights that sum to 1.0.

8. Sequence_Rules.inter_txn_gap_seconds must have min/max values in seconds
   that make sense for burst/chain patterns in {scenario_name}.

Respond with ONLY the JSON object — no markdown fences, no prose, no comments.
"""


BLUEPRINT_FIX_PROMPT_TEMPLATE = """The following fraud blueprint JSON failed validation.

## VALIDATION ERRORS
{errors}

## ORIGINAL BLUEPRINT
{blueprint_json}

Fix every validation error listed above.
Remember: ALL Fraud_Patterns.params fields must be numbers/integers/booleans/arrays-of-integers.
ALL Normal_User_Profile.transaction_amount fields (min, max, mean, std) must be numbers.
Return ONLY the corrected complete JSON object — no markdown, no prose.
"""