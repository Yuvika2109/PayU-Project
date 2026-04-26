"""
schemas/upi_schema.py
UPI (Unified Payments Interface) dataset column definitions and lookup pools.

Columns are based on the NPCI UPI transaction data format used in Indian
payment systems and fraud analytics. No external standard mandated — columns
reflect what analysts actually need to detect UPI fraud.
"""

from __future__ import annotations
from typing import Dict, List

# ── Indian Banks ───────────────────────────────────────────────────────────────
INDIAN_BANKS: List[str] = [
    "HDFC Bank", "State Bank of India", "ICICI Bank", "Axis Bank",
    "Kotak Mahindra Bank", "Yes Bank", "Punjab National Bank",
    "Bank of Baroda", "Canara Bank", "Union Bank of India",
    "IndusInd Bank", "IDFC First Bank", "Federal Bank", "RBL Bank",
    "South Indian Bank", "Bandhan Bank", "AU Small Finance Bank",
    "Airtel Payments Bank", "Paytm Payments Bank", "India Post Payments Bank",
]

# ── UPI bank handle → bank name ───────────────────────────────────────────────
UPI_HANDLE_TO_BANK: Dict[str, str] = {
    "okhdfc":      "HDFC Bank",
    "oksbi":       "State Bank of India",
    "okicici":     "ICICI Bank",
    "okaxis":      "Axis Bank",
    "ybl":         "Yes Bank",           # PhonePe
    "ibl":         "IndusInd Bank",
    "kotak":       "Kotak Mahindra Bank",
    "pnb":         "Punjab National Bank",
    "barodampay":  "Bank of Baroda",
    "cnrb":        "Canara Bank",
    "unionbank":   "Union Bank of India",
    "idfcbank":    "IDFC First Bank",
    "federal":     "Federal Bank",
    "rblbank":     "RBL Bank",
    "paytm":       "Paytm Payments Bank",
    "apl":         "Airtel Payments Bank",
    "ippb":        "India Post Payments Bank",
}

# ── VPA handle distribution (weighted by app popularity, India 2024) ──────────
UPI_HANDLE_WEIGHTS: Dict[str, float] = {
    "ybl":       0.26,   # PhonePe (most popular)
    "okaxis":    0.14,   # GPay via Axis
    "oksbi":     0.10,   # GPay via SBI
    "okhdfc":    0.09,   # GPay via HDFC
    "okicici":   0.07,   # GPay via ICICI
    "paytm":     0.11,   # Paytm
    "apl":       0.05,   # Amazon Pay
    "kotak":     0.04,   # Kotak
    "idfcbank":  0.03,   # IDFC
    "pnb":       0.03,   # BHIM / PNB
    "federal":   0.02,   # Federal Bank
    "ibl":       0.02,   # IndusInd
    "barodampay":0.02,   # Bank of Baroda
    "cnrb":      0.01,   # Canara Bank
    "ippb":      0.01,   # India Post
}

# ── UPI Payment Apps (maps to primary handle) ─────────────────────────────────
APP_TO_PRIMARY_HANDLE: Dict[str, List[str]] = {
    "PhonePe":       ["ybl", "ibl"],
    "GPay":          ["okaxis", "oksbi", "okhdfc", "okicici"],
    "Paytm":         ["paytm"],
    "BHIM":          ["oksbi", "pnb", "barodampay", "cnrb", "unionbank"],
    "Amazon Pay":    ["apl"],
    "CRED":          ["okhdfc", "ybl"],
    "WhatsApp Pay":  ["oksbi", "okicici", "okaxis"],
    "iMobile Pay":   ["okicici"],
    "HDFC PayZapp":  ["okhdfc"],
    "Slice":         ["ybl"],
}

UPI_APPS: List[str] = list(APP_TO_PRIMARY_HANDLE.keys())

UPI_APP_WEIGHTS: Dict[str, float] = {
    "PhonePe": 0.32,
    "GPay":    0.28,
    "Paytm":   0.14,
    "BHIM":    0.08,
    "Amazon Pay": 0.06,
    "CRED":    0.05,
    "WhatsApp Pay": 0.04,
    "iMobile Pay":  0.01,
    "HDFC PayZapp": 0.01,
    "Slice":   0.01,
}

# ── Indian States + Cities ─────────────────────────────────────────────────────
INDIAN_STATES: List[str] = [
    "Maharashtra", "Karnataka", "Tamil Nadu", "Delhi", "Telangana",
    "Gujarat", "Rajasthan", "Uttar Pradesh", "West Bengal", "Kerala",
    "Madhya Pradesh", "Andhra Pradesh", "Punjab", "Haryana", "Bihar",
    "Odisha", "Jharkhand", "Chhattisgarh", "Assam", "Uttarakhand",
]

STATE_TO_CITIES: Dict[str, List[str]] = {
    "Maharashtra":   ["Mumbai", "Pune", "Nagpur", "Nashik", "Thane", "Aurangabad"],
    "Karnataka":     ["Bengaluru", "Mysuru", "Mangaluru", "Hubli", "Belagavi"],
    "Tamil Nadu":    ["Chennai", "Coimbatore", "Madurai", "Tiruchirappalli", "Salem"],
    "Delhi":         ["New Delhi", "Noida", "Gurgaon", "Faridabad", "Ghaziabad"],
    "Telangana":     ["Hyderabad", "Warangal", "Nizamabad", "Karimnagar"],
    "Gujarat":       ["Ahmedabad", "Surat", "Vadodara", "Rajkot", "Gandhinagar"],
    "Rajasthan":     ["Jaipur", "Jodhpur", "Udaipur", "Kota", "Ajmer"],
    "Uttar Pradesh": ["Lucknow", "Kanpur", "Agra", "Varanasi", "Meerut"],
    "West Bengal":   ["Kolkata", "Howrah", "Durgapur", "Asansol", "Siliguri"],
    "Kerala":        ["Kochi", "Thiruvananthapuram", "Kozhikode", "Thrissur"],
    "Madhya Pradesh":["Indore", "Bhopal", "Jabalpur", "Gwalior"],
    "Andhra Pradesh":["Visakhapatnam", "Vijayawada", "Guntur", "Nellore"],
    "Punjab":        ["Ludhiana", "Amritsar", "Chandigarh", "Jalandhar"],
    "Haryana":       ["Gurgaon", "Faridabad", "Panipat", "Ambala"],
    "Bihar":         ["Patna", "Gaya", "Muzaffarpur", "Bhagalpur"],
    "Odisha":        ["Bhubaneswar", "Cuttack", "Rourkela"],
    "Jharkhand":     ["Ranchi", "Jamshedpur", "Dhanbad"],
    "Chhattisgarh":  ["Raipur", "Bhilai", "Durg"],
    "Assam":         ["Guwahati", "Silchar", "Dibrugarh"],
    "Uttarakhand":   ["Dehradun", "Haridwar", "Rishikesh"],
}

# ── Indian First Names (common male + female) ─────────────────────────────────
INDIAN_FIRST_NAMES: List[str] = [
    "Rahul", "Priya", "Amit", "Neha", "Vijay", "Anjali", "Suresh", "Pooja",
    "Arun", "Kavita", "Rajesh", "Sunita", "Deepak", "Rina", "Sandeep",
    "Meena", "Manoj", "Rekha", "Ashok", "Usha", "Rakesh", "Geeta",
    "Vikas", "Shweta", "Rohit", "Simran", "Arjun", "Divya", "Sanjay",
    "Pallavi", "Nitin", "Sneha", "Gaurav", "Ritu", "Vikram", "Anita",
    "Sachin", "Lakshmi", "Ajay", "Nidhi", "Aditya", "Preeti", "Ravi",
    "Smita", "Kiran", "Nisha", "Sunil", "Madhuri", "Naveen", "Archana",
    "Harish", "Sonia", "Dinesh", "Aarti", "Jitendra", "Manisha", "Vinod",
    "Shruti", "Hemant", "Radha", "Yash", "Poonam", "Anand", "Vandana",
    "Lalit", "Babita", "Mohan", "Sarita", "Ramesh", "Shakuntala", "Girish",
]

INDIAN_LAST_NAMES: List[str] = [
    "Sharma", "Verma", "Patel", "Singh", "Kumar", "Gupta", "Joshi",
    "Mishra", "Pandey", "Yadav", "Shah", "Mehta", "Reddy", "Nair",
    "Iyer", "Pillai", "Chaudhary", "Srivastava", "Tiwari", "Dubey",
    "Malhotra", "Kapoor", "Saxena", "Agarwal", "Bansal", "Goel",
    "Jain", "Khanna", "Bose", "Das", "Roy", "Chatterjee", "Mukherjee",
    "Kulkarni", "Desai", "Patil", "Naik", "More", "Pawar", "Jadhav",
    "Rao", "Naidu", "Murthy", "Shetty", "Hegde", "Menon", "Thomas",
    "Varghese", "Mathew", "Babu", "Rajan", "Krishnan", "Subramaniam",
]

# ── UPI Transaction Types ──────────────────────────────────────────────────────
UPI_TXN_TYPES: List[str] = [
    "COLLECT_REQUEST",   # Payer pulls from payee — payee must approve
    "PUSH_PAY",          # Sender pushes to receiver directly
    "QR_PAY",            # Scan-and-pay via static/dynamic QR
    "INTENT_PAY",        # App-to-app redirect payment (merchant)
    "P2PM",              # Person-to-Merchant payment
]

UPI_TXN_TYPE_WEIGHTS_NORMAL: Dict[str, float] = {
    "PUSH_PAY":        0.40,
    "QR_PAY":          0.25,
    "P2PM":            0.20,
    "INTENT_PAY":      0.10,
    "COLLECT_REQUEST": 0.05,
}

# ── UPI Status Codes ───────────────────────────────────────────────────────────
UPI_SUCCESS = "SUCCESS"
UPI_FAILED  = "FAILED"
UPI_PENDING = "PENDING"
UPI_REVERSED = "REVERSED"

# ── NPCI UPI Failure Reason Codes ────────────────────────────────────────────
UPI_FAILURE_CODES: List[str] = [
    "INSUFFICIENT_FUNDS",
    "WRONG_UPI_PIN",
    "TRANSACTION_LIMIT_EXCEEDED",
    "DAILY_LIMIT_EXCEEDED",
    "ACCOUNT_BLOCKED",
    "BENEFICIARY_ACCOUNT_INVALID",
    "TRANSACTION_TIMEOUT",
    "BANK_SERVER_DOWN",
    "USER_DECLINED",
    "OTP_EXPIRED",
    "VPA_NOT_REGISTERED",
    "INACTIVE_ACCOUNT",
    "DEBIT_FREEZE",
]

# ── Payment Purpose Codes ──────────────────────────────────────────────────────
UPI_PURPOSE_CODES: Dict[str, str] = {
    "00": "Personal Transfer",
    "01": "Merchant Payment",
    "02": "Utility Bill",
    "03": "Loan Repayment",
    "04": "Insurance Premium",
    "05": "Investment",
    "06": "Education Fee",
    "07": "Rent",
    "08": "Cab / Auto",
    "09": "Food & Dining",
}

# ── Realistic Payment Remarks by Purpose ──────────────────────────────────────
REMARKS_BY_PURPOSE: Dict[str, List[str]] = {
    "Personal Transfer": [
        "Sharing dinner cost", "Monthly chanda", "Birthday gift",
        "Paying back", "Borrowed money", "Movie tickets",
        "Thanks for the help", "Petrol split", "Trip expenses",
        "Festival gift", "Wedding contribution",
    ],
    "Merchant Payment": [
        "Order #", "Invoice payment", "Purchase", "Bill payment",
        "Product delivery", "Service fee", "Subscription renewal",
    ],
    "Utility Bill": [
        "Electricity bill", "Water bill", "Gas bill", "Internet bill",
        "Mobile recharge", "DTH recharge",
    ],
    "Food & Dining": [
        "Swiggy order", "Zomato delivery", "Restaurant bill",
        "Lunch", "Dinner", "Breakfast", "Tea & snacks", "Biryani",
    ],
    "Cab / Auto": [
        "Ola ride", "Uber ride", "Auto fare", "Cab fare",
        "Rapido", "Metro card recharge",
    ],
    "Loan Repayment": [
        "EMI payment", "Loan installment", "Credit card bill",
        "NBFC repayment", "Monthly EMI",
    ],
    "Rent": [
        "Monthly rent", "Rent payment", "Room rent", "PG rent",
        "House rent", "Office rent",
    ],
}

# ── Merchant VPA suffixes (merchant UPI handles) ───────────────────────────────
MERCHANT_VPA_SUFFIXES: List[str] = [
    "paytm", "ybl", "okicici", "ibl", "apl", "kotak",
    "razorpay", "cashfree", "instamojo", "billdesk",
]

# ── MCC codes relevant to UPI merchant payments ───────────────────────────────
UPI_MERCHANT_MCC: List[str] = [
    "5411",  # Grocery Stores
    "5812",  # Eating Places/Restaurants
    "4121",  # Taxicabs and Limousines
    "7011",  # Hotels and Motels
    "5912",  # Drug Stores and Pharmacies
    "5999",  # Miscellaneous and Specialty Retail
    "4814",  # Telecommunication Services
    "5691",  # Clothing Stores
    "5732",  # Electronics Stores
    "5045",  # Computers, Peripherals
    "4829",  # Wire Transfer
    "6011",  # Automated Cash Disbursements
    "6051",  # Non-Financial Institutions
]

# ── Column Definitions for the dataset ────────────────────────────────────────
# (column_name, dtype, description)
UPI_COLUMNS: List[tuple] = [
    # Transaction Identification
    ("txn_id",                     "str",      "UPI transaction reference (12-digit numeric)"),
    ("upi_ref_id",                 "str",      "Bank-assigned UPI global transaction ID"),
    ("timestamp",                  "datetime", "Transaction datetime in IST"),
    ("hour_of_day",                "int",      "Hour of transaction (0-23 IST)"),
    ("day_of_week",                "int",      "0=Monday … 6=Sunday"),
    ("is_weekend",                 "int",      "1 if Saturday or Sunday"),
    ("is_off_hours",               "int",      "1 if transaction between 11pm and 6am IST"),

    # Parties
    ("sender_vpa",                 "str",      "Sender Virtual Payment Address e.g. rahul@okaxis"),
    ("receiver_vpa",               "str",      "Receiver VPA e.g. zomato@icici"),
    ("sender_name",                "str",      "Sender's registered name"),
    ("receiver_name",              "str",      "Receiver's registered / display name"),
    ("sender_bank",                "str",      "Sender's linked bank"),
    ("receiver_bank",              "str",      "Receiver's linked bank"),
    ("sender_account_type",        "str",      "SAVINGS / CURRENT / OD"),

    # Transaction Details
    ("amount",                     "float",    "Transaction amount in INR (₹)"),
    ("currency",                   "str",      "Always INR"),
    ("txn_type",                   "str",      "COLLECT_REQUEST / PUSH_PAY / QR_PAY / INTENT_PAY / P2PM"),
    ("txn_status",                 "str",      "SUCCESS / FAILED / PENDING / REVERSED"),
    ("failure_code",               "str",      "NPCI failure reason code (empty for SUCCESS)"),
    ("purpose_code",               "str",      "Payment purpose code 00-09"),
    ("purpose_description",        "str",      "Human-readable purpose"),
    ("remarks",                    "str",      "Sender's payment note"),
    ("mcc",                        "str",      "Merchant Category Code (for P2PM / merchant payments)"),
    ("is_merchant_payment",        "int",      "1 if receiver is a registered merchant VPA"),

    # Device & App
    ("upi_app",                    "str",      "App used: PhonePe / GPay / Paytm / BHIM / etc."),
    ("device_id",                  "str",      "Anonymised device fingerprint"),
    ("device_os",                  "str",      "Android / iOS"),
    ("os_version",                 "str",      "OS version string"),
    ("app_version",                "str",      "UPI app version"),
    ("ip_address",                 "str",      "Device IP address at transaction time"),
    ("is_new_device",              "int",      "1 if device fingerprint seen for first time"),
    ("is_vpn_or_proxy",            "int",      "1 if IP is datacenter / VPN / proxy"),

    # Location
    ("sender_city",                "str",      "Sender's registered city"),
    ("sender_state",               "str",      "Sender's registered state"),
    ("receiver_city",              "str",      "Receiver's city"),
    ("receiver_state",             "str",      "Receiver's state"),
    ("cross_state_flag",           "int",      "1 if sender and receiver are in different states"),

    # Behavioral / Risk Signals
    ("sender_velocity_1h",         "int",      "UPI txns sent by sender in last 1 hour"),
    ("sender_velocity_24h",        "int",      "UPI txns sent by sender in last 24 hours"),
    ("failed_attempts_before",     "int",      "Failed auth attempts in same session before this txn"),
    ("is_new_vpa",                 "int",      "1 if receiver VPA registered within last 7 days"),
    ("is_first_txn_to_vpa",        "int",      "1 if sender has never previously transacted with this receiver"),
    ("collect_requests_1h",        "int",      "Collect requests received by sender in last 1 hour"),
    ("amount_deviation_pct",       "float",    "% deviation from sender's 30-day average transaction amount"),
    ("is_high_value",              "int",      "1 if amount > ₹10,000"),
    ("is_round_amount",            "int",      "1 if amount is exactly divisible by 100"),
    ("days_since_upi_reg",         "int",      "Days since sender first registered on UPI"),
    ("receiver_fraud_score",       "float",    "Historical fraud risk score for receiver VPA (0.0-1.0)"),

    # Ground Truth
    ("fraud_label",                "int",      "1 = fraud transaction, 0 = legitimate"),
    ("fraud_type",                 "str",      "Fraud pattern name (empty for legitimate transactions)"),
]

UPI_COLUMN_NAMES: List[str] = [col[0] for col in UPI_COLUMNS]
