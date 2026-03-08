"""
prompts/error_fix_prompt.py
Prompt template for the Error Fix Agent.
"""

import json


def build_error_fix_prompt(
    blueprint: dict,
    broken_code: str,
    error_message: str,
    attempt: int,
) -> str:
    """
    Build the prompt that asks the LLM to repair failing generated code.

    Parameters
    ----------
    blueprint     : The validated fraud blueprint dict.
    broken_code   : The Python code that raised an error.
    error_message : The full traceback / error captured from execution.
    attempt       : Which fix attempt this is (1-based).

    Returns
    -------
    str: Full prompt string.
    """
    blueprint_summary = json.dumps(
        {
            "Fraud_Scenario_Name": blueprint.get("Fraud_Scenario_Name"),
            "Dataset_Specifications": blueprint.get("Dataset_Specifications"),
            "Fraud_Patterns": blueprint.get("Fraud_Patterns"),
        },
        indent=2,
    )

    return f"""You are a Python debugging expert (fix attempt {attempt}).

A synthetic fraud-dataset generation script failed with an error.
Your job is to return a CORRECTED, complete, runnable Python script.

## ERROR MESSAGE
{error_message}

## BLUEPRINT CONTEXT (summary)
{blueprint_summary}

## BROKEN CODE
{broken_code}

## INSTRUCTIONS
1. Analyse the error carefully.
2. Fix the root cause – do NOT just suppress the exception.
3. Preserve the original intent: generate a synthetic fraud dataset matching the blueprint.
4. Ensure all required columns exist: transaction_id, timestamp, user_id, card_number,
   bin_number, merchant_id, merchant_category, transaction_amount, currency, location,
   device_id, ip_address, fraud_label.
5. Use only: pandas, numpy, faker, datetime, random, uuid, os, pathlib.
6. Keep `random.seed(42)` and `numpy.random.seed(42)` for reproducibility.

Output ONLY the corrected Python code – no markdown fences, no explanations.
"""
