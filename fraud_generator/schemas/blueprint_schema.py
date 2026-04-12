"""
schemas/blueprint_schema.py  (v3 — EMVCo 3DS)

JSON-Schema for the fraud blueprint v2, extended with:
  - Column_Definitions now references EMVCo 3DS data elements
  - Validation_Constraints covers EMVCo-specific enum/range rules
  - QUANTITATIVE_CHECKS updated for purchase_amount (minor units)

All data elements follow EMVCo 3-D Secure Core Specification v2.3.1.
"""

BLUEPRINT_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "FraudBlueprint_v3_EMVCo3DS",
    "type": "object",
    "required": [
        "Fraud_Scenario_Name",
        "Description",
        "Fraud_Type",
        "Dataset_Specifications",
        "Normal_User_Profile",
        "Fraud_Patterns",
        "Fraud_Injection_Rules",
        "Sequence_Rules",
        "Anomaly_Signals",
        "Column_Definitions",
        "Validation_Constraints",
    ],
    "properties": {
        "Fraud_Scenario_Name": {"type": "string", "minLength": 1},
        "Description":         {"type": "string", "minLength": 1},
        "Fraud_Type":          {"type": "string", "minLength": 1},

        "Dataset_Specifications": {
            "type": "object",
            "required": ["total_rows", "fraud_ratio", "output_format",
                         "date_range_start", "date_range_end",
                         "num_users", "num_merchants"],
            "properties": {
                "total_rows":       {"type": "integer", "minimum": 1},
                "fraud_ratio":      {"type": "number",  "minimum": 0.001, "maximum": 0.99},
                "output_format":    {"type": "string",
                                     "enum": ["csv", "json", "parquet", "excel"]},
                "date_range_start": {"type": "string", "pattern": "^\\d{4}-\\d{2}-\\d{2}$"},
                "date_range_end":   {"type": "string", "pattern": "^\\d{4}-\\d{2}-\\d{2}$"},
                "num_users":        {"type": "integer", "minimum": 1},
                "num_merchants":    {"type": "integer", "minimum": 1},
            },
        },

        "Normal_User_Profile": {
            "type": "object",
            "required": [
                "transaction_amount", "transactions_per_day",
                "active_hours", "active_days",
                "merchant_category_weights", "currency_weights",
                "location_change_prob", "device_change_prob",
            ],
            "properties": {
                "transaction_amount": {
                    "type": "object",
                    "required": ["distribution", "min", "max", "mean", "std"],
                    "properties": {
                        "distribution": {"type": "string",
                                         "enum": ["normal", "lognormal", "uniform", "pareto"]},
                        "min":  {"type": "number", "minimum": 0.01},
                        "max":  {"type": "number"},
                        "mean": {"type": "number"},
                        "std":  {"type": "number", "minimum": 0},
                    },
                },
                "transactions_per_day": {
                    "type": "object",
                    "required": ["mean", "std", "max"],
                    "properties": {
                        "mean": {"type": "number", "minimum": 0},
                        "std":  {"type": "number", "minimum": 0},
                        "max":  {"type": "integer", "minimum": 1},
                    },
                },
                "active_hours": {
                    "type": "object",
                    "required": ["peak_start", "peak_end", "off_peak_weight"],
                    "properties": {
                        "peak_start":      {"type": "integer", "minimum": 0, "maximum": 23},
                        "peak_end":        {"type": "integer", "minimum": 0, "maximum": 23},
                        "off_peak_weight": {"type": "number",  "minimum": 0, "maximum": 1},
                    },
                },
                "active_days": {
                    "type": "object",
                    "required": ["weekday_weight", "weekend_weight"],
                    "properties": {
                        "weekday_weight": {"type": "number", "minimum": 0},
                        "weekend_weight": {"type": "number", "minimum": 0},
                    },
                },
                "merchant_category_weights": {"type": "object", "minProperties": 1},
                "currency_weights":          {"type": "object", "minProperties": 1},
                "location_change_prob":      {"type": "number", "minimum": 0, "maximum": 1},
                "device_change_prob":        {"type": "number", "minimum": 0, "maximum": 1},
            },
        },

        "Fraud_Patterns": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "required": ["pattern_name", "description", "weight",
                             "params", "sequence_type"],
                "properties": {
                    "pattern_name":  {"type": "string"},
                    "description":   {"type": "string"},
                    "weight":        {"type": "number", "minimum": 0},
                    "sequence_type": {"type": "string",
                                      "enum": ["independent", "burst", "chain", "network"]},
                    "params": {
                        "type": "object",
                        "properties": {
                            "amount_min":            {"type": "number", "minimum": 0.01},
                            "amount_max":            {"type": "number"},
                            "amount_mean":           {"type": "number"},
                            "amount_std":            {"type": "number"},
                            "burst_min_txns":        {"type": "integer", "minimum": 1},
                            "burst_max_txns":        {"type": "integer"},
                            "burst_window_mins":     {"type": "integer"},
                            "num_accounts":          {"type": "integer"},
                            "num_merchants":         {"type": "integer"},
                            "preferred_hours":       {"type": "array",
                                                      "items": {"type": "integer"}},
                            "preferred_days":        {"type": "array",
                                                      "items": {"type": "integer"}},
                            "same_device_prob":      {"type": "number", "minimum": 0, "maximum": 1},
                            "same_location_prob":    {"type": "number", "minimum": 0, "maximum": 1},
                            "foreign_ip_prob":       {"type": "number", "minimum": 0, "maximum": 1},
                            "round_amount_prob":     {"type": "number", "minimum": 0, "maximum": 1},
                            "velocity_txns_per_hour":{"type": "number", "minimum": 0},
                            # EMVCo 3DS-specific fraud params
                            "trans_status_dist":     {"type": "object",
                                                      "description": "Weights for Y/N/U/A/C trans_status for this pattern"},
                            "aci_new_acct_prob":     {"type": "number", "minimum": 0, "maximum": 1,
                                                      "description": "Prob acct_info_open_acct_ind=01 (new account fraud)"},
                            "challenge_bypass_prob": {"type": "number", "minimum": 0, "maximum": 1,
                                                      "description": "Prob fraud avoids 3DS challenge"},
                            "high_risk_mcc_prob":    {"type": "number", "minimum": 0, "maximum": 1,
                                                      "description": "Prob of transaction at high-risk MCC"},
                            "cross_border_prob":     {"type": "number", "minimum": 0, "maximum": 1,
                                                      "description": "Prob merchantCountryCode != billAddrCountry"},
                            "gift_card_prob":        {"type": "number", "minimum": 0, "maximum": 1,
                                                      "description": "Prob of prepaid/gift card purchase"},
                        },
                    },
                },
            },
        },

        "Fraud_Injection_Rules": {
            "type": "object",
            "required": ["strategy", "fraud_user_ratio",
                         "max_fraud_txns_per_user", "contaminate_normal_users"],
            "properties": {
                "strategy": {"type": "string",
                              "enum": ["dedicated_fraudsters", "mixed"]},
                "fraud_user_ratio":          {"type": "number", "minimum": 0, "maximum": 1},
                "max_fraud_txns_per_user":   {"type": "integer", "minimum": 1},
                "contaminate_normal_users":  {"type": "boolean"},
                "contamination_prob":        {"type": "number", "minimum": 0, "maximum": 1},
            },
        },

        "Sequence_Rules": {
            "type": "object",
            "required": ["enabled", "max_chain_length", "inter_txn_gap_seconds"],
            "properties": {
                "enabled":          {"type": "boolean"},
                "max_chain_length": {"type": "integer", "minimum": 1},
                "inter_txn_gap_seconds": {
                    "type": "object",
                    "required": ["min", "max"],
                    "properties": {
                        "min": {"type": "integer", "minimum": 0},
                        "max": {"type": "integer", "minimum": 1},
                    },
                },
                "reuse_card_in_chain":     {"type": "boolean"},
                "reuse_merchant_in_chain": {"type": "boolean"},
            },
        },

        "Anomaly_Signals": {
            "type": "object",
            "minProperties": 1,
            "description": (
                "Maps pattern_name → dict of EMVCo 3DS column thresholds. "
                "E.g. {\"BIN_Attack\": {\"velocity_1h\": \"> 30\", "
                "\"acct_info_open_acct_ind\": \"== 01\", "
                "\"purchase_amount\": \"< 200 (minor units)\"}}"
            ),
        },

        # ── EMVCo 3DS Column Definitions ──────────────────────────────────────
        "Column_Definitions": {
            "type": "object",
            "minProperties": 1,
            "description": (
                "Maps each EMVCo 3DS column name to its data element spec. "
                "Keys correspond to columns in schemas/emvco_3ds_schema.py "
                "CORE_COLUMNS list."
            ),
        },

        # ── EMVCo 3DS Validation Constraints ──────────────────────────────────
        "Validation_Constraints": {
            "type": "object",
            "description": (
                "EMVCo 3DS v2.3.1 field-level validation rules. "
                "E.g. purchase_currency must be ISO 4217 numeric, "
                "eci must be 01-07, trans_status in {Y,N,U,A,C,R,I}."
            ),
        },
    },
}

REQUIRED_TOP_LEVEL_KEYS = [
    "Fraud_Scenario_Name",
    "Dataset_Specifications",
    "Normal_User_Profile",
    "Fraud_Patterns",
    "Fraud_Injection_Rules",
    "Sequence_Rules",
    "Anomaly_Signals",
]

# Quantitative cross-field checks — references purchase_amount profile
QUANTITATIVE_CHECKS = [
    ("Normal_User_Profile", "transaction_amount", ["min", "max", "mean", "std"]),
    ("Normal_User_Profile", "transactions_per_day", ["mean", "max"]),
    ("Normal_User_Profile", "active_hours", ["peak_start", "peak_end"]),
]

# ── EMVCo Column Definition Block (injected into generated blueprints) ─────────
# This block is written into the blueprint JSON under "Column_Definitions" so that
# downstream consumers know the exact EMVCo element IDs and types.

EMVCO_COLUMN_DEFINITION_BLOCK = {
    "threeds_server_trans_id":    {"emvco_id": "3DSServerTransID",      "type": "string (UUID)"},
    "acs_trans_id":               {"emvco_id": "acsTransID",            "type": "string (UUID)"},
    "ds_trans_id":                {"emvco_id": "dsTransID",             "type": "string (UUID)"},
    "message_version":            {"emvco_id": "messageVersion",        "type": "enum: 2.1.0|2.2.0|2.3.1"},
    "device_channel":             {"emvco_id": "deviceChannel",         "type": "enum: 01=APP|02=BRW|03=3RI"},
    "acct_number":                {"emvco_id": "acctNumber",            "type": "string (masked PAN)"},
    "card_expiry_date":           {"emvco_id": "cardExpiryDate",        "type": "string YYMM"},
    "acct_type":                  {"emvco_id": "acctType",              "type": "enum: 01|02|03"},
    "acct_info_chg_ind":          {"emvco_id": "acctInfo.chgInd",       "type": "enum: 01|02|03|04"},
    "acct_info_open_acct_ind":    {"emvco_id": "acctInfo.openAcctInd",  "type": "enum: 01|02|03|04"},
    "acct_info_txn_activity_day": {"emvco_id": "acctInfo.txnActivityDay","type": "integer"},
    "acct_info_txn_activity_year":{"emvco_id": "acctInfo.txnActivityYear","type": "integer"},
    "acct_info_nb_purchase_account":{"emvco_id":"acctInfo.nbPurchaseAccount","type":"integer"},
    "ship_addr_match":            {"emvco_id": "shipAddrMatch",         "type": "enum: Y|N"},
    "browser_ip":                 {"emvco_id": "browserIP",             "type": "string (IPv4/IPv6)"},
    "browser_language":           {"emvco_id": "browserLanguage",       "type": "string (IETF BCP 47)"},
    "browser_user_agent":         {"emvco_id": "browserUserAgent",      "type": "string"},
    "browser_java_enabled":       {"emvco_id": "browserJavaEnabled",    "type": "boolean"},
    "browser_javascript_enabled": {"emvco_id": "browserJavascriptEnabled","type": "boolean"},
    "browser_screen_height":      {"emvco_id": "browserScreenHeight",   "type": "integer (pixels)"},
    "browser_screen_width":       {"emvco_id": "browserScreenWidth",    "type": "integer (pixels)"},
    "browser_tz":                 {"emvco_id": "browserTZ",             "type": "integer (UTC offset minutes)"},
    "merchant_id":                {"emvco_id": "merchantID",            "type": "string"},
    "mcc":                        {"emvco_id": "mcc",                   "type": "string (ISO 18245, 4-digit)"},
    "acquirer_bin":               {"emvco_id": "acquirerBIN",           "type": "string (6-11 digits)"},
    "merchant_country_code":      {"emvco_id": "merchantCountryCode",   "type": "string (ISO 3166-1 numeric)"},
    "purchase_amount":            {"emvco_id": "purchaseAmount",        "type": "integer (minor currency units)"},
    "purchase_currency":          {"emvco_id": "purchaseCurrency",      "type": "string (ISO 4217 numeric)"},
    "purchase_exponent":          {"emvco_id": "purchaseExponent",      "type": "integer (0-9)"},
    "purchase_date":              {"emvco_id": "purchaseDate",          "type": "string YYYYMMDDHHmmss UTC"},
    "trans_type":                 {"emvco_id": "transType",             "type": "enum: 01|03|10|11|28"},
    "three_ds_requestor_auth_ind":{"emvco_id": "threeDSRequestorAuthInd","type": "enum: 01-07"},
    "three_ds_comp_ind":          {"emvco_id": "threeDSCompInd",        "type": "enum: Y|N|U"},
    "acs_challenge_mandated":     {"emvco_id": "acsChallengeMandate",   "type": "enum: Y|N"},
    "trans_status":               {"emvco_id": "transStatus",           "type": "enum: Y|N|U|A|C|R|I"},
    "eci":                        {"emvco_id": "eci",                   "type": "string: 01-07"},
    "challenge_completed":        {"emvco_id": "challengeCompleted",    "type": "boolean"},
    # Derived / synthetic
    "velocity_1h":                {"emvco_id": "DERIVED",               "type": "integer"},
    "velocity_24h":               {"emvco_id": "DERIVED",               "type": "integer"},
    "amount_vs_avg_ratio":        {"emvco_id": "DERIVED",               "type": "float"},
    "new_device_flag":            {"emvco_id": "DERIVED",               "type": "integer (0|1)"},
    "new_shipping_addr_flag":     {"emvco_id": "DERIVED",               "type": "integer (0|1)"},
    "cross_border_flag":          {"emvco_id": "DERIVED",               "type": "integer (0|1)"},
    "high_risk_mcc_flag":         {"emvco_id": "DERIVED",               "type": "integer (0|1)"},
    "fraud_label":                {"emvco_id": "SYNTHETIC",             "type": "integer (0|1)"},
    "fraud_pattern":              {"emvco_id": "SYNTHETIC",             "type": "string"},
}

EMVCO_VALIDATION_CONSTRAINTS = {
    "purchase_currency":   "ISO 4217 numeric 3-digit code (e.g. 840=USD, 978=EUR)",
    "purchase_exponent":   "0-9; typically 2 for most currencies",
    "purchase_date":       "YYYYMMDDHHmmss UTC format",
    "eci":                 "02 or 05 = full auth; 01 or 06 = attempts processing; 07 = not auth",
    "trans_status":        "Y | N | U | A | C | R | I",
    "device_channel":      "01=APP (SDK) | 02=BRW (browser) | 03=3RI (requestor-initiated)",
    "message_version":     "2.1.0 | 2.2.0 | 2.3.1",
    "mcc":                 "4-digit ISO 18245 Merchant Category Code",
    "acquirer_bin":        "6 to 11 numeric digits",
    "merchant_country_code": "ISO 3166-1 3-digit numeric country code",
    "bill_addr_country":   "ISO 3166-1 3-digit numeric country code",
    "acct_number":         "First-6 + masked middle + last-4 of PAN",
    "card_expiry_date":    "YYMM format",
    "browser_tz":          "UTC offset in whole minutes (e.g. -300 = UTC-5)",
    "acct_info_open_acct_ind": "01=New|02=<30d|03=30-60d|04=>60d",
    "trans_type":          "01=Goods/Service|03=Check|10=Funding|11=Quasi-Cash|28=Prepaid",
}