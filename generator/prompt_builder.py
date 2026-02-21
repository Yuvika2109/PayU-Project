def build_prompt(scenario: str):

    if scenario == "BIN_ATTACK":
        scenario_description = """
Simulate a BIN attack:
- Small repeated amounts
- Same card_bin across transactions
- Burst timing
- Shared IP cluster
"""
    elif scenario == "ACCOUNT_TAKEOVER":
        scenario_description = """
Simulate an Account Takeover:
- Sudden location change
- New device
- Large unusual transaction
- Possible password reset event
"""
    else:
        raise ValueError("Unsupported scenario")

    return f"""
You are a fraud behavior modeling system.

Generate a fraud blueprint in strict JSON format.

Scenario Description:
{scenario_description}

Return JSON with:
- scenario
- fraud_characteristics
- statistical_properties

Return ONLY valid JSON.
"""