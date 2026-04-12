"""
prompts/error_fix_prompt.py  (v2 — EMVCo 3DS)
Prompt template for the Error Fix Agent.
Updated to reference EMVCo 3DS column names for context.
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
            "Anomaly_Signals": blueprint.get("Anomaly_Signals"),
        },
        indent=2,
    )

    return f"""You are a Python debugging expert (fix attempt {attempt}).

A synthetic EMVCo 3DS fraud-dataset generation script failed with an error.
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
3. Preserve the original intent: generate a synthetic EMVCo 3DS fraud dataset matching the blueprint.
4. Ensure ALL required EMVCo 3DS columns exist in the output DataFrame:

   IDENTIFICATION: threeds_server_trans_id, acs_trans_id, ds_trans_id, sdk_trans_id,
     message_version, device_channel, three_ds_requestor_id, three_ds_requestor_name

   CARDHOLDER: acct_number, card_expiry_date, acct_id, acct_type,
     acct_info_chg_ind, acct_info_open_acct_ind, acct_info_ship_addr_usage_ind,
     acct_info_txn_activity_day, acct_info_txn_activity_year, acct_info_prov_attempts_day,
     acct_info_nb_purchase_account, ship_addr_match, ship_addr_usage_ind,
     bill_addr_city, bill_addr_country, bill_addr_state, email

   BROWSER: browser_accept_header, browser_ip, browser_java_enabled,
     browser_javascript_enabled, browser_language, browser_color_depth,
     browser_screen_height, browser_screen_width, browser_tz, browser_user_agent,
     sdk_app_id, sdk_enc_data, sdk_ephem_pub_key, sdk_max_timeout, sdk_reference_number

   MERCHANT: merchant_id, merchant_name, mcc, acquirer_bin, acquirer_merchant_id,
     merchant_country_code

   PURCHASE: purchase_amount, purchase_currency, purchase_exponent, purchase_date,
     trans_type, recurring_expiry, recurring_frequency

   AUTH: three_ds_requestor_auth_ind, three_ds_comp_ind, acs_challenge_mandated,
     authentication_type, trans_status, trans_status_reason, eci, authentication_value,
     acs_reference_number, ds_reference_number, challenge_completed, challenge_cancel_ind

   PRIOR_AUTH: three_ds_requestor_prior_auth_ind, prior_auth_method, prior_auth_timestamp

   RISK: ship_indicator, delivery_timeframe, reorder_items_ind, pre_order_purchase_ind,
     gift_card_amount, gift_card_count, purchase_instal_data

   DERIVED: velocity_1h, velocity_24h, amount_vs_avg_ratio, new_device_flag,
     new_shipping_addr_flag, cross_border_flag, high_risk_mcc_flag,
     time_since_acct_open_days, hour_of_day, day_of_week, is_weekend,
     purchase_amount_decimal

   GROUND_TRUTH: fraud_label, fraud_pattern

5. EMVCo field encoding requirements:
   - purchase_amount: integer in minor units (dollars × 100)
   - purchase_currency: ISO 4217 numeric string (e.g. "840" for USD)
   - purchase_date: string YYYYMMDDHHmmss UTC
   - acct_number: masked PAN (first6 + asterisks + last4)
   - card_expiry_date: YYMM format
   - merchant_country_code / bill_addr_country: ISO 3166-1 numeric string
   - eci: "05"=full Visa, "02"=full MC, "06"/"01"=attempts, "07"=not auth
   - browser_tz: integer (UTC offset in minutes, e.g. -300 = UTC-5)

6. Use only: pandas, numpy, faker, datetime, random, uuid, os, pathlib, hashlib.
7. Keep `random.seed(42)` and `numpy.random.seed(42)` for reproducibility.

Output ONLY the corrected Python code – no markdown fences, no explanations.
"""