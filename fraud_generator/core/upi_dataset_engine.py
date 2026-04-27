"""
core/upi_dataset_engine.py
Realistic UPI (Unified Payments Interface) fraud dataset generator.

Generates synthetic UPI transaction data with:
  - Realistic Indian user/merchant profiles and VPAs
  - Normal daily UPI transactions (P2P, merchant payments, bill payments)
  - Three fraud patterns with hardcoded realistic behavioral signals:
      1. UPI Collect Scam  — rapid collect requests, failed attempts, new VPA
      2. UPI Mule Chain    — layered fund transfers across accounts
      3. UPI Credential Fraud — stolen credentials, new device, high value

Called by DatasetEngine when blueprint["fraud_category"] == "upi".
No LLM involvement — fully deterministic given a seed.
"""

from __future__ import annotations

import hashlib
import random
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from schemas.upi_schema import (
    APP_TO_PRIMARY_HANDLE,
    INDIAN_BANKS,
    INDIAN_FIRST_NAMES,
    INDIAN_LAST_NAMES,
    INDIAN_STATES,
    MERCHANT_VPA_SUFFIXES,
    REMARKS_BY_PURPOSE,
    STATE_TO_CITIES,
    UPI_APP_WEIGHTS,
    UPI_APPS,
    UPI_COLUMN_NAMES,
    UPI_FAILURE_CODES,
    UPI_HANDLE_TO_BANK,
    UPI_HANDLE_WEIGHTS,
    UPI_MERCHANT_MCC,
    UPI_PURPOSE_CODES,
    UPI_SUCCESS,
    UPI_FAILED,
    UPI_TXN_TYPES,
    UPI_TXN_TYPE_WEIGHTS_NORMAL,
)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _weighted_choice(weights: Dict[str, float]) -> str:
    keys  = list(weights.keys())
    probs = list(weights.values())
    total = sum(probs)
    probs = [p / total for p in probs]
    return random.choices(keys, weights=probs, k=1)[0]


def _indian_name() -> str:
    first = random.choice(INDIAN_FIRST_NAMES)
    last  = random.choice(INDIAN_LAST_NAMES)
    return f"{first} {last}"


def _make_vpa(name: str, handle: str) -> str:
    """Create a realistic VPA from name + handle."""
    first = name.split()[0].lower()
    last  = name.split()[-1].lower() if len(name.split()) > 1 else ""
    style = random.random()
    if style < 0.35:
        return f"{first}.{last}@{handle}"
    elif style < 0.60:
        n = random.randint(1, 999)
        return f"{first}{n}@{handle}"
    elif style < 0.80:
        phone_stub = random.randint(60000, 99999)
        return f"9{phone_stub}@{handle}"
    else:
        return f"{first}{last}@{handle}"


def _make_merchant_vpa(merchant_name: str) -> str:
    slug   = merchant_name.lower().replace(" ", "").replace("&", "")[:12]
    handle = random.choice(MERCHANT_VPA_SUFFIXES)
    return f"{slug}@{handle}"


def _indian_ip() -> str:
    """Generate a plausible Indian ISP IP (Jio/Airtel/BSNL ranges)."""
    prefixes = ["49.36", "49.37", "49.204", "106.51", "103.21",
                "157.42", "117.98", "115.240", "122.167", "59.95"]
    return f"{random.choice(prefixes)}.{random.randint(0,255)}.{random.randint(1,254)}"


def _suspicious_ip() -> str:
    """IP range that looks like VPN / datacenter / foreign."""
    prefixes = ["45.33", "104.21", "192.241", "185.220", "51.15",
                "95.179", "77.247", "198.50", "136.243", "94.102"]
    return f"{random.choice(prefixes)}.{random.randint(0,255)}.{random.randint(1,254)}"


def _txn_id() -> str:
    return "".join([str(random.randint(0, 9)) for _ in range(12)])


def _upi_ref_id(ts: datetime) -> str:
    return ts.strftime("%y%m%d%H%M%S") + str(random.randint(10000000, 99999999))


def _app_version(app: str) -> str:
    versions = {
        "PhonePe":    ["4.8.1", "4.9.0", "5.0.2", "5.1.0"],
        "GPay":       ["240.0", "241.1", "242.0", "243.0"],
        "Paytm":      ["10.5.1", "10.6.0", "10.7.2", "11.0.0"],
        "BHIM":       ["3.2.0", "3.3.0", "3.4.1"],
        "Amazon Pay": ["24.1.0", "24.2.1", "24.3.0"],
        "CRED":       ["4.4.5", "4.5.0", "4.6.1"],
    }
    return random.choice(versions.get(app, ["1.0.0", "1.1.0", "2.0.0"]))


def _os_version(os: str) -> str:
    if os == "Android":
        return random.choice(["Android 12", "Android 13", "Android 14"])
    return random.choice(["iOS 15.8", "iOS 16.7", "iOS 17.2", "iOS 17.4"])


def _amount_deviation(amount: float, user_avg: float) -> float:
    if user_avg <= 0:
        return 0.0
    return round((amount - user_avg) / user_avg * 100, 1)


# ─── Data Classes ──────────────────────────────────────────────────────────────

@dataclass
class UPIUser:
    user_id:        str
    name:           str
    vpa:            str
    bank:           str
    handle:         str
    app:            str
    device_id:      str
    device_os:      str
    city:           str
    state:          str
    account_type:   str
    days_on_upi:    int
    avg_txn_amount: float
    is_fraudster:   bool = False
    mule_hop:       int  = 0         # 0 = not mule; 1..N = hop index in chain


@dataclass
class UPIMerchant:
    merchant_id:   str
    name:          str
    vpa:           str
    bank:          str
    mcc:           str
    city:          str
    state:         str
    is_high_risk:  bool = False


# ─── Pools ─────────────────────────────────────────────────────────────────────

class UPIUserPool:
    def __init__(self, num_users: int, fraud_user_ratio: float, seed: int = 42):
        random.seed(seed)
        np.random.seed(seed)

        n_fraud  = max(1, int(num_users * fraud_user_ratio))
        n_normal = num_users - n_fraud

        self.users:        List[UPIUser] = []
        self.normal_users: List[UPIUser] = []
        self.fraud_users:  List[UPIUser] = []

        for i in range(n_normal):
            u = self._make_user(f"U{i:06d}", is_fraudster=False)
            self.users.append(u)
            self.normal_users.append(u)

        for i in range(n_fraud):
            u = self._make_user(f"F{i:06d}", is_fraudster=True)
            self.users.append(u)
            self.fraud_users.append(u)

    def _make_user(self, uid: str, is_fraudster: bool) -> UPIUser:
        name   = _indian_name()
        handle = _weighted_choice(UPI_HANDLE_WEIGHTS)
        bank   = UPI_HANDLE_TO_BANK.get(handle, random.choice(INDIAN_BANKS))
        app    = _weighted_choice(UPI_APP_WEIGHTS)
        state  = random.choice(INDIAN_STATES)
        cities = STATE_TO_CITIES.get(state, ["Unknown"])
        city   = random.choice(cities)
        os_    = random.choice(["Android", "Android", "Android", "iOS"])

        return UPIUser(
            user_id        = uid,
            name           = name,
            vpa            = _make_vpa(name, handle),
            bank           = bank,
            handle         = handle,
            app            = app,
            device_id      = str(uuid.uuid4())[:12],
            device_os      = os_,
            city           = city,
            state          = state,
            account_type   = random.choices(
                ["SAVINGS", "CURRENT", "OD"], weights=[0.82, 0.14, 0.04]
            )[0],
            days_on_upi    = random.randint(30, 2500),
            avg_txn_amount = round(random.lognormvariate(6.0, 0.8), 2),  # ~₹400 avg
            is_fraudster   = is_fraudster,
        )


class UPIMerchantPool:
    def __init__(self, num_merchants: int, seed: int = 42):
        random.seed(seed)
        self.merchants: List[UPIMerchant] = []

        food_names    = ["Swiggy", "Zomato", "Dominos", "McDonald's", "KFC",
                         "Blinkit", "BigBasket", "JioMart", "Zepto", "Instamart"]
        utility_names = ["BESCOM", "MSEDCL", "TATA Power", "Airtel", "Jio",
                         "Vodafone Idea", "BSNL", "CESC", "TNEB", "BSES"]
        retail_names  = ["Myntra", "Meesho", "Nykaa", "Flipkart", "Amazon",
                         "Tata Cliq", "Reliance Digital", "Croma", "Snapdeal"]
        all_names     = food_names + utility_names + retail_names

        for i in range(num_merchants):
            name    = all_names[i % len(all_names)] if i < len(all_names) else f"Merchant_{i}"
            state   = random.choice(INDIAN_STATES)
            cities  = STATE_TO_CITIES.get(state, ["Unknown"])
            mcc     = random.choice(UPI_MERCHANT_MCC)

            self.merchants.append(UPIMerchant(
                merchant_id  = f"M{i:05d}",
                name         = name,
                vpa          = _make_merchant_vpa(name),
                bank         = random.choice(INDIAN_BANKS),
                mcc          = mcc,
                city         = random.choice(cities),
                state        = state,
                is_high_risk = mcc in ["4829", "6011", "6051"],
            ))

    def random_merchant(self) -> UPIMerchant:
        return random.choice(self.merchants)


# ─── Normal UPI Transaction Generator ─────────────────────────────────────────

class UPINormalGenerator:
    """Generates realistic everyday UPI transactions for non-fraudulent users."""

    def __init__(self, blueprint: Dict[str, Any],
                 user_pool: UPIUserPool, merchant_pool: UPIMerchantPool):
        self.bp        = blueprint
        self.users     = user_pool
        self.merchants = merchant_pool

        specs      = blueprint["Dataset_Specifications"]
        self.start = datetime.fromisoformat(specs["date_range_start"])
        self.end   = datetime.fromisoformat(specs["date_range_end"])

        # Amount params from blueprint (normal profile)
        prof          = blueprint.get("Normal_User_Profile", {})
        ta            = prof.get("transaction_amount", {})
        self.amt_min  = max(10.0, ta.get("min",  10.0))
        self.amt_max  = min(50000.0, ta.get("max", 5000.0))
        self.amt_mean = ta.get("mean", 450.0)
        self.amt_std  = ta.get("std", 380.0)

    def generate(self, target_n: int) -> pd.DataFrame:
        rows  = []
        users = self.users.normal_users or self.users.users
        if not users:
            return pd.DataFrame()

        per_user = max(1, target_n // len(users))
        attempts = 0

        while len(rows) < target_n and attempts < target_n * 3:
            user     = random.choice(users)
            n_txns   = max(1, np.random.poisson(per_user))
            for _ in range(n_txns):
                rows.append(self._make_row(user))
            attempts += 1
            if len(rows) >= target_n:
                break

        return pd.DataFrame(rows[:target_n])

    def _make_row(self, user: UPIUser) -> Dict:
        ts      = self._sample_ts(peak_start=9, peak_end=22, off_peak_w=0.08)
        is_merch = random.random() < 0.45
        merchant = self.merchants.random_merchant()

        # Transaction type
        txn_type = _weighted_choice(UPI_TXN_TYPE_WEIGHTS_NORMAL)

        # Receiver
        if is_merch:
            receiver_vpa  = merchant.vpa
            receiver_name = merchant.name
            receiver_bank = merchant.bank
            receiver_city = merchant.city
            receiver_state= merchant.state
            mcc           = merchant.mcc
            purpose_code  = "01"
        else:
            # P2P to another known user
            recv_users = [u for u in self.users.normal_users if u.user_id != user.user_id]
            receiver   = random.choice(recv_users) if recv_users else user
            receiver_vpa  = receiver.vpa
            receiver_name = receiver.name
            receiver_bank = receiver.bank
            receiver_city = receiver.city
            receiver_state= receiver.state
            mcc           = ""
            purpose_code  = random.choice(["00", "07", "08", "09"])

        purpose_desc = UPI_PURPOSE_CODES.get(purpose_code, "Personal Transfer")
        remarks_pool = REMARKS_BY_PURPOSE.get(purpose_desc, ["Payment"])
        remark       = random.choice(remarks_pool)
        if purpose_code == "01":
            remark = f"Order #{random.randint(100000, 999999)}"

        amount = self._sample_amount()
        cross_state = int(user.state != receiver_state)
        hour_  = ts.hour
        off_hr = int(hour_ >= 23 or hour_ < 6)

        # Normal: very low velocity, known VPAs
        return {
            "txn_id":               _txn_id(),
            "upi_ref_id":           _upi_ref_id(ts),
            "timestamp":            ts.strftime("%Y-%m-%d %H:%M:%S"),
            "hour_of_day":          hour_,
            "day_of_week":          ts.weekday(),
            "is_weekend":           int(ts.weekday() >= 5),
            "is_off_hours":         off_hr,
            "sender_vpa":           user.vpa,
            "receiver_vpa":         receiver_vpa,
            "sender_name":          user.name,
            "receiver_name":        receiver_name,
            "sender_bank":          user.bank,
            "receiver_bank":        receiver_bank,
            "sender_account_type":  user.account_type,
            "amount":               amount,
            "currency":             "INR",
            "txn_type":             txn_type,
            "txn_status":           random.choices(
                                        [UPI_SUCCESS, UPI_FAILED],
                                        weights=[0.93, 0.07])[0],
            "failure_code":         "",
            "purpose_code":         purpose_code,
            "purpose_description":  purpose_desc,
            "remarks":              remark,
            "mcc":                  mcc,
            "is_merchant_payment":  int(is_merch),
            "upi_app":              user.app,
            "device_id":            user.device_id,
            "device_os":            user.device_os,
            "os_version":           _os_version(user.device_os),
            "app_version":          _app_version(user.app),
            "ip_address":           _indian_ip(),
            "is_new_device":        0,
            "is_vpn_or_proxy":      0,
            "sender_city":          user.city,
            "sender_state":         user.state,
            "receiver_city":        receiver_city,
            "receiver_state":       receiver_state,
            "cross_state_flag":     cross_state,
            "sender_velocity_1h":   random.randint(0, 2),
            "sender_velocity_24h":  random.randint(1, 6),
            "failed_attempts_before": 0,
            "is_new_vpa":           0,
            "is_first_txn_to_vpa":  int(random.random() < 0.15),
            "collect_requests_1h":  0,
            "amount_deviation_pct": _amount_deviation(amount, user.avg_txn_amount),
            "is_high_value":        int(amount > 10000),
            "is_round_amount":      int(amount % 100 == 0),
            "days_since_upi_reg":   user.days_on_upi,
            "receiver_fraud_score": round(random.uniform(0.0, 0.05), 3),
            "fraud_label":          0,
            "fraud_type":           "",
        }

    def _sample_ts(self, peak_start=9, peak_end=22, off_peak_w=0.1) -> datetime:
        delta = (self.end - self.start).total_seconds()
        ts    = self.start + timedelta(seconds=random.uniform(0, delta))
        if random.random() > off_peak_w:
            ts = ts.replace(
                hour=random.randint(peak_start, peak_end),
                minute=random.randint(0, 59),
                second=random.randint(0, 59),
            )
        return ts

    def _sample_amount(self) -> float:
        v = np.random.lognormal(
            mean=np.log(max(self.amt_mean, 1)) - 0.5 * (self.amt_std / max(self.amt_mean, 1)) ** 2,
            sigma=max(0.1, self.amt_std / max(self.amt_mean, 1)),
        )
        return round(float(max(self.amt_min, min(self.amt_max, v))), 2)


# ─── Fraud Injector ────────────────────────────────────────────────────────────

class UPIFraudInjector:
    """
    Generates UPI transactions that exhibit realistic fraud-specific signals.

    Three hardcoded pattern generators — each uses behaviorally accurate
    distributions derived from real UPI fraud reports:

      collect_scam     — rapid collect requests, new VPA, failed attempts
      mule_chain       — layered fund forwarding across accounts
      credential_fraud — stolen OTP/PIN, new device, high value, off-hours
    """

    def __init__(self, blueprint: Dict[str, Any],
                 user_pool: UPIUserPool, merchant_pool: UPIMerchantPool):
        self.bp        = blueprint
        self.users     = user_pool
        self.merchants = merchant_pool

        specs      = blueprint["Dataset_Specifications"]
        self.start = datetime.fromisoformat(specs["date_range_start"])
        self.end   = datetime.fromisoformat(specs["date_range_end"])

        # Identify scenario from blueprint name (drives pattern weights)
        self.scenario = blueprint.get("Fraud_Scenario_Name", "").lower()

        # Per-scenario default pattern weights
        self._pattern_weights = self._derive_pattern_weights()

        # Extract per-pattern params from blueprint Fraud_Patterns so the
        # injector respects the LLM-filled values (amount, timing, velocity).
        self._bp_patterns: Dict[str, Dict] = {}
        for pat in blueprint.get("Fraud_Patterns", []):
            pname = pat.get("pattern_name", "").lower()
            self._bp_patterns[pname] = pat.get("params", {})

    def _derive_pattern_weights(self) -> Dict[str, float]:
        s = self.scenario
        if "collect" in s:
            return {"collect_scam": 0.80, "mule_chain": 0.10, "credential_fraud": 0.10}
        if "mule" in s:
            return {"collect_scam": 0.10, "mule_chain": 0.75, "credential_fraud": 0.15}
        if "credential" in s or "account takeover" in s or "takeover" in s:
            return {"collect_scam": 0.10, "mule_chain": 0.20, "credential_fraud": 0.70}
        # Default UPI fraud: mix of all three
        return {"collect_scam": 0.45, "mule_chain": 0.30, "credential_fraud": 0.25}

    def _get_pattern_params(self, keyword: str) -> Dict:
        """Return blueprint params for the first pattern whose name contains keyword."""
        for name, params in self._bp_patterns.items():
            if keyword in name:
                return params
        return {}

    def generate(self, target_n: int) -> pd.DataFrame:
        rows       = []
        patterns   = list(self._pattern_weights.keys())
        weights    = list(self._pattern_weights.values())
        fraud_users = self.users.fraud_users or self.users.users[:max(1, len(self.users.users)//10)]

        attempts = 0
        while len(rows) < target_n and attempts < target_n * 4:
            user    = random.choice(fraud_users)
            pattern = random.choices(patterns, weights=weights, k=1)[0]

            if pattern == "collect_scam":
                batch = self._collect_scam(user)
            elif pattern == "mule_chain":
                batch = self._mule_chain(user)
            else:
                batch = self._credential_fraud(user)

            rows.extend(batch)
            attempts += 1

        return pd.DataFrame(rows[:target_n])

    # ── Pattern 1: UPI Collect Scam ──────────────────────────────────────────
    # Fraudster sends rapid collect requests to victim posing as bank/refund.
    # Pattern: 3-8 requests in 15-30 min window, 7pm-11pm, ₹200-₹1200.
    # 0-3 failures (USER_DECLINED) before victim approves. New receiver VPA.
    # ALL rows labeled fraud=1 (failed attempts are still part of the attack).

    def _collect_scam(self, victim: UPIUser) -> List[Dict]:
        rows = []

        # Read blueprint-derived params (fall back to user-scenario defaults)
        bp = self._get_pattern_params("collect")

        n_requests = random.randint(
            max(3, int(bp.get("burst_min_txns", 3))),
            max(3, min(8, int(bp.get("burst_max_txns", 8)))),
        )
        window_secs = int(bp.get("burst_window_mins", 20)) * 60  # 15-30 min spread

        # Amount: ₹200-₹1200 per user scenario spec
        amt_min = max(200.0, float(bp.get("amount_min", 200)))
        amt_max = min(1200.0, float(bp.get("amount_max", 1200)))
        if amt_min >= amt_max:
            amt_min, amt_max = 200.0, 1200.0

        # Preferred hours: 7pm-11pm (19-23)
        pref_hours = bp.get("preferred_hours", list(range(19, 24)))
        if isinstance(pref_hours, list) and len(pref_hours) == 2:
            pref_hours = list(range(int(pref_hours[0]), int(pref_hours[1]) + 1))
        if not isinstance(pref_hours, list) or not pref_hours:
            pref_hours = list(range(19, 24))

        anchor      = self._sample_ts(preferred_hours=pref_hours)
        fraud_name  = _indian_name()
        fraud_handle = random.choice(["paytm", "ybl", "okicici", "apl"])
        fraud_vpa   = _make_vpa(fraud_name, fraud_handle)
        fraud_bank  = UPI_HANDLE_TO_BANK.get(fraud_handle, random.choice(INDIAN_BANKS))
        fraud_city  = random.choice(["Unknown", "Bengaluru", "Mumbai", "Delhi"])
        fraud_state = random.choice(INDIAN_STATES)

        # All requests in a batch use the same amount (realistic: scammer asks same amount)
        amount = round(random.uniform(amt_min, amt_max), 2)

        # Some initial requests may be declined/timeout before victim accepts
        n_fail = random.randint(0, min(3, n_requests - 1))

        remark_pool = [
            "Refund from last order", "Cashback credited", "Lucky draw prize",
            "Payment reversal", "Gift from family", "Survey reward",
            "Electricity refund", "Govt subsidy", "Reimbursement",
        ]

        for i in range(n_requests):
            # Spread requests evenly across the 15-30 min window
            seg_start = (i / n_requests) * window_secs
            seg_end   = ((i + 1) / n_requests) * window_secs
            ts = anchor + timedelta(seconds=random.uniform(seg_start, seg_end))

            is_failed  = (i < n_fail)
            status     = UPI_FAILED if is_failed else UPI_SUCCESS
            failure_cd = random.choice(
                ["USER_DECLINED", "TRANSACTION_TIMEOUT", "WRONG_UPI_PIN"]
            ) if is_failed else ""

            # Progressive signals — velocity grows as more requests arrive
            cur_velocity_1h   = i + 1
            cur_collect_1h    = i + 1
            failed_before     = min(i, n_fail)   # failures seen BEFORE current request

            rows.append({
                "txn_id":               _txn_id(),
                "upi_ref_id":           _upi_ref_id(ts),
                "timestamp":            ts.strftime("%Y-%m-%d %H:%M:%S"),
                "hour_of_day":          ts.hour,
                "day_of_week":          ts.weekday(),
                "is_weekend":           int(ts.weekday() >= 5),
                "is_off_hours":         int(ts.hour >= 23 or ts.hour < 6),
                "sender_vpa":           victim.vpa,
                "receiver_vpa":         fraud_vpa,
                "sender_name":          victim.name,
                "receiver_name":        fraud_name,
                "sender_bank":          victim.bank,
                "receiver_bank":        fraud_bank,
                "sender_account_type":  victim.account_type,
                "amount":               amount,
                "currency":             "INR",
                "txn_type":             "COLLECT_REQUEST",
                "txn_status":           status,
                "failure_code":         failure_cd,
                "purpose_code":         "00",
                "purpose_description":  "Personal Transfer",
                "remarks":              random.choice(remark_pool),
                "mcc":                  "",
                "is_merchant_payment":  0,
                "upi_app":              victim.app,
                "device_id":            victim.device_id,
                "device_os":            victim.device_os,
                "os_version":           _os_version(victim.device_os),
                "app_version":          _app_version(victim.app),
                "ip_address":           _indian_ip(),
                "is_new_device":        0,
                "is_vpn_or_proxy":      0,
                "sender_city":          victim.city,
                "sender_state":         victim.state,
                "receiver_city":        fraud_city,
                "receiver_state":       fraud_state,
                "cross_state_flag":     int(victim.state != fraud_state),
                "sender_velocity_1h":   cur_velocity_1h,
                "sender_velocity_24h":  cur_velocity_1h + random.randint(2, 8),
                "failed_attempts_before": failed_before,
                "is_new_vpa":           1,
                "is_first_txn_to_vpa":  1,
                "collect_requests_1h":  cur_collect_1h,
                "amount_deviation_pct": _amount_deviation(amount, victim.avg_txn_amount),
                "is_high_value":        int(amount > 10000),
                "is_round_amount":      int(amount % 100 == 0),
                "days_since_upi_reg":   victim.days_on_upi,
                "receiver_fraud_score": round(random.uniform(0.70, 0.98), 3),
                # All collect scam rows are fraud — failed attempts are still part of the attack
                "fraud_label":          1,
                "fraud_type":           "UPI Collect Scam",
            })

        return rows

    # ── Pattern 2: UPI Mule Chain ─────────────────────────────────────────────
    # Fraudulently obtained funds move through 3-6 mule accounts.
    # Each hop forwards ~90-97% of received amount within 1-4 hours.
    # Different banks per hop. is_first_txn_to_vpa=1 for every hop.

    def _mule_chain(self, origin: UPIUser) -> List[Dict]:
        rows   = []
        bp     = self._get_pattern_params("mule")
        n_hops = random.randint(
            max(3, int(bp.get("burst_min_txns", 3))),
            max(3, min(6, int(bp.get("burst_max_txns", 6)))),
        )
        amt_min = float(bp.get("amount_min", 500))
        amt_max = float(bp.get("amount_max", 5000))
        amount  = round(random.uniform(amt_min, max(amt_min + 1, amt_max)), 2)

        pref_hours = bp.get("preferred_hours", list(range(22, 24)) + list(range(0, 5)))
        if isinstance(pref_hours, list) and len(pref_hours) == 2:
            pref_hours = list(range(int(pref_hours[0]), int(pref_hours[1]) + 1))
        if not isinstance(pref_hours, list) or not pref_hours:
            pref_hours = list(range(22, 24)) + list(range(0, 5))

        anchor = self._sample_ts(preferred_hours=pref_hours)

        # Build a chain of mule VPAs (different handles per hop for realism)
        mule_handles  = random.sample(list(UPI_HANDLE_WEIGHTS.keys()), min(n_hops, len(UPI_HANDLE_WEIGHTS)))
        mule_names    = [_indian_name() for _ in range(n_hops)]
        mule_vpas     = [_make_vpa(mule_names[i], mule_handles[i % len(mule_handles)])
                         for i in range(n_hops)]
        mule_banks    = [UPI_HANDLE_TO_BANK.get(mule_handles[i % len(mule_handles)],
                         random.choice(INDIAN_BANKS)) for i in range(n_hops)]
        mule_states   = [random.choice(INDIAN_STATES) for _ in range(n_hops)]
        mule_cities   = [random.choice(STATE_TO_CITIES.get(s, ["Unknown"])) for s in mule_states]

        sender_vpa   = origin.vpa
        sender_name  = origin.name
        sender_bank  = origin.bank
        sender_city  = origin.city
        sender_state = origin.state
        cur_ts       = anchor

        for hop in range(n_hops):
            receiver_vpa   = mule_vpas[hop]
            receiver_name  = mule_names[hop]
            receiver_bank  = mule_banks[hop]
            receiver_city  = mule_cities[hop]
            receiver_state = mule_states[hop]

            rows.append({
                "txn_id":               _txn_id(),
                "upi_ref_id":           _upi_ref_id(cur_ts),
                "timestamp":            cur_ts.strftime("%Y-%m-%d %H:%M:%S"),
                "hour_of_day":          cur_ts.hour,
                "day_of_week":          cur_ts.weekday(),
                "is_weekend":           int(cur_ts.weekday() >= 5),
                "is_off_hours":         int(cur_ts.hour >= 23 or cur_ts.hour < 6),
                "sender_vpa":           sender_vpa,
                "receiver_vpa":         receiver_vpa,
                "sender_name":          sender_name,
                "receiver_name":        receiver_name,
                "sender_bank":          sender_bank,
                "receiver_bank":        receiver_bank,
                "sender_account_type":  "SAVINGS",
                "amount":               round(amount, 2),
                "currency":             "INR",
                "txn_type":             "PUSH_PAY",
                "txn_status":           UPI_SUCCESS,
                "failure_code":         "",
                "purpose_code":         "00",
                "purpose_description":  "Personal Transfer",
                "remarks":              random.choice(["Transfer", "Payment", "Settlement",
                                                       "Return amount", "Advance", "Dues"]),
                "mcc":                  "",
                "is_merchant_payment":  0,
                "upi_app":              origin.app,
                "device_id":            str(uuid.uuid4())[:12] if hop == 0 else str(uuid.uuid4())[:12],
                "device_os":            random.choice(["Android", "Android", "iOS"]),
                "os_version":           random.choice(["Android 13", "Android 14", "iOS 17"]),
                "app_version":          _app_version(random.choice(["PhonePe", "GPay", "Paytm"])),
                "ip_address":           _suspicious_ip() if random.random() < 0.4 else _indian_ip(),
                "is_new_device":        1,
                "is_vpn_or_proxy":      int(random.random() < 0.35),
                "sender_city":          sender_city,
                "sender_state":         sender_state,
                "receiver_city":        receiver_city,
                "receiver_state":       receiver_state,
                "cross_state_flag":     int(sender_state != receiver_state),
                "sender_velocity_1h":   random.randint(2, 8),
                "sender_velocity_24h":  random.randint(3, 15),
                "failed_attempts_before": 0,
                "is_new_vpa":           int(random.random() < 0.70),
                "is_first_txn_to_vpa":  1,
                "collect_requests_1h":  0,
                "amount_deviation_pct": random.uniform(150, 800),   # far above user avg
                "is_high_value":        int(amount > 10000),
                "is_round_amount":      int(amount % 100 == 0),
                "days_since_upi_reg":   random.randint(1, 30),      # recently registered
                "receiver_fraud_score": round(random.uniform(0.55, 0.90), 3),
                "fraud_label":          1,
                "fraud_type":           "UPI Mule Transfer",
            })

            # Next hop: forward 90-97% of received amount
            amount       = round(amount * random.uniform(0.90, 0.97), 2)
            sender_vpa   = receiver_vpa
            sender_name  = receiver_name
            sender_bank  = receiver_bank
            sender_city  = receiver_city
            sender_state = receiver_state
            cur_ts      += timedelta(hours=random.uniform(0.5, 4.0))

        return rows

    # ── Pattern 3: UPI Credential Fraud ──────────────────────────────────────
    # Attacker has stolen UPI credentials (via OTP phishing / SIM swap).
    # Signs: new device, suspicious IP, high-value transfers, 2-5am.

    def _credential_fraud(self, user: UPIUser) -> List[Dict]:
        rows        = []
        bp          = self._get_pattern_params("credential")
        n_txns      = random.randint(
            max(1, int(bp.get("burst_min_txns", 1))),
            max(1, min(4, int(bp.get("burst_max_txns", 4)))),
        )
        pref_hours  = bp.get("preferred_hours", list(range(2, 6)))
        if isinstance(pref_hours, list) and len(pref_hours) == 2:
            pref_hours = list(range(int(pref_hours[0]), int(pref_hours[1]) + 1))
        if not isinstance(pref_hours, list) or not pref_hours:
            pref_hours = list(range(2, 6))

        anchor      = self._sample_ts(preferred_hours=pref_hours)
        new_device  = str(uuid.uuid4())[:12]
        attacker_ip = _suspicious_ip()

        amt_min = float(bp.get("amount_min", 2000))
        amt_max = float(bp.get("amount_max", 49000))

        for i in range(n_txns):
            ts     = anchor + timedelta(minutes=random.uniform(i * 5, i * 15 + 10))
            amount = round(random.uniform(amt_min, max(amt_min + 1, amt_max)), 2)

            # Mule receiver
            recv_handle  = random.choice(["paytm", "ybl", "okicici"])
            recv_name    = _indian_name()
            recv_vpa     = _make_vpa(recv_name, recv_handle)
            recv_bank    = UPI_HANDLE_TO_BANK.get(recv_handle, "Unknown Bank")
            recv_state   = random.choice(INDIAN_STATES)
            recv_city    = random.choice(STATE_TO_CITIES.get(recv_state, ["Unknown"]))

            rows.append({
                "txn_id":               _txn_id(),
                "upi_ref_id":           _upi_ref_id(ts),
                "timestamp":            ts.strftime("%Y-%m-%d %H:%M:%S"),
                "hour_of_day":          ts.hour,
                "day_of_week":          ts.weekday(),
                "is_weekend":           int(ts.weekday() >= 5),
                "is_off_hours":         1,                   # always off-hours
                "sender_vpa":           user.vpa,
                "receiver_vpa":         recv_vpa,
                "sender_name":          user.name,
                "receiver_name":        recv_name,
                "sender_bank":          user.bank,
                "receiver_bank":        recv_bank,
                "sender_account_type":  user.account_type,
                "amount":               amount,
                "currency":             "INR",
                "txn_type":             random.choice(["PUSH_PAY", "COLLECT_REQUEST"]),
                "txn_status":           UPI_SUCCESS,
                "failure_code":         "",
                "purpose_code":         "00",
                "purpose_description":  "Personal Transfer",
                "remarks":              random.choice(["Urgent payment", "Transfer",
                                                       "Settlement", "Return"]),
                "mcc":                  "",
                "is_merchant_payment":  0,
                "upi_app":              user.app,
                "device_id":            new_device,          # attacker's device
                "device_os":            random.choice(["Android", "Android", "iOS"]),
                "os_version":           random.choice(["Android 13", "Android 14", "iOS 17"]),
                "app_version":          _app_version(user.app),
                "ip_address":           attacker_ip,
                "is_new_device":        1,
                "is_vpn_or_proxy":      int(random.random() < 0.55),
                "sender_city":          user.city,
                "sender_state":         user.state,
                "receiver_city":        recv_city,
                "receiver_state":       recv_state,
                "cross_state_flag":     int(user.state != recv_state),
                "sender_velocity_1h":   n_txns,
                "sender_velocity_24h":  n_txns + random.randint(0, 3),
                "failed_attempts_before": random.randint(0, 2),
                "is_new_vpa":           int(random.random() < 0.80),
                "is_first_txn_to_vpa":  1,
                "collect_requests_1h":  0,
                "amount_deviation_pct": _amount_deviation(amount, user.avg_txn_amount),
                "is_high_value":        1,
                "is_round_amount":      int(amount % 100 == 0),
                "days_since_upi_reg":   user.days_on_upi,
                "receiver_fraud_score": round(random.uniform(0.65, 0.95), 3),
                "fraud_label":          1,
                "fraud_type":           "UPI Credential Fraud",
            })

        return rows

    def _sample_ts(self, preferred_hours: Optional[List[int]] = None) -> datetime:
        delta = (self.end - self.start).total_seconds()
        ts    = self.start + timedelta(seconds=random.uniform(0, delta))
        if preferred_hours:
            ts = ts.replace(
                hour=random.choice(preferred_hours),
                minute=random.randint(0, 59),
                second=random.randint(0, 59),
            )
        return ts


# ─── Top-level UPI Engine ──────────────────────────────────────────────────────

class UPIDatasetEngine:
    """
    Orchestrates UPI dataset generation from a blueprint.
    Called by DatasetEngine when fraud_category == "upi".
    """

    def __init__(self, blueprint: Dict[str, Any], seed: int = 42):
        self.bp   = blueprint
        self.seed = seed
        random.seed(seed)
        np.random.seed(seed)

    def generate(self) -> pd.DataFrame:
        specs         = self.bp["Dataset_Specifications"]
        total_rows    = specs["total_rows"]
        fraud_ratio   = specs["fraud_ratio"]
        num_users     = specs.get("num_users", max(100, total_rows // 8))
        inj_rules     = self.bp.get("Fraud_Injection_Rules", {})

        n_fraud  = int(total_rows * fraud_ratio)
        n_normal = total_rows - n_fraud

        fraud_user_ratio = inj_rules.get("fraud_user_ratio", 0.10)

        user_pool     = UPIUserPool(num_users, fraud_user_ratio, seed=self.seed)
        merchant_pool = UPIMerchantPool(max(50, num_users // 5), seed=self.seed)

        normal_gen = UPINormalGenerator(self.bp, user_pool, merchant_pool)
        normal_df  = normal_gen.generate(n_normal)

        fraud_inj  = UPIFraudInjector(self.bp, user_pool, merchant_pool)
        fraud_df   = fraud_inj.generate(n_fraud)

        df = pd.concat([normal_df, fraud_df], ignore_index=True)
        df = df.sample(frac=1, random_state=self.seed).reset_index(drop=True)
        df = df.sort_values("timestamp").reset_index(drop=True)
        df = df.head(total_rows)

        # Fix failure_code for FAILED rows that have empty code
        mask_fail = (df["txn_status"] == UPI_FAILED) & (df["failure_code"] == "")
        df.loc[mask_fail, "failure_code"] = random.choice(UPI_FAILURE_CODES)

        # Enforce types
        df = self._enforce_types(df)
        return df

    def _enforce_types(self, df: pd.DataFrame) -> pd.DataFrame:
        int_cols = [
            "hour_of_day", "day_of_week", "is_weekend", "is_off_hours",
            "is_merchant_payment", "is_new_device", "is_vpn_or_proxy",
            "cross_state_flag", "sender_velocity_1h", "sender_velocity_24h",
            "failed_attempts_before", "is_new_vpa", "is_first_txn_to_vpa",
            "collect_requests_1h", "is_high_value", "is_round_amount",
            "days_since_upi_reg", "fraud_label",
        ]
        float_cols = ["amount", "amount_deviation_pct", "receiver_fraud_score"]

        for c in int_cols:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0).astype(int)
        for c in float_cols:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0.0).astype(float)

        # Ensure all expected columns exist (fill missing with sensible defaults)
        for col in UPI_COLUMN_NAMES:
            if col not in df.columns:
                df[col] = "" if col in ("failure_code", "mcc", "fraud_type") else 0

        return df[UPI_COLUMN_NAMES]
