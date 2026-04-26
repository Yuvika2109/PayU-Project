"""
schemas/generic_fraud_schema.py
Generic transaction fraud dataset column definitions.

Used for 'Other' fraud scenarios: money laundering, phishing,
synthetic identity, friendly fraud, triangulation, refund abuse, etc.
"""

from __future__ import annotations
from typing import Dict, List

# ── Merchant Categories ────────────────────────────────────────────────────────
GENERIC_MERCHANT_CATEGORIES: List[str] = [
    "Retail", "Electronics", "Travel & Hotels", "Grocery", "Food & Dining",
    "Fuel & Gas", "Healthcare", "Entertainment", "Financial Services",
    "Clothing & Apparel", "Home & Garden", "Sports & Outdoors",
    "Education", "Automotive", "Utilities", "Insurance", "Gambling",
    "Cryptocurrency Exchange", "Money Transfer", "Luxury Goods",
]

# ── Channels ──────────────────────────────────────────────────────────────────
CHANNELS: List[str] = [
    "ONLINE", "POS", "MOBILE_APP", "ATM", "PHONE_ORDER", "MAIL_ORDER",
]

DEVICE_TYPES: List[str] = [
    "MOBILE", "DESKTOP", "TABLET", "ATM_TERMINAL", "POS_TERMINAL",
]

CARD_TYPES: List[str] = ["CREDIT", "DEBIT", "PREPAID", "VIRTUAL"]

CURRENCIES: List[str] = [
    "USD", "EUR", "GBP", "INR", "AUD", "CAD", "SGD", "AED", "MXN", "BRL",
]

CURRENCY_WEIGHTS: Dict[str, float] = {
    "USD": 0.45,
    "EUR": 0.18,
    "GBP": 0.10,
    "INR": 0.08,
    "AUD": 0.05,
    "CAD": 0.04,
    "SGD": 0.03,
    "AED": 0.03,
    "MXN": 0.02,
    "BRL": 0.02,
}

COUNTRIES: List[str] = [
    "US", "GB", "DE", "FR", "IN", "AU", "CA", "SG", "AE", "BR",
    "MX", "JP", "CN", "ZA", "NG", "RU", "UA", "RO", "BY", "VN",
]

# Countries with elevated fraud risk (used in fraud injector)
HIGH_RISK_COUNTRIES: List[str] = [
    "NG", "RU", "UA", "RO", "BY", "VN", "BD", "PK", "GH",
]

# ── MCC pools by fraud scenario ────────────────────────────────────────────────
SCENARIO_MCC_MAP: Dict[str, List[str]] = {
    "money laundering":   ["4829", "6051", "6011", "7995", "6010"],
    "phishing":           ["4829", "6051", "5999", "5732", "7372"],
    "synthetic identity": ["5311", "5732", "5651", "7011", "4511"],
    "friendly fraud":     ["5812", "5999", "5651", "5945", "5411"],
    "triangulation":      ["5999", "5045", "5732", "5065", "7372"],
    "refund fraud":       ["5812", "5999", "5651", "5945", "5411"],
    "identity fraud":     ["5311", "5732", "7011", "4511", "5094"],
    "corporate card":     ["7011", "4511", "5812", "5541", "7011"],
}

# ── High-risk MCCs ─────────────────────────────────────────────────────────────
HIGH_RISK_MCCS: List[str] = [
    "6051",  # Non-Financial Institutions (crypto exchanges, forex)
    "6211",  # Security Brokers/Dealers
    "6010",  # Manual Cash Disbursements
    "6011",  # Automated Cash Disbursements (ATM)
    "7995",  # Betting/Casino Gambling
    "5933",  # Pawn Shops
    "4829",  # Wire Transfer / Money Orders
    "6540",  # Prepaid Load / Funding Transactions
    "7273",  # Dating/Escort Services
    "9222",  # Fines
]

# ── MCC → Category ─────────────────────────────────────────────────────────────
MCC_TO_CATEGORY: Dict[str, str] = {
    "5411": "Grocery",
    "5812": "Food & Dining",
    "5732": "Electronics",
    "5311": "Retail",
    "5651": "Clothing & Apparel",
    "7011": "Travel & Hotels",
    "4511": "Travel & Hotels",
    "6011": "Financial Services",
    "4829": "Financial Services",
    "6051": "Financial Services",
    "5999": "Retail",
    "5094": "Electronics",
    "5045": "Electronics",
    "7372": "Financial Services",
    "7995": "Gambling",
    "6010": "Financial Services",
    "5541": "Fuel & Gas",
    "5945": "Entertainment",
    "5065": "Electronics",
}

# ── Merchant name pools by category ───────────────────────────────────────────
MERCHANT_NAMES_BY_CATEGORY: Dict[str, List[str]] = {
    "Retail":           ["Amazon", "Walmart", "Target", "ASOS", "Flipkart", "eBay", "AliExpress"],
    "Electronics":      ["Best Buy", "Newegg", "B&H Photo", "Croma", "Reliance Digital"],
    "Travel & Hotels":  ["Booking.com", "Airbnb", "Marriott", "Hilton", "MakeMyTrip", "Expedia"],
    "Grocery":          ["Whole Foods", "BigBasket", "Blinkit", "Instacart", "Kroger"],
    "Food & Dining":    ["DoorDash", "Uber Eats", "Swiggy", "Zomato", "Dominos", "Pizza Hut"],
    "Financial Services":["MoneyGram", "Western Union", "Coinbase", "LocalBitcoins", "Remitly"],
    "Gambling":         ["Betway", "DraftKings", "PokerStars", "Casumo", "FanDuel"],
    "Luxury Goods":     ["Louis Vuitton", "Gucci", "Rolex", "Tiffany & Co.", "Cartier"],
    "Clothing & Apparel":["Zara", "H&M", "Nike", "Adidas", "Mango", "Forever21"],
}

# ── OS and browser pools ────────────────────────────────────────────────────────
DEVICE_OS_LIST: List[str] = ["Windows 11", "Windows 10", "macOS 14", "macOS 13",
                               "Android 14", "Android 13", "iOS 17", "iOS 16", "Ubuntu 22.04"]
BROWSER_LIST: List[str] = ["Chrome 120", "Chrome 119", "Firefox 121", "Safari 17",
                             "Edge 120", "Opera 106"]

# ── Column Definitions ─────────────────────────────────────────────────────────
GENERIC_COLUMNS: List[tuple] = [
    # Transaction Identification
    ("txn_id",                     "str",      "Unique transaction identifier (UUID)"),
    ("timestamp",                  "datetime", "Transaction datetime (UTC)"),
    ("hour_of_day",                "int",      "Hour of transaction (0-23)"),
    ("day_of_week",                "int",      "0=Monday … 6=Sunday"),
    ("is_weekend",                 "int",      "1 if Saturday or Sunday"),
    ("is_off_hours",               "int",      "1 if outside 8am-10pm local time"),

    # User / Account
    ("user_id",                    "str",      "Anonymised user account identifier"),
    ("account_age_days",           "int",      "Days since account was opened"),
    ("card_type",                  "str",      "CREDIT / DEBIT / PREPAID / VIRTUAL"),
    ("card_last4",                 "str",      "Last 4 digits of card"),
    ("billing_country",            "str",      "ISO 2-letter billing country code"),

    # Transaction
    ("amount",                     "float",    "Transaction amount (decimal, in transaction currency)"),
    ("currency",                   "str",      "ISO 4217 currency code"),
    ("channel",                    "str",      "ONLINE / POS / MOBILE_APP / ATM / PHONE_ORDER"),
    ("is_round_amount",            "int",      "1 if amount divisible by 100 (structuring signal)"),
    ("is_high_value",              "int",      "1 if amount is in top 5% for this user"),

    # Merchant
    ("merchant_id",                "str",      "Anonymised merchant identifier"),
    ("merchant_name",              "str",      "Merchant display name"),
    ("merchant_category",          "str",      "Merchant category (Retail, Electronics, etc.)"),
    ("merchant_country",           "str",      "ISO 2-letter merchant country code"),
    ("mcc",                        "str",      "ISO 18245 Merchant Category Code"),
    ("is_high_risk_merchant",      "int",      "1 if MCC is in high-risk category"),

    # Device / Network
    ("device_id",                  "str",      "Anonymised device fingerprint"),
    ("device_type",                "str",      "MOBILE / DESKTOP / TABLET / ATM_TERMINAL"),
    ("device_os",                  "str",      "Operating system and version"),
    ("browser",                    "str",      "Browser name and version (online only)"),
    ("ip_address",                 "str",      "Transaction IP address"),
    ("ip_country",                 "str",      "Country inferred from IP geolocation"),
    ("is_new_device",              "int",      "1 if device seen for first time for this user"),
    ("is_foreign_ip",              "int",      "1 if IP country differs from billing country"),
    ("is_vpn_or_proxy",            "int",      "1 if IP flagged as VPN / proxy / datacenter"),

    # Shipping
    ("shipping_country",           "str",      "Shipping destination country (online only)"),
    ("shipping_billing_mismatch",  "int",      "1 if shipping and billing countries differ"),
    ("is_first_time_merchant",     "int",      "1 if user has never transacted with this merchant"),

    # Velocity / Behavioral
    ("velocity_1h",                "int",      "Transactions by this user in last 1 hour"),
    ("velocity_24h",               "int",      "Transactions by this user in last 24 hours"),
    ("amount_vs_user_avg",         "float",    "Ratio: this amount / user's 90-day average amount"),
    ("failed_auth_attempts",       "int",      "Failed auth attempts before this transaction"),
    ("cross_border_flag",          "int",      "1 if merchant country differs from billing country"),
    ("days_since_last_txn",        "int",      "Days since user's previous transaction"),

    # Ground Truth
    ("fraud_label",                "int",      "1 = fraud transaction, 0 = legitimate"),
    ("fraud_type",                 "str",      "Fraud pattern name (empty for legitimate transactions)"),
]

GENERIC_COLUMN_NAMES: List[str] = [col[0] for col in GENERIC_COLUMNS]
