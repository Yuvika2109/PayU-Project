import json


# ── Shared schema block ───────────────────────────────────────────────────────
# This is injected into every prompt so the LLM knows the exact output format.

_SCHEMA_EXAMPLE = {
    "transaction_id": "uuid-string",
    "card_id":        "CARD-XXXX-XXXX-XXXX",
    "bin":            "6-digit string (first 6 of card_id)",
    "amount":         "float (e.g. 9.99)",
    "merchant":       "string (e.g. Amazon)",
    "country":        "2-letter ISO code (e.g. IN)",
    "device":         "mobile | desktop | tablet",
    "timestamp":      "ISO 8601 string (e.g. 2024-03-15T14:22:00)",
    "is_fraud":       True,
}

_SCHEMA_INSTRUCTION = f"""
Return ONLY a valid JSON array. No explanation, no markdown, no prose — just the array.
Each element must follow this exact schema:
{json.dumps(_SCHEMA_EXAMPLE, indent=2)}
""".strip()


# ── BIN Attack scenario ───────────────────────────────────────────────────────

def _build_bin_attack_prompt(count: int) -> str:
    """
    BIN Attack pattern:
    - Many different cards sharing the same BIN (first 4 digits)
    - Small probe amounts (typically $1–$10) to test card validity
    - Rapid-fire timing — many transactions within minutes
    - Often from the same country/device, different card numbers
    """
    return f"""
You are a financial fraud data generator. Generate {count} synthetic fraudulent 
payment transactions that simulate a BIN Attack.

A BIN Attack pattern looks like this:
- Many different card numbers that all share the SAME first 4 digits (the BIN)
- Transaction amounts are very small — between $0.50 and $10.00 — because attackers 
  probe with micro-amounts to check if a card is live
- All transactions happen within a short time window (within 1–2 hours)
- Timestamps should be clustered tightly, e.g. 2024-03-15T02:00:00 to 2024-03-15T03:45:00
- Typically same country and device type across most transactions
- Use 2–3 different merchants (the attacker tries a few different sites)

{_SCHEMA_INSTRUCTION}

Generate exactly {count} transactions now:
""".strip()


# ── Account Takeover scenario ─────────────────────────────────────────────────

def _build_account_takeover_prompt(count: int) -> str:
    """
    Account Takeover pattern:
    - A single card_id suddenly appears from a NEW country or device
    - Transaction amount is unusually large compared to typical spend
    - Often a single high-value transaction or a few in quick succession
    - New device type not seen before on this card
    """
    return f"""
You are a financial fraud data generator. Generate {count} synthetic fraudulent 
payment transactions that simulate an Account Takeover (ATO).

An Account Takeover pattern looks like this:
- A card that was previously used normally is now suddenly used from a DIFFERENT 
  country (e.g. card normally used in IN, now appears in RU or NG)
- The device changes too — the cardholder used mobile, the attacker uses desktop
- Transaction amounts are unusually HIGH — between $300 and $2000 — because the 
  attacker wants to extract value quickly
- Timestamps are bunched in a short window (within 30–90 minutes) as the attacker 
  acts before the account is locked
- Only 1–3 unique card IDs (attacker has access to a small number of stolen accounts)
- Use high-value merchants: electronics, travel, gift cards

{_SCHEMA_INSTRUCTION}

Generate exactly {count} transactions now:
""".strip()


# ── Public interface ──────────────────────────────────────────────────────────

# Registry maps scenario names to their builder functions
_SCENARIO_BUILDERS = {
    "BIN Attack":        _build_bin_attack_prompt,
    "Account Takeover":  _build_account_takeover_prompt,
}

SUPPORTED_SCENARIOS = list(_SCENARIO_BUILDERS.keys())


def build_prompt(scenario: str, fraud_count: int) -> str:
    """
    Returns the complete LLM prompt for the given scenario and count.

    Parameters
    ----------
    scenario    : one of SUPPORTED_SCENARIOS
    fraud_count : number of fraud transactions the LLM should generate

    Returns
    -------
    str — ready to send to llm_client.generate_fraud_transactions()
    """
    if scenario not in _SCENARIO_BUILDERS:
        raise ValueError(
            f"Unknown scenario: '{scenario}'. "
            f"Supported scenarios: {SUPPORTED_SCENARIOS}"
        )

    if fraud_count <= 0:
        raise ValueError(f"fraud_count must be positive, got {fraud_count}")

    prompt = _SCENARIO_BUILDERS[scenario](fraud_count)
    print(f"[prompt_builder] Built prompt for scenario='{scenario}', count={fraud_count}")
    return prompt