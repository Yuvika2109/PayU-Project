"""
prompts/blueprint_prompt.py  (v5)
Forces the LLM to produce machine-readable, quantitative blueprints.

v3: replaced 4800-char worked example with compact _SKELETON.
v4: added SCENARIO_RULES keyword table for known scenarios.
v5: replaced keyword table with a REASONING FRAMEWORK that teaches the LLM
    HOW to derive correct amount ranges and patterns for ANY scenario —
    including ones it has never seen before. The framework works by asking
    the LLM to reason from the fraud behaviour description rather than
    matching keywords. This is powered by the richer `description` field
    that ScenarioEnricher (v4) now generates for unknown scenarios.
"""


# ── Reasoning framework (replaces the keyword lookup table) ───────────────────
# Teaches the LLM to derive correct numeric parameters from ANY scenario
# by reasoning about the fraud behaviour, not pattern-matching keywords.

REASONING_FRAMEWORK = """
## HOW TO DERIVE CORRECT PARAMETERS FOR THIS SCENARIO

Before filling in numbers, reason through these four questions:

**Q1 — What does the fraudster want, and how fast do they need to act?**
  - Fast smash-and-grab (account takeover, stolen card) → burst/chain, high amounts, tight window
  - Slow-burn concealment (money laundering, synthetic identity) → network, spread over weeks
  - Probe/test (BIN attack, card testing) → burst of micro-transactions, off-hours

**Q2 — What does a LEGITIMATE transaction look like in this context?**
  Use that to set Normal_User_Profile.transaction_amount.
  Examples: consumer retail = mean $85, corporate travel = mean $450,
  peer-to-peer payment = mean $200, ATM/cash = mean $150.
  min MUST be >= 0.01.

**Q3 — How does FRAUD DIFFER from normal in this scenario?**
  This difference drives the fraud pattern params:
  - Fraud amounts MUCH lower than normal → BIN attack / card testing
  - Fraud amounts MUCH higher than normal → account takeover, corporate card abuse
  - Fraud amounts SIMILAR to normal → friendly fraud, refund fraud, phishing
  - Many txns in short window → burst sequence_type
  - Escalating amounts → chain sequence_type
  - Many accounts, same IP/merchant → network sequence_type

**Q4 — What anomaly signals would a fraud analyst look for?**
  These map directly to Anomaly_Signals. Be specific: column name + threshold value.
  Example: "transaction_amount < 2.00", "velocity > 30/hour", "foreign_ip_flag = 1"

## KNOWN FRAUD AMOUNT REFERENCE (use as anchors for similar scenarios)

| Fraud type | Fraud amount range | Normal user amounts |
|---|---|---|
| BIN attack / card testing | $0.01 – $2.00 (mean $0.50) | mean $85 |
| Account takeover | $200 – $5,000 (mean $800) | mean $85 |
| Corporate card abuse | $300 – $8,000 (mean $1,200) | mean $450 |
| Money laundering / structuring | $1 – $9,999 (stay under reporting limit) | mean $200 |
| Phishing / authorised push payment | $50 – $2,000 (mean $400) | mean $85 |
| Friendly fraud / chargeback | $50 – $500 (mean $150, matches real purchases) | mean $85 |
| Synthetic identity bust-out | $500 – $5,000 escalating over days | mean $85 |
| Refund / return abuse | $30 – $400 (mean $120) | mean $85 |
| Loyalty / rewards fraud | $20 – $200 (point redemption value) | mean $85 |
| Insider fraud / employee theft | $100 – $10,000 (irregular, round numbers) | mean $500 |
| First-party / bust-out fraud | $200 – $3,000 (max credit limit) | mean $150 |

If the scenario in the TARGET SCENARIO section does not match any row above,
derive amounts from the description by reasoning through Q1-Q4 above.
"""


# ── Compact structural skeleton ───────────────────────────────────────────────

_SKELETON = """{
  "Fraud_Scenario_Name": "<string>",
  "Description": "<string>",
  "Fraud_Type": "<string>",
  "Dataset_Specifications": {
    "total_rows": <int>,
    "fraud_ratio": <float 0-1>,
    "output_format": "<csv|json|parquet|excel>",
    "date_range_start": "<YYYY-MM-DD>",
    "date_range_end": "<YYYY-MM-DD>",
    "num_users": <int>,
    "num_merchants": <int>
  },
  "Normal_User_Profile": {
    "transaction_amount": {
      "distribution": "<normal|lognormal|uniform|pareto>",
      "min": <float >= 0.01>, "max": <float>, "mean": <float>, "std": <float>
    },
    "transactions_per_day": {"mean": <float>, "std": <float>, "max": <int>},
    "active_hours": {"peak_start": <0-23>, "peak_end": <0-23>, "off_peak_weight": <float>},
    "active_days": {"weekday_weight": <float>, "weekend_weight": <float>},
    "merchant_category_weights": {"<Category>": <float>, "<Category>": <float>},
    "currency_weights": {"<ISO>": <float>, "<ISO>": <float>},
    "location_change_prob": <float>,
    "device_change_prob": <float>
  },
  "Fraud_Patterns": [
    {
      "pattern_name": "<string>",
      "description": "<string>",
      "weight": <float>,
      "sequence_type": "<burst|chain|network|independent>",
      "params": {
        "amount_min": <float >= 0.01>,
        "amount_max": <float>,
        "amount_mean": <float between amount_min and amount_max>,
        "amount_std": <float>,
        "burst_min_txns": <int>, "burst_max_txns": <int>,
        "burst_window_mins": <int>, "num_merchants": <int>,
        "preferred_hours": [<int>, <int>],
        "preferred_days": [<int>, <int>],
        "same_device_prob": <float>,
        "same_location_prob": <float>,
        "foreign_ip_prob": <float>,
        "round_amount_prob": <float>,
        "velocity_txns_per_hour": <float>
      }
    }
  ],
  "Fraud_Injection_Rules": {
    "strategy": "<dedicated_fraudsters|mixed>",
    "fraud_user_ratio": <float>,
    "max_fraud_txns_per_user": <int>,
    "contaminate_normal_users": <bool>,
    "contamination_prob": <float>
  },
  "Sequence_Rules": {
    "enabled": <bool>,
    "max_chain_length": <int>,
    "inter_txn_gap_seconds": {"min": <int>, "max": <int>},
    "reuse_card_in_chain": <bool>,
    "reuse_merchant_in_chain": <bool>
  },
  "Anomaly_Signals": {
    "<pattern_name>": {
      "<column_name>": "<threshold e.g. < 2.00 or > 30 per hour>",
      "<column_name>": "<threshold>"
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

    user_context_block = ""
    if user_context and user_context.strip():
        user_context_block = (
            "\n## USER'S EXACT REQUEST\n"
            "Read this carefully — it contains specific hints about amounts, locations,\n"
            "merchant types, and behaviour that MUST be reflected in the blueprint:\n"
            f'  \"{user_context.strip()}\"\n'
            "Extract any numeric hints (e.g. \"tiny charges\" -> amount_min=0.01 max=2.00,\n"
            "\"luxury hotels\" -> Travel merchants, \"large transfers\" -> amount_min=50000,\n"
            "\"multiple cities\" -> location_change_prob=0.9, \"over per-diem\" -> amounts>$150).\n"
        )

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
{user_context_block}{REASONING_FRAMEWORK}
## JSON STRUCTURE TO FILL
Generate a blueprint for "{scenario_name}" by replacing every <placeholder> with a
realistic numeric or string value. Follow the exact same key names and structure.
{_SKELETON}

## CRITICAL RULES:
1. Every field in Fraud_Patterns.params MUST be a number, integer, boolean, or array of integers.
   No strings like "multiple transactions" — use numbers like burst_min_txns=5, burst_window_mins=15.

2. Normal_User_Profile.transaction_amount MUST have: distribution, min, max, mean, std
   (all numeric). Choose values realistic for legitimate {fraud_type} victims.
   min MUST be >= 0.01.

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
ALL amount_min values must be >= 0.01 — zero and negative amounts are never valid.
ALL amount_mean values must be between amount_min and amount_max.
Return ONLY the corrected complete JSON object — no markdown, no prose.
"""