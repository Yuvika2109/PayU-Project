"""
prompts/code_generation_prompt.py
Prompt template for the Code Generator Agent.
"""

import json


def build_code_generation_prompt(blueprint: dict, output_path: str) -> str:
    """
    Build the prompt that instructs the LLM to generate a self-contained
    Python script from the fraud blueprint.

    Parameters
    ----------
    blueprint   : The validated fraud blueprint dict.
    output_path : Absolute path where the CSV (or other format) should be saved.

    Returns
    -------
    str: Full prompt string.
    """
    blueprint_json = json.dumps(blueprint, indent=2)
    scenario = blueprint.get("Fraud_Scenario_Name", "Unknown")
    specs = blueprint.get("Dataset_Specifications", {})
    total_rows = specs.get("total_rows", 1000)
    fraud_ratio = specs.get("fraud_ratio", 0.05)
    output_format = specs.get("output_format", "csv").lower()

    return f"""You are a senior Python data-engineering specialist.
Generate a complete, self-contained Python script that creates a synthetic fraud dataset.

## FRAUD BLUEPRINT
{blueprint_json}

## SCRIPT REQUIREMENTS
1. Use ONLY these libraries: pandas, numpy, faker, datetime, random, uuid, os, pathlib
2. Generate exactly {total_rows:,} rows total with {fraud_ratio:.1%} fraud rate
   ({int(total_rows * fraud_ratio):,} fraud rows, {total_rows - int(total_rows * fraud_ratio):,} normal rows).
3. Save the final DataFrame to:
      {output_path}
   Use the appropriate pandas method for the format "{output_format}".
4. Print a concise summary at the end (row count, fraud count, columns).

## CODE STRUCTURE
- A `generate_normal_transactions(n, fake)` function
- A `generate_fraud_transactions(n, fake)` function
- A `main()` function that combines both, shuffles, resets index, saves output
- `if __name__ == "__main__": main()`

## COLUMN REQUIREMENTS (all must be present)
transaction_id, timestamp, user_id, card_number, bin_number, merchant_id,
merchant_category, transaction_amount, currency, location, device_id,
ip_address, fraud_label

## FRAUD BEHAVIOUR for "{scenario}"
- Implement the Fraud_Patterns from the blueprint realistically.
- Apply Behavioral_Rules to distinguish fraud from normal rows.
- Follow Temporal_Patterns for timestamp generation.
- Follow Data_Distribution for numeric field ranges.

## STRICT RULES
- Do NOT use any external API or network calls.
- Do NOT import libraries not listed above.
- The script must run without interactive input.
- Ensure reproducibility with `random.seed(42)` and `numpy.random.seed(42)`.
- Handle edge cases listed in the blueprint.

Output ONLY the Python code – no markdown fences, no explanations.
"""
