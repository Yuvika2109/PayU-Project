

import json

# ── Blueprint schema the LLM must return ──────────────────────────────────────

_BLUEPRINT_SCHEMA = {
    "amount_min":           "float  — lowest fraud transaction amount in USD",
    "amount_max":           "float  — highest fraud transaction amount in USD",
    "amount_distribution":  "uniform | normal | skewed_low | skewed_high",
    "velocity_per_card":    "int    — typical number of transactions per card in the time window",
    "time_window_hours":    "int    — how many hours the burst of fraud lasts",
    "num_unique_cards":     "int    — how many distinct card_ids to generate",
    "shared_bin":           "bool   — do all fraud cards share the same BIN prefix?",
    "bin_prefix":           "string — 6-digit BIN prefix (e.g. '453201')",
    "merchants":            "list[str] — 2-5 merchant names commonly targeted",
    "merchant_categories":  "list[str] — e.g. ['streaming', 'gaming', 'electronics']",
    "countries":            "list[str] — 2-letter ISO codes for fraud origin countries",
    "devices":              "list[str] — device types used: mobile / desktop / tablet",
    "time_clustering":      "burst | spread — are transactions clustered or spread out?",
}

_BLUEPRINT_INSTRUCTION = f"""
Return ONLY a valid JSON object — no explanation, no markdown, no prose.
The object must contain these fields:
{json.dumps(_BLUEPRINT_SCHEMA, indent=2)}
""".strip()


# ── Known scenario hints (optional enrichment) ───────────────────────────────

_SCENARIO_HINTS = {
    "bin attack": (
        "BIN Attack pattern: many different cards sharing the same 6-digit BIN prefix, "
        "very small probe amounts ($0.50–$10), rapid-fire timing within 1–2 hours, "
        "same country/device, 2–3 merchants (streaming, gaming sites)."
    ),
    "account takeover": (
        "Account Takeover pattern: a card suddenly used from a new country and device, "
        "unusually large amounts ($300–$2000), 1–3 stolen cards, transactions within "
        "30–90 minutes, high-value merchants (electronics, travel, gift cards)."
    ),
    "card testing": (
        "Card Testing pattern: many small transactions ($0.50–$5) across different "
        "merchants to check if stolen card numbers are valid, rapid succession, "
        "often from the same device/IP, amounts just above $0."
    ),
    "velocity abuse": (
        "Velocity Abuse pattern: a single card used excessively at one merchant, "
        "moderate amounts ($20–$100), dozens of transactions in a few hours, "
        "same device and country, same or similar merchant."
    ),
}


def _find_hint(scenario_text: str) -> str:
    """Returns a known hint if the scenario matches a known pattern, else empty."""
    lower = scenario_text.lower()
    for key, hint in _SCENARIO_HINTS.items():
        if key in lower:
            return f"\nKnown pattern reference:\n{hint}\n"
    return ""


# ── Public interface ──────────────────────────────────────────────────────────

SUPPORTED_SCENARIOS = list(_SCENARIO_HINTS.keys())


def build_prompt(scenario: str, fraud_count: int) -> str:
    """
    Builds a prompt that asks the LLM to return a fraud behavior BLUEPRINT
    (parameter spec), not actual transaction rows.

    Parameters
    ----------
    scenario    : free-text description of the fraud scenario
    fraud_count : how many fraud rows will be generated (for context)

    Returns
    -------
    str — complete prompt ready for llm_client
    """
    if fraud_count <= 0:
        raise ValueError(f"fraud_count must be positive, got {fraud_count}")

    hint = _find_hint(scenario)

    prompt = f"""
You are a financial fraud analytics expert. A user has described a fraud scenario.
Your job is to return a JSON object describing the STATISTICAL PARAMETERS of that
fraud pattern — NOT actual transaction data.

Fraud scenario described by the user:
\"{scenario}\"
{hint}
Context: the system will use your blueprint to programmatically generate
{fraud_count} synthetic fraud transactions using Python and NumPy.

{_BLUEPRINT_INSTRUCTION}

Return the blueprint JSON now:
""".strip()

    print(f"[prompt_builder] Built blueprint prompt for: '{scenario[:60]}...', count={fraud_count}")
    return prompt