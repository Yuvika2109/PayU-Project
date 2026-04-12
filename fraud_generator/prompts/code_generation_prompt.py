"""
prompts/code_generation_prompt.py  (v2 — EMVCo 3DS)
Prompt template for the Code Generator Agent.
Updated to reference the full EMVCo 3DS v2.3.1 column set.
"""

import json


def build_code_generation_prompt(blueprint: dict, output_path: str) -> str:
    """
    Build the prompt that instructs the LLM to generate a self-contained
    Python script from the fraud blueprint that produces EMVCo 3DS columns.

    Parameters
    ----------
    blueprint   : The validated fraud blueprint dict.
    output_path : Absolute path where the output file should be saved.

    Returns
    -------
    str: Full prompt string.
    """
    blueprint_json = json.dumps(blueprint, indent=2)
    scenario       = blueprint.get("Fraud_Scenario_Name", "Unknown")
    specs          = blueprint.get("Dataset_Specifications", {})
    total_rows     = specs.get("total_rows", 1000)
    fraud_ratio    = specs.get("fraud_ratio", 0.05)
    output_format  = specs.get("output_format", "csv").lower()

    return f"""You are a senior Python data-engineering specialist working on EMVCo 3DS synthetic data.
Generate a complete, self-contained Python script that creates a synthetic 3DS fraud dataset.

## FRAUD BLUEPRINT
{blueprint_json}

## SCRIPT REQUIREMENTS
1. Use ONLY these libraries: pandas, numpy, faker, datetime, random, uuid, os, pathlib, hashlib
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

## EMVCo 3DS COLUMN REQUIREMENTS (ALL must be present)

### Transaction / Auth Identification
threeds_server_trans_id, acs_trans_id, ds_trans_id, sdk_trans_id,
message_version, device_channel, three_ds_requestor_id, three_ds_requestor_name

### Cardholder / Account
acct_number, card_expiry_date, acct_id, acct_type,
acct_info_chg_ind, acct_info_open_acct_ind, acct_info_ship_addr_usage_ind,
acct_info_txn_activity_day, acct_info_txn_activity_year, acct_info_prov_attempts_day,
acct_info_nb_purchase_account,
ship_addr_match, ship_addr_usage_ind,
bill_addr_city, bill_addr_country, bill_addr_state, email

### Browser / Device Fingerprint
browser_accept_header, browser_ip, browser_java_enabled, browser_javascript_enabled,
browser_language, browser_color_depth, browser_screen_height, browser_screen_width,
browser_tz, browser_user_agent,
sdk_app_id, sdk_enc_data, sdk_ephem_pub_key, sdk_max_timeout, sdk_reference_number

### Merchant & Acquirer
merchant_id, merchant_name, mcc, acquirer_bin, acquirer_merchant_id, merchant_country_code

### Purchase / Transaction
purchase_amount, purchase_currency, purchase_exponent, purchase_date, trans_type,
recurring_expiry, recurring_frequency

### Authentication Response
three_ds_requestor_auth_ind, three_ds_comp_ind, acs_challenge_mandated,
authentication_type, trans_status, trans_status_reason, eci, authentication_value,
acs_reference_number, ds_reference_number, challenge_completed, challenge_cancel_ind

### Prior Auth
three_ds_requestor_prior_auth_ind, prior_auth_method, prior_auth_timestamp

### Risk Signals
ship_indicator, delivery_timeframe, reorder_items_ind, pre_order_purchase_ind,
gift_card_amount, gift_card_count, purchase_instal_data

### Derived ML Features
velocity_1h, velocity_24h, amount_vs_avg_ratio, new_device_flag, new_shipping_addr_flag,
cross_border_flag, high_risk_mcc_flag, time_since_acct_open_days

### Ground Truth
fraud_label, fraud_pattern

### Derived Time Features (added after generation)
hour_of_day, day_of_week, is_weekend, purchase_amount_decimal

## EMVCo FIELD ENCODING RULES
- purchase_amount: integer in minor currency units (e.g. $9.99 USD = 999)
- purchase_currency: ISO 4217 numeric string (USD=840, EUR=978, GBP=826)
- purchase_exponent: typically 2 for most currencies
- purchase_date: string format YYYYMMDDHHmmss UTC
- acct_number: masked PAN — first 6 digits + asterisks + last 4 (e.g. "411111******1234")
- card_expiry_date: YYMM format (e.g. "2812" = Dec 2028)
- bill_addr_country / merchant_country_code: ISO 3166-1 numeric (e.g. "840" = USA)
- eci: "05"=full auth Visa, "02"=full auth MC, "06"/"01"=attempts, "07"=not auth
- trans_status: "Y"=authenticated, "N"=not auth, "U"=unknown, "A"=attempts, "C"=challenge, "R"=rejected
- browser_tz: integer minutes offset from UTC (e.g. -300 = UTC-5)
- email: SHA-256 hash of actual email (first 16 hex chars for brevity)
- device_channel: "01"=APP(SDK), "02"=BRW(browser), "03"=3RI

## FRAUD BEHAVIOUR for "{scenario}"
- Implement the Fraud_Patterns from the blueprint realistically.
- For fraud rows, use the Anomaly_Signals from the blueprint to set realistic
  3DS field values:
    * High velocity_1h/velocity_24h for burst patterns
    * acct_info_open_acct_ind="01" for new-account fraud
    * ship_addr_match="N" and new_shipping_addr_flag=1 for account takeover
    * cross_border_flag=1 and foreign browser_ip for cross-border fraud
    * high_risk_mcc_flag=1 for MCCs in {{6051, 6211, 7995, 4829, 6540}}
    * trans_status mostly "Y" (fraud that got through) with some "N"/"U"

## STRICT RULES
- Do NOT use any external API or network calls.
- Do NOT import libraries not listed above.
- The script must run without interactive input.
- Ensure reproducibility with `random.seed(42)` and `numpy.random.seed(42)`.
- Handle edge cases listed in the blueprint.

Output ONLY the Python code – no markdown fences, no explanations.
"""