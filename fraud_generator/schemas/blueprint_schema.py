"""
schemas/blueprint_schema.py  (v2 — machine-readable / quantitative)

Every field that influences data generation MUST be numeric or enumerable.
String descriptions are allowed alongside quantitative fields for readability,
but the generator engine reads only numeric / boolean / enum fields.
"""

BLUEPRINT_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "FraudBlueprint_v2",
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
                "output_format":    {"type": "string"},
                "date_range_start": {"type": "string"},
                "date_range_end":   {"type": "string"},
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
                        "min":  {"type": "number"},
                        "max":  {"type": "number"},
                        "mean": {"type": "number"},
                        "std":  {"type": "number"},
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
                            "amount_min":            {"type": "number"},
                            "amount_max":            {"type": "number"},
                            "amount_mean":           {"type": "number"},
                            "amount_std":            {"type": "number"},
                            "burst_min_txns":        {"type": "integer"},
                            "burst_max_txns":        {"type": "integer"},
                            "burst_window_mins":     {"type": "integer"},
                            "num_accounts":          {"type": "integer"},
                            "num_merchants":         {"type": "integer"},
                            "preferred_hours":       {"type": "array",
                                                      "items": {"type": "integer"}},
                            "preferred_days":        {"type": "array",
                                                      "items": {"type": "integer"}},
                            "same_device_prob":      {"type": "number"},
                            "same_location_prob":    {"type": "number"},
                            "foreign_ip_prob":       {"type": "number"},
                            "round_amount_prob":     {"type": "number"},
                            "velocity_txns_per_hour":{"type": "number"},
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

        "Anomaly_Signals": {"type": "object", "minProperties": 1},
        "Column_Definitions": {"type": "object", "minProperties": 1},
        "Validation_Constraints": {"type": "object"},
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

QUANTITATIVE_CHECKS = [
    ("Normal_User_Profile", "transaction_amount", ["min", "max", "mean", "std"]),
    ("Normal_User_Profile", "transactions_per_day", ["mean", "max"]),
    ("Normal_User_Profile", "active_hours", ["peak_start", "peak_end"]),
]