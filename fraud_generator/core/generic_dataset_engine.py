"""
core/generic_dataset_engine.py
Generic fraud dataset generator for non-card, non-UPI scenarios.

Covers: money laundering, phishing, synthetic identity, friendly fraud,
triangulation fraud, refund abuse, identity theft, corporate card abuse.

Each fraud pattern uses hardcoded realistic behavioral signals:
  money_laundering    — structuring below reporting threshold, network pattern
  phishing            — legitimate-looking amounts, victim device, unusual recipient
  synthetic_identity  — slow credit build-up then bust-out
  friendly_fraud      — normal retail amounts, disputed after delivery
  triangulation       — burst of CNP transactions at multiple merchants
  generic             — fallback for any unknown scenario

Called by DatasetEngine when blueprint["fraud_category"] == "other".
"""

from __future__ import annotations

import random
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from schemas.generic_fraud_schema import (
    BROWSER_LIST,
    CARD_TYPES,
    CHANNELS,
    COUNTRIES,
    CURRENCIES,
    CURRENCY_WEIGHTS,
    DEVICE_OS_LIST,
    DEVICE_TYPES,
    GENERIC_COLUMN_NAMES,
    GENERIC_MERCHANT_CATEGORIES,
    HIGH_RISK_COUNTRIES,
    HIGH_RISK_MCCS,
    MCC_TO_CATEGORY,
    MERCHANT_NAMES_BY_CATEGORY,
    SCENARIO_MCC_MAP,
)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _weighted_choice(weights: Dict[str, float]) -> str:
    keys  = list(weights.keys())
    probs = list(weights.values())
    total = sum(probs)
    probs = [p / total for p in probs]
    return random.choices(keys, weights=probs, k=1)[0]


def _txn_id() -> str:
    return str(uuid.uuid4())


def _ip(foreign: bool = False) -> str:
    if foreign:
        return f"{random.randint(1,223)}.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(1,254)}"
    prefixes = ["192.168", "10.0", "172.16", "98.34", "76.191"]
    return f"{random.choice(prefixes)}.{random.randint(0,255)}.{random.randint(1,254)}"


def _card_last4() -> str:
    return str(random.randint(1000, 9999))


def _sample_amount(mn: float, mx: float, mean: float, std: float,
                   dist: str = "lognormal") -> float:
    if dist == "lognormal":
        sigma = max(0.05, std / max(mean, 1))
        mu    = np.log(max(mean, 1)) - 0.5 * sigma ** 2
        v     = np.random.lognormal(mu, sigma)
    elif dist == "uniform":
        v = np.random.uniform(mn, mx)
    else:
        v = np.random.normal(mean, std)
    return round(float(max(mn, min(mx, v))), 2)


def _merchant_for_category(category: str) -> tuple:
    """Return (merchant_name, mcc) for a category."""
    mcc_pool = [mcc for mcc, cat in MCC_TO_CATEGORY.items() if cat == category]
    if not mcc_pool:
        mcc_pool = ["5999"]
    mcc        = random.choice(mcc_pool)
    names      = MERCHANT_NAMES_BY_CATEGORY.get(category, ["MerchantCo"])
    name       = random.choice(names)
    return name, mcc


# ─── Data Classes ──────────────────────────────────────────────────────────────

@dataclass
class GenericUser:
    user_id:        str
    billing_country:str
    card_type:      str
    card_last4:     str
    device_id:      str
    device_type:    str
    device_os:      str
    avg_amount:     float
    account_age:    int
    is_fraudster:   bool = False


@dataclass
class GenericMerchant:
    merchant_id:  str
    name:         str
    category:     str
    country:      str
    mcc:          str
    is_high_risk: bool


# ─── Pools ────────────────────────────────────────────────────────────────────

class GenericUserPool:
    def __init__(self, num_users: int, fraud_user_ratio: float, seed: int = 42):
        random.seed(seed)
        np.random.seed(seed)

        n_fraud  = max(1, int(num_users * fraud_user_ratio))
        n_normal = num_users - n_fraud

        self.users:        List[GenericUser] = []
        self.normal_users: List[GenericUser] = []
        self.fraud_users:  List[GenericUser] = []

        for i in range(n_normal):
            u = self._make_user(f"U{i:06d}", is_fraudster=False)
            self.users.append(u)
            self.normal_users.append(u)

        for i in range(n_fraud):
            u = self._make_user(f"F{i:06d}", is_fraudster=True)
            self.users.append(u)
            self.fraud_users.append(u)

    def _make_user(self, uid: str, is_fraudster: bool) -> GenericUser:
        country = _weighted_choice(CURRENCY_WEIGHTS)  # reuse currency country proxy
        country_map = {"USD": "US", "EUR": "DE", "GBP": "GB", "INR": "IN",
                       "AUD": "AU", "CAD": "CA", "SGD": "SG", "AED": "AE",
                       "MXN": "MX", "BRL": "BR"}
        billing_country = country_map.get(country, "US")
        device_type     = random.choices(
            ["MOBILE", "DESKTOP", "TABLET"], weights=[0.55, 0.35, 0.10]
        )[0]
        device_os = random.choice(DEVICE_OS_LIST)

        return GenericUser(
            user_id         = uid,
            billing_country = billing_country,
            card_type       = random.choices(
                CARD_TYPES, weights=[0.45, 0.40, 0.10, 0.05]
            )[0],
            card_last4      = _card_last4(),
            device_id       = str(uuid.uuid4())[:12],
            device_type     = device_type,
            device_os       = device_os,
            avg_amount      = round(_sample_amount(10, 5000, 150, 200), 2),
            account_age     = random.randint(30, 3000),
            is_fraudster    = is_fraudster,
        )


class GenericMerchantPool:
    def __init__(self, num_merchants: int, mcc_pool: List[str], seed: int = 42):
        random.seed(seed)
        self.merchants: List[GenericMerchant] = []

        categories = GENERIC_MERCHANT_CATEGORIES
        countries  = [c for c in COUNTRIES if c not in HIGH_RISK_COUNTRIES]

        for i in range(num_merchants):
            cat  = random.choice(categories)
            name, mcc = _merchant_for_category(cat)
            if mcc_pool and random.random() < 0.4:
                mcc = random.choice(mcc_pool)
                cat = MCC_TO_CATEGORY.get(mcc, cat)

            self.merchants.append(GenericMerchant(
                merchant_id  = f"M{i:05d}",
                name         = name,
                category     = cat,
                country      = random.choice(countries),
                mcc          = mcc,
                is_high_risk = mcc in HIGH_RISK_MCCS,
            ))

    def random_merchant(self, high_risk: bool = False) -> GenericMerchant:
        if high_risk:
            pool = [m for m in self.merchants if m.is_high_risk]
            if pool:
                return random.choice(pool)
        return random.choice(self.merchants)


# ─── Normal Generator ─────────────────────────────────────────────────────────

class GenericNormalGenerator:
    def __init__(self, blueprint: Dict[str, Any],
                 user_pool: GenericUserPool, merchant_pool: GenericMerchantPool):
        self.bp        = blueprint
        self.users     = user_pool
        self.merchants = merchant_pool

        specs         = blueprint["Dataset_Specifications"]
        self.start    = datetime.fromisoformat(specs["date_range_start"])
        self.end      = datetime.fromisoformat(specs["date_range_end"])
        prof          = blueprint.get("Normal_User_Profile", {})
        ta            = prof.get("transaction_amount", {})
        self.amt_min  = max(1.0,    ta.get("min",  1.0))
        self.amt_max  = min(100000, ta.get("max",  5000.0))
        self.amt_mean = ta.get("mean", 150.0)
        self.amt_std  = ta.get("std",  200.0)

    def generate(self, target_n: int) -> pd.DataFrame:
        rows  = []
        users = self.users.normal_users or self.users.users
        if not users:
            return pd.DataFrame()

        attempts = 0
        while len(rows) < target_n and attempts < target_n * 3:
            user = random.choice(users)
            rows.append(self._make_row(user))
            attempts += 1

        return pd.DataFrame(rows[:target_n])

    def _make_row(self, user: GenericUser) -> Dict:
        ts       = self._sample_ts(peak_start=8, peak_end=22)
        merchant = self.merchants.random_merchant()
        currency = _weighted_choice(CURRENCY_WEIGHTS)
        amount   = _sample_amount(self.amt_min, self.amt_max, self.amt_mean, self.amt_std)
        channel  = random.choices(
            ["ONLINE", "POS", "MOBILE_APP"],
            weights=[0.50, 0.30, 0.20]
        )[0]

        return {
            "txn_id":                  _txn_id(),
            "timestamp":               ts.strftime("%Y-%m-%d %H:%M:%S"),
            "hour_of_day":             ts.hour,
            "day_of_week":             ts.weekday(),
            "is_weekend":              int(ts.weekday() >= 5),
            "is_off_hours":            int(ts.hour < 8 or ts.hour >= 22),
            "user_id":                 user.user_id,
            "account_age_days":        user.account_age,
            "card_type":               user.card_type,
            "card_last4":              user.card_last4,
            "billing_country":         user.billing_country,
            "amount":                  amount,
            "currency":                currency,
            "channel":                 channel,
            "is_round_amount":         int(amount % 100 == 0),
            "is_high_value":           int(amount > user.avg_amount * 3),
            "merchant_id":             merchant.merchant_id,
            "merchant_name":           merchant.name,
            "merchant_category":       merchant.category,
            "merchant_country":        merchant.country,
            "mcc":                     merchant.mcc,
            "is_high_risk_merchant":   int(merchant.is_high_risk),
            "device_id":               user.device_id,
            "device_type":             user.device_type,
            "device_os":               user.device_os,
            "browser":                 random.choice(BROWSER_LIST) if channel == "ONLINE" else "",
            "ip_address":              _ip(foreign=False),
            "ip_country":              user.billing_country,
            "is_new_device":           0,
            "is_foreign_ip":           0,
            "is_vpn_or_proxy":         0,
            "shipping_country":        user.billing_country,
            "shipping_billing_mismatch": 0,
            "is_first_time_merchant":  int(random.random() < 0.10),
            "velocity_1h":             random.randint(0, 2),
            "velocity_24h":            random.randint(1, 6),
            "amount_vs_user_avg":      round(amount / max(user.avg_amount, 1), 3),
            "failed_auth_attempts":    0,
            "cross_border_flag":       int(user.billing_country != merchant.country),
            "days_since_last_txn":     random.randint(0, 14),
            "fraud_label":             0,
            "fraud_type":              "",
        }

    def _sample_ts(self, peak_start=8, peak_end=22) -> datetime:
        delta = (self.end - self.start).total_seconds()
        ts    = self.start + timedelta(seconds=random.uniform(0, delta))
        if random.random() > 0.1:
            ts = ts.replace(
                hour=random.randint(peak_start, peak_end),
                minute=random.randint(0, 59),
                second=random.randint(0, 59),
            )
        return ts


# ─── Fraud Injector ────────────────────────────────────────────────────────────

class GenericFraudInjector:
    """
    Realistic fraud patterns for non-card, non-UPI scenarios.
    Each pattern generator hardcodes the behavioral signals that actually
    distinguish it from normal transactions.
    """

    _PATTERN_DISPATCH = {
        "money laundering":   "_money_laundering",
        "phishing":           "_phishing",
        "synthetic identity": "_synthetic_identity",
        "friendly fraud":     "_friendly_fraud",
        "triangulation":      "_triangulation",
        "identity fraud":     "_identity_fraud",
        "refund fraud":       "_refund_fraud",
        "corporate card":     "_corporate_card",
    }

    def __init__(self, blueprint: Dict[str, Any],
                 user_pool: GenericUserPool, merchant_pool: GenericMerchantPool):
        self.bp        = blueprint
        self.users     = user_pool
        self.merchants = merchant_pool

        specs      = blueprint["Dataset_Specifications"]
        self.start = datetime.fromisoformat(specs["date_range_start"])
        self.end   = datetime.fromisoformat(specs["date_range_end"])

        self.scenario   = blueprint.get("Fraud_Scenario_Name", "").lower()
        self.patterns   = self._resolve_patterns()

    def _resolve_patterns(self) -> List[str]:
        s = self.scenario
        for key in self._PATTERN_DISPATCH:
            if key in s:
                return [key]
        return ["money laundering", "phishing", "synthetic identity"]

    def generate(self, target_n: int) -> pd.DataFrame:
        rows       = []
        fraud_users = self.users.fraud_users or self.users.users[:max(1, len(self.users.users) // 10)]
        attempts   = 0

        while len(rows) < target_n and attempts < target_n * 4:
            user    = random.choice(fraud_users)
            pattern = random.choice(self.patterns)
            method  = self._PATTERN_DISPATCH.get(pattern, "_generic_fraud")
            batch   = getattr(self, method)(user)
            rows.extend(batch)
            attempts += 1

        return pd.DataFrame(rows[:target_n])

    # ── Pattern: Money Laundering ────────────────────────────────────────────
    # Structuring deposits/transfers just below the $10,000 reporting threshold.
    # Key signals: amounts $1,000-$9,499, round amounts, Financial Services
    # merchants (wire transfer, crypto), network of accounts.

    def _money_laundering(self, user: GenericUser) -> List[Dict]:
        rows   = []
        n_txns = random.randint(3, 8)
        anchor = self._sample_ts(preferred_hours=list(range(9, 18)))

        # Structuring: amounts carefully below $9,500
        base_amount = random.uniform(1000, 9400)

        for i in range(n_txns):
            ts      = anchor + timedelta(hours=random.uniform(i * 2, i * 8 + 4))
            # Each transfer slightly different to avoid exact-match detection
            amount  = round(base_amount * random.uniform(0.85, 0.99), 2)
            # Make it a round number (common in structuring)
            amount  = round(amount / 100) * 100
            # Financial services merchant
            merch   = self.merchants.random_merchant(high_risk=True)
            currency= random.choice(["USD", "EUR", "GBP"])

            rows.append(self._build_row(
                user=user, ts=ts, merchant=merch, amount=amount, currency=currency,
                pattern="Money Laundering",
                overrides={
                    "channel":                 "ONLINE",
                    "is_round_amount":         1,
                    "is_high_value":           int(amount > 5000),
                    "is_foreign_ip":           int(random.random() < 0.40),
                    "is_vpn_or_proxy":         int(random.random() < 0.35),
                    "velocity_1h":             random.randint(1, 4),
                    "velocity_24h":            n_txns,
                    "amount_vs_user_avg":      round(amount / max(user.avg_amount, 1), 2),
                    "cross_border_flag":       int(random.random() < 0.50),
                    "shipping_billing_mismatch": 0,
                },
            ))

        return rows

    # ── Pattern: Phishing ────────────────────────────────────────────────────
    # Victim was deceived into authorising a transfer.
    # Key signals: victim's own device, normal-ish amounts, but unusual
    # recipient (first-time merchant, foreign IP on recipient side),
    # transaction within minutes of a suspicious email/call.

    def _phishing(self, user: GenericUser) -> List[Dict]:
        rows  = []
        n     = random.randint(1, 3)
        anchor= self._sample_ts(preferred_hours=list(range(10, 20)))

        for i in range(n):
            ts     = anchor + timedelta(minutes=random.uniform(i * 2, i * 15))
            amount = round(random.uniform(50, 2000), 2)
            merch  = self.merchants.random_merchant()
            # Use high-risk merchant for the actual transfer
            if random.random() < 0.6:
                merch = self.merchants.random_merchant(high_risk=True)

            rows.append(self._build_row(
                user=user, ts=ts, merchant=merch, amount=amount, currency="USD",
                pattern="Phishing",
                overrides={
                    "device_id":               user.device_id,  # victim's own device
                    "is_new_device":           0,
                    "is_foreign_ip":           int(random.random() < 0.65),
                    "is_vpn_or_proxy":         int(random.random() < 0.45),
                    "is_first_time_merchant":  1,
                    "velocity_1h":             n,
                    "velocity_24h":            n + random.randint(0, 2),
                    "failed_auth_attempts":    random.randint(0, 1),
                    "shipping_billing_mismatch": int(random.random() < 0.60),
                    "cross_border_flag":       int(random.random() < 0.60),
                },
            ))

        return rows

    # ── Pattern: Synthetic Identity ──────────────────────────────────────────
    # Fabricated PII used to open accounts and slowly build credit history,
    # then a large "bust-out" purchase before abandoning the identity.
    # Key signals: new account, escalating amounts over time, bust-out at end.

    def _synthetic_identity(self, user: GenericUser) -> List[Dict]:
        rows   = []
        n_warm = random.randint(5, 12)   # warm-up transactions
        n_bust = random.randint(1, 3)    # bust-out transactions
        anchor = self._sample_ts(preferred_hours=list(range(9, 21)))

        # Warm-up: small, normal-looking purchases
        for i in range(n_warm):
            ts     = anchor + timedelta(days=random.uniform(i * 3, i * 10))
            amount = round(random.uniform(10, 400), 2)
            merch  = self.merchants.random_merchant()

            rows.append(self._build_row(
                user=user, ts=ts, merchant=merch, amount=amount, currency="USD",
                pattern="",  # warm-up rows labelled 0
                overrides={
                    "account_age_days":   max(1, i * 5),
                    "is_new_device":      int(i == 0),
                    "velocity_24h":       1,
                    "fraud_label":        0,
                    "fraud_type":         "",
                },
            ))

        # Bust-out: large purchases at high-value merchants
        bust_anchor = anchor + timedelta(days=n_warm * 7 + random.randint(5, 30))
        for j in range(n_bust):
            ts     = bust_anchor + timedelta(hours=random.uniform(j * 0.5, j * 2))
            amount = round(random.uniform(1000, 8000), 2)
            merch  = self.merchants.random_merchant()

            rows.append(self._build_row(
                user=user, ts=ts, merchant=merch, amount=amount, currency="USD",
                pattern="Synthetic Identity",
                overrides={
                    "account_age_days":   n_warm * 7 + j,
                    "is_new_device":      int(random.random() < 0.50),
                    "is_foreign_ip":      int(random.random() < 0.40),
                    "velocity_1h":        n_bust,
                    "velocity_24h":       n_bust + 1,
                    "amount_vs_user_avg": round(amount / max(user.avg_amount, 1), 2),
                    "is_high_value":      1,
                    "shipping_billing_mismatch": int(random.random() < 0.55),
                },
            ))

        return rows

    # ── Pattern: Friendly Fraud ──────────────────────────────────────────────
    # Legitimate cardholder disputes valid transactions to get refunds.
    # Key signals: amounts ≈ normal, legitimate merchants, no foreign IP,
    # same device — indistinguishable from real purchases.

    def _friendly_fraud(self, user: GenericUser) -> List[Dict]:
        rows  = []
        n     = random.randint(1, 4)
        anchor= self._sample_ts(preferred_hours=list(range(10, 21)))

        for i in range(n):
            ts     = anchor + timedelta(days=random.uniform(i * 5, i * 20))
            amount = round(random.uniform(30, 500), 2)
            merch  = self.merchants.random_merchant()

            rows.append(self._build_row(
                user=user, ts=ts, merchant=merch, amount=amount, currency="USD",
                pattern="Friendly Fraud",
                overrides={
                    "device_id":         user.device_id,
                    "is_new_device":     0,
                    "is_foreign_ip":     0,
                    "is_vpn_or_proxy":   0,
                    "velocity_1h":       1,
                    "velocity_24h":      random.randint(1, 3),
                    "is_first_time_merchant": int(random.random() < 0.30),
                    "shipping_billing_mismatch": 0,
                    "cross_border_flag": 0,
                },
            ))

        return rows

    # ── Pattern: Triangulation Fraud ─────────────────────────────────────────
    # Fraudster runs a fake storefront, collects real payments, fulfils
    # orders using stolen cards. Burst of CNP txns at multiple merchants.

    def _triangulation(self, user: GenericUser) -> List[Dict]:
        rows       = []
        n_txns     = random.randint(5, 20)
        anchor     = self._sample_ts(preferred_hours=list(range(2, 8)))
        merchants  = [self.merchants.random_merchant() for _ in range(random.randint(3, 7))]

        for i in range(n_txns):
            ts     = anchor + timedelta(minutes=random.uniform(i * 2, i * 5 + 3))
            amount = round(random.uniform(50, 1500), 2)
            merch  = random.choice(merchants)

            rows.append(self._build_row(
                user=user, ts=ts, merchant=merch, amount=amount, currency="USD",
                pattern="Triangulation Fraud",
                overrides={
                    "is_new_device":      int(random.random() < 0.70),
                    "is_foreign_ip":      int(random.random() < 0.65),
                    "is_vpn_or_proxy":    int(random.random() < 0.50),
                    "channel":            "ONLINE",
                    "velocity_1h":        n_txns,
                    "velocity_24h":       n_txns + random.randint(0, 5),
                    "is_first_time_merchant": 1,
                    "shipping_billing_mismatch": int(random.random() < 0.70),
                    "cross_border_flag":  int(random.random() < 0.55),
                },
            ))

        return rows

    # ── Pattern: Identity Fraud ───────────────────────────────────────────────
    def _identity_fraud(self, user: GenericUser) -> List[Dict]:
        rows   = []
        n      = random.randint(2, 6)
        anchor = self._sample_ts(preferred_hours=list(range(0, 6)))

        for i in range(n):
            ts     = anchor + timedelta(hours=random.uniform(i * 0.5, i * 3))
            amount = round(random.uniform(200, 4000), 2)
            merch  = self.merchants.random_merchant()

            rows.append(self._build_row(
                user=user, ts=ts, merchant=merch, amount=amount, currency="USD",
                pattern="Identity Fraud",
                overrides={
                    "is_new_device":      1,
                    "is_foreign_ip":      int(random.random() < 0.70),
                    "is_vpn_or_proxy":    int(random.random() < 0.50),
                    "velocity_1h":        n,
                    "failed_auth_attempts": random.randint(0, 3),
                    "shipping_billing_mismatch": int(random.random() < 0.65),
                    "is_first_time_merchant": 1,
                    "cross_border_flag":  1,
                },
            ))

        return rows

    # ── Pattern: Refund Fraud ─────────────────────────────────────────────────
    def _refund_fraud(self, user: GenericUser) -> List[Dict]:
        rows  = []
        n     = random.randint(1, 5)
        anchor= self._sample_ts(preferred_hours=list(range(11, 20)))

        for i in range(n):
            ts     = anchor + timedelta(days=random.uniform(i * 2, i * 10))
            amount = round(random.uniform(30, 400), 2)
            merch  = self.merchants.random_merchant()

            rows.append(self._build_row(
                user=user, ts=ts, merchant=merch, amount=amount, currency="USD",
                pattern="Refund Fraud",
                overrides={
                    "device_id":          user.device_id,
                    "is_new_device":      0,
                    "is_foreign_ip":      0,
                    "velocity_1h":        1,
                    "velocity_24h":       random.randint(1, 4),
                    "is_first_time_merchant": int(random.random() < 0.40),
                },
            ))

        return rows

    # ── Pattern: Corporate Card Abuse ─────────────────────────────────────────
    def _corporate_card(self, user: GenericUser) -> List[Dict]:
        rows   = []
        n      = random.randint(2, 8)
        anchor = self._sample_ts(preferred_hours=list(range(17, 23)))

        for i in range(n):
            ts     = anchor + timedelta(days=random.uniform(i, i * 3))
            amount = round(random.uniform(200, 5000), 2)  # over per-diem
            merch  = self.merchants.random_merchant()

            rows.append(self._build_row(
                user=user, ts=ts, merchant=merch, amount=amount, currency="USD",
                pattern="Corporate Card Abuse",
                overrides={
                    "device_id":         user.device_id,
                    "channel":           "POS",
                    "merchant_category": random.choice(["Travel & Hotels", "Food & Dining",
                                                         "Entertainment", "Gambling"]),
                    "velocity_24h":      n,
                    "amount_vs_user_avg":round(amount / max(user.avg_amount, 1), 2),
                    "is_high_value":     int(amount > 500),
                    "cross_border_flag": int(random.random() < 0.45),
                },
            ))

        return rows

    # ── Fallback ──────────────────────────────────────────────────────────────
    def _generic_fraud(self, user: GenericUser) -> List[Dict]:
        rows  = []
        n     = random.randint(1, 5)
        anchor= self._sample_ts()

        for i in range(n):
            ts     = anchor + timedelta(hours=random.uniform(i * 0.5, i * 4))
            amount = round(random.uniform(50, 3000), 2)
            merch  = self.merchants.random_merchant()

            rows.append(self._build_row(
                user=user, ts=ts, merchant=merch, amount=amount, currency="USD",
                pattern="Generic Fraud",
                overrides={
                    "is_foreign_ip":  int(random.random() < 0.50),
                    "velocity_1h":    n,
                },
            ))

        return rows

    # ── Row builder ───────────────────────────────────────────────────────────

    def _build_row(self, user: GenericUser, ts: datetime, merchant: GenericMerchant,
                   amount: float, currency: str, pattern: str,
                   overrides: Optional[Dict] = None) -> Dict:
        overrides = overrides or {}
        is_foreign_ip = overrides.get("is_foreign_ip", int(random.random() < 0.30))
        ip_country = (random.choice(HIGH_RISK_COUNTRIES) if is_foreign_ip
                      else user.billing_country)

        row = {
            "txn_id":                  _txn_id(),
            "timestamp":               ts.strftime("%Y-%m-%d %H:%M:%S"),
            "hour_of_day":             ts.hour,
            "day_of_week":             ts.weekday(),
            "is_weekend":              int(ts.weekday() >= 5),
            "is_off_hours":            int(ts.hour < 8 or ts.hour >= 22),
            "user_id":                 user.user_id,
            "account_age_days":        user.account_age,
            "card_type":               user.card_type,
            "card_last4":              user.card_last4,
            "billing_country":         user.billing_country,
            "amount":                  amount,
            "currency":                currency,
            "channel":                 "ONLINE",
            "is_round_amount":         int(amount % 100 == 0),
            "is_high_value":           int(amount > user.avg_amount * 3),
            "merchant_id":             merchant.merchant_id,
            "merchant_name":           merchant.name,
            "merchant_category":       merchant.category,
            "merchant_country":        merchant.country,
            "mcc":                     merchant.mcc,
            "is_high_risk_merchant":   int(merchant.is_high_risk),
            "device_id":               str(uuid.uuid4())[:12],
            "device_type":             user.device_type,
            "device_os":               user.device_os,
            "browser":                 random.choice(BROWSER_LIST),
            "ip_address":              _ip(foreign=bool(is_foreign_ip)),
            "ip_country":              ip_country,
            "is_new_device":           int(random.random() < 0.60),
            "is_foreign_ip":           is_foreign_ip,
            "is_vpn_or_proxy":         int(random.random() < 0.40),
            "shipping_country":        (random.choice(HIGH_RISK_COUNTRIES)
                                        if random.random() < 0.35 else user.billing_country),
            "shipping_billing_mismatch": int(random.random() < 0.45),
            "is_first_time_merchant":  int(random.random() < 0.70),
            "velocity_1h":             random.randint(2, 12),
            "velocity_24h":            random.randint(3, 25),
            "amount_vs_user_avg":      round(amount / max(user.avg_amount, 1), 3),
            "failed_auth_attempts":    random.randint(0, 2),
            "cross_border_flag":       int(user.billing_country != merchant.country),
            "days_since_last_txn":     random.randint(0, 5),
            "fraud_label":             1 if pattern else 0,
            "fraud_type":              pattern,
        }

        # Apply caller overrides
        row.update(overrides)

        # Fix shipping_billing_mismatch based on final countries
        if "shipping_country" in overrides:
            row["shipping_billing_mismatch"] = int(
                overrides["shipping_country"] != user.billing_country
            )

        return row

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


# ─── Top-level Engine ──────────────────────────────────────────────────────────

class GenericDatasetEngine:
    """
    Orchestrates generic fraud dataset generation from a blueprint.
    Called by DatasetEngine when fraud_category == "other".
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

        # Derive MCC pool from scenario
        scenario   = self.bp.get("Fraud_Scenario_Name", "").lower()
        mcc_pool   = []
        for key, mccs in SCENARIO_MCC_MAP.items():
            if key in scenario:
                mcc_pool = mccs
                break

        user_pool     = GenericUserPool(num_users, fraud_user_ratio, seed=self.seed)
        merchant_pool = GenericMerchantPool(max(50, num_users // 5),
                                             mcc_pool or ["5999", "5732", "5812"],
                                             seed=self.seed)

        normal_gen = GenericNormalGenerator(self.bp, user_pool, merchant_pool)
        normal_df  = normal_gen.generate(n_normal)

        fraud_inj  = GenericFraudInjector(self.bp, user_pool, merchant_pool)
        fraud_df   = fraud_inj.generate(n_fraud)

        df = pd.concat([normal_df, fraud_df], ignore_index=True)
        df = df.sample(frac=1, random_state=self.seed).reset_index(drop=True)
        df = df.sort_values("timestamp").reset_index(drop=True)
        df = df.head(total_rows)
        df = self._enforce_types(df)
        return df

    def _enforce_types(self, df: pd.DataFrame) -> pd.DataFrame:
        int_cols = [
            "hour_of_day", "day_of_week", "is_weekend", "is_off_hours",
            "account_age_days", "is_round_amount", "is_high_value",
            "is_high_risk_merchant", "is_new_device", "is_foreign_ip",
            "is_vpn_or_proxy", "shipping_billing_mismatch", "is_first_time_merchant",
            "velocity_1h", "velocity_24h", "failed_auth_attempts",
            "cross_border_flag", "days_since_last_txn", "fraud_label",
        ]
        float_cols = ["amount", "amount_vs_user_avg"]

        for c in int_cols:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0).astype(int)
        for c in float_cols:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0.0).astype(float)

        for col in GENERIC_COLUMN_NAMES:
            if col not in df.columns:
                df[col] = "" if col in ("fraud_type", "browser", "failure_code") else 0

        return df[GENERIC_COLUMN_NAMES]
