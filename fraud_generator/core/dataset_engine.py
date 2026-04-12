"""
core/dataset_engine.py  (v2 — EMVCo 3DS)

Static, deterministic fraud dataset engine.
Reads a validated v2 blueprint and generates a synthetic dataset whose
columns conform to the EMVCo 3-D Secure (3DS) v2.3.1 specification.

Column set is defined in schemas/emvco_3ds_schema.py.

Architecture
------------
1. UserPool        – builds a fixed set of realistic 3DS user profiles
2. MerchantPool    – builds merchants with MCC codes
3. NormalGenerator – generates baseline 3DS authentication streams per user
4. FraudInjector   – overlays fraud patterns with 3DS-specific signals
5. DatasetEngine   – orchestrates everything and returns a DataFrame
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

try:
    from faker import Faker
    _fake = Faker()
    Faker.seed(42)
except ImportError:
    _fake = None

from schemas.emvco_3ds_schema import (
    CORE_COLUMNS,
    CURRENCY_CODES,
    ENUM_POOLS,
    HIGH_RISK_MCCS,
    MCC_CATEGORIES,
    SCENARIO_MCC_MAP,
)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _clamp(val: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, val))


def _weighted_choice(weights_dict: Dict[str, float]) -> str:
    keys  = list(weights_dict.keys())
    probs = [weights_dict[k] for k in keys]
    total = sum(probs)
    probs = [p / total for p in probs]
    return random.choices(keys, weights=probs, k=1)[0]


def _sanitise_weights(weights_dict, fallback: dict) -> dict:
    if not isinstance(weights_dict, dict) or not weights_dict:
        return fallback
    clean = {k: v for k, v in weights_dict.items() if isinstance(v, (int, float))}
    return clean if clean else fallback


def _sample_amount(dist: str, mn: float, mx: float,
                   mean: float, std: float) -> float:
    if dist == "lognormal":
        sigma = std / mean if mean > 0 else 0.5
        mu    = np.log(mean) - 0.5 * sigma ** 2
        v     = np.random.lognormal(mu, sigma)
    elif dist == "normal":
        v = np.random.normal(mean, std)
    elif dist == "pareto":
        b = mean / (mean - mn) if mean > mn else 2.0
        v = (np.random.pareto(b) + 1) * mn
    else:
        v = np.random.uniform(mn, mx)
    return round(float(_clamp(max(0.01, v), mn, mx)), 2)


def _sample_timestamp(start: datetime, end: datetime,
                       peak_start: int, peak_end: int,
                       off_peak_weight: float,
                       preferred_hours: Optional[List[int]] = None) -> datetime:
    delta = (end - start).total_seconds()
    ts    = start + timedelta(seconds=random.uniform(0, delta))
    if preferred_hours:
        if random.random() > 0.15:
            ts = ts.replace(hour=random.choice(preferred_hours),
                            minute=random.randint(0, 59),
                            second=random.randint(0, 59))
    else:
        hour    = ts.hour
        in_peak = peak_start <= hour <= peak_end
        if not in_peak and random.random() > off_peak_weight:
            ts = ts.replace(
                hour=random.randint(peak_start, peak_end),
                minute=random.randint(0, 59),
                second=random.randint(0, 59),
            )
    return ts


def _faker_or_fallback(method: str, *args, **kwargs):
    if _fake:
        return getattr(_fake, method)(*args, **kwargs)
    return f"fake_{method}_{random.randint(1000, 9999)}"


def _enum(pool_key: str) -> str:
    """Pick a random value from an EMVCo enum pool."""
    return random.choice(ENUM_POOLS[pool_key])


def _hash_email(email: str) -> str:
    """SHA-256 hash of email address (PII protection)."""
    return hashlib.sha256(email.encode()).hexdigest()[:16]


def _make_pan() -> str:
    """Generate a plausible 16-digit Visa PAN (Luhn-valid not required for synthetic data)."""
    return "4" + "".join([str(random.randint(0, 9)) for _ in range(15)])


def _mask_pan(pan: str) -> str:
    """Return first-6 + ******* + last-4 masked PAN."""
    if len(pan) < 10:
        return pan
    return pan[:6] + "*" * (len(pan) - 10) + pan[-4:]


def _currency_code(iso_alpha: str) -> str:
    """Convert ISO 4217 alpha-3 to numeric code (fallback to '840' USD)."""
    return CURRENCY_CODES.get(iso_alpha, "840")


def _purchase_amount_minor(amount: float, exponent: int = 2) -> int:
    """Convert decimal purchase amount to EMVCo minor-unit integer."""
    return int(round(amount * (10 ** exponent)))


def _mcc_for_scenario(scenario_name: str) -> List[str]:
    """Return MCC list for a known scenario, falling back to generic retail."""
    lower = scenario_name.lower()
    for key, mccs in SCENARIO_MCC_MAP.items():
        if key in lower:
            return mccs
    return ["5999", "5411", "5812", "5732", "5311"]


def _random_mcc(mcc_pool: List[str]) -> str:
    return random.choice(mcc_pool)


def _is_high_risk_mcc(mcc: str) -> int:
    return 1 if mcc in HIGH_RISK_MCCS else 0


def _browser_ua() -> str:
    agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/604.1",
        "Mozilla/5.0 (Linux; Android 14; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.6099.144 Mobile Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64; rv:121.0) Gecko/20100101 Firefox/121.0",
    ]
    return random.choice(agents)


# ─── Blueprint Normaliser ─────────────────────────────────────────────────────

def _normalise_blueprint(bp: Dict[str, Any]) -> Dict[str, Any]:
    """
    Coerce blueprint fields that should be lists/dicts but may arrive in the
    wrong shape when an LLM emits them differently.

    Handles the most common LLM mistake: Fraud_Patterns returned as a keyed
    dict instead of a list, which causes the classic
    "list indices must be integers or slices, not str" error.
    """
    bp = dict(bp)  # shallow copy — don't mutate the caller's dict

    # ── Fraud_Patterns: must be a list[dict], each with 'pattern_name' ────────
    fp = bp.get("Fraud_Patterns", [])
    if isinstance(fp, dict):
        normalised = []
        for name, body in fp.items():
            if isinstance(body, dict):
                entry = dict(body)
                entry.setdefault("pattern_name", name)
                # Ensure required keys exist with safe defaults
                entry.setdefault("weight", 1.0)
                entry.setdefault("sequence_type", "independent")
                entry.setdefault("params", {})
                normalised.append(entry)
            else:
                # body is a scalar — wrap it minimally
                normalised.append({
                    "pattern_name":  name,
                    "weight":        float(body) if isinstance(body, (int, float)) else 1.0,
                    "sequence_type": "independent",
                    "params":        {},
                })
        bp["Fraud_Patterns"] = normalised
    elif isinstance(fp, list):
        # List is correct shape — but make sure every entry has required keys
        cleaned = []
        for i, item in enumerate(fp):
            if isinstance(item, dict):
                entry = dict(item)
                entry.setdefault("pattern_name", f"pattern_{i}")
                entry.setdefault("weight", 1.0)
                entry.setdefault("sequence_type", "independent")
                entry.setdefault("params", {})
                cleaned.append(entry)
        bp["Fraud_Patterns"] = cleaned

    # Guard: if Fraud_Patterns is still empty, inject a generic fallback
    if not bp.get("Fraud_Patterns"):
        bp["Fraud_Patterns"] = [{
            "pattern_name":  "generic_fraud",
            "weight":        1.0,
            "sequence_type": "independent",
            "params": {
                "amount_min":        10.0,
                "amount_max":        500.0,
                "amount_mean":       120.0,
                "amount_std":        80.0,
                "foreign_ip_prob":   0.6,
                "same_device_prob":  0.3,
                "same_location_prob":0.3,
                "velocity_txns_per_hour": 8,
            },
        }]

    # ── Fraud_Injection_Rules: must be a dict ─────────────────────────────────
    fir = bp.get("Fraud_Injection_Rules", {})
    if isinstance(fir, list):
        # LLM may emit [{"key": ..., "value": ...}, ...]
        rebuilt = {}
        for item in fir:
            if isinstance(item, dict) and "key" in item and "value" in item:
                rebuilt[item["key"]] = item["value"]
        bp["Fraud_Injection_Rules"] = rebuilt
    if not isinstance(bp.get("Fraud_Injection_Rules"), dict):
        bp["Fraud_Injection_Rules"] = {}

    # Ensure required Fraud_Injection_Rules keys exist
    fir = bp["Fraud_Injection_Rules"]
    fir.setdefault("fraud_user_ratio", 0.10)
    fir.setdefault("max_fraud_txns_per_user", 50)
    fir.setdefault("contaminate_normal_users", False)
    fir.setdefault("contamination_prob", 0.0)

    # ── Sequence_Rules: must be a dict ────────────────────────────────────────
    sr = bp.get("Sequence_Rules", {})
    if isinstance(sr, list):
        bp["Sequence_Rules"] = {}
    if not isinstance(bp.get("Sequence_Rules"), dict):
        bp["Sequence_Rules"] = {}

    bp["Sequence_Rules"].setdefault(
        "inter_txn_gap_seconds", {"min": 30, "max": 300}
    )

    # ── Normal_User_Profile: guard sub-fields ────────────────────────────────
    nup = bp.get("Normal_User_Profile", {})
    if not isinstance(nup, dict):
        nup = {}
        bp["Normal_User_Profile"] = nup

    nup.setdefault("transaction_amount", {
        "distribution": "lognormal",
        "min": 1.0, "max": 2000.0, "mean": 85.0, "std": 120.0,
    })
    nup.setdefault("transactions_per_day", {"mean": 1.5, "std": 1.0})
    nup.setdefault("active_hours", {
        "peak_start": 9, "peak_end": 21, "off_peak_weight": 0.1
    })
    nup.setdefault("active_days", {"weekday_weight": 0.75, "weekend_weight": 0.25})
    nup.setdefault("merchant_category_weights", {"Miscellaneous Retail": 1.0})
    nup.setdefault("currency_weights", {"USD": 1.0})
    nup.setdefault("location_change_prob", 0.05)
    nup.setdefault("device_change_prob", 0.02)

    # ── Dataset_Specifications: guard required keys ───────────────────────────
    ds = bp.get("Dataset_Specifications", {})
    if not isinstance(ds, dict):
        ds = {}
        bp["Dataset_Specifications"] = ds

    ds.setdefault("date_range_start", "2022-01-01")
    ds.setdefault("date_range_end",   "2023-12-31")
    ds.setdefault("num_users",        1000)
    ds.setdefault("num_merchants",    500)
    ds.setdefault("total_rows",       1000)
    ds.setdefault("fraud_ratio",      0.05)
    ds.setdefault("output_format",    "csv")

    return bp


# ─── Data Classes ─────────────────────────────────────────────────────────────

@dataclass
class UserProfile:
    user_id:          str
    acct_id:          str
    home_city:        str
    home_country:     str                  # ISO 3166-1 numeric
    home_ip_prefix:   str
    primary_device:   str
    sdk_app_id:       str
    pan:              str
    card_expiry:      str                  # YYMM
    email_hash:       str
    acct_open_ind:    str                  # EMVCo acctInfo.openAcctInd
    browser_language: str
    browser_tz:       int
    screen_w:         int
    screen_h:         int
    is_fraudster:     bool = False
    card_numbers:     List[str] = field(default_factory=list)


@dataclass
class MerchantProfile:
    merchant_id:          str
    acquirer_merchant_id: str
    merchant_name:        str
    mcc:                  str
    category:             str
    city:                 str
    country_code:         str              # ISO 3166-1 numeric
    acquirer_bin:         str
    requestor_id:         str
    requestor_name:       str


# ─── Pools ────────────────────────────────────────────────────────────────────

class UserPool:
    def __init__(self, num_users: int, fraud_user_ratio: float, seed: int = 42):
        random.seed(seed)
        np.random.seed(seed)

        n_fraud  = max(1, int(num_users * fraud_user_ratio))
        n_normal = num_users - n_fraud

        self.users: List[UserProfile] = []
        for i in range(n_normal):
            self.users.append(self._make_user(f"U{i:06d}", is_fraudster=False))
        for i in range(n_fraud):
            self.users.append(self._make_user(f"F{i:06d}", is_fraudster=True))

        self.normal_users = [u for u in self.users if not u.is_fraudster]
        self.fraud_users  = [u for u in self.users if     u.is_fraudster]

    _COUNTRIES = ["840", "826", "978", "036", "124", "124", "840", "840"]
    _LANGUAGES = ["en-US", "en-GB", "fr-FR", "de-DE", "es-ES", "ja-JP", "zh-CN", "pt-BR"]
    _SCREEN_SIZES = [(1920, 1080), (1366, 768), (1440, 900), (2560, 1440),
                     (390, 844), (414, 896), (375, 667)]
    _TZ_OFFSETS = [-480, -420, -360, -300, -240, 0, 60, 120, 330, 540]

    def _make_user(self, uid: str, is_fraudster: bool) -> UserProfile:
        ip_a   = random.randint(10, 220)
        ip_b   = random.randint(0, 255)
        pan    = _make_pan()
        yy     = random.randint(25, 30)
        mm     = random.randint(1, 12)
        w, h   = random.choice(self._SCREEN_SIZES)
        email  = _faker_or_fallback("email")

        cards  = [_make_pan() for _ in range(random.randint(1, 3))]
        cards.insert(0, pan)

        return UserProfile(
            user_id          = uid,
            acct_id          = str(uuid.uuid4())[:12],
            home_city        = _faker_or_fallback("city"),
            home_country     = random.choice(self._COUNTRIES),
            home_ip_prefix   = f"{ip_a}.{ip_b}",
            primary_device   = str(uuid.uuid4())[:8],
            sdk_app_id       = str(uuid.uuid4()),
            pan              = pan,
            card_expiry      = f"{yy:02d}{mm:02d}",
            email_hash       = _hash_email(email),
            acct_open_ind    = random.choice(["02", "03", "04"]),
            browser_language = random.choice(self._LANGUAGES),
            browser_tz       = random.choice(self._TZ_OFFSETS),
            screen_w         = w,
            screen_h         = h,
            is_fraudster     = is_fraudster,
            card_numbers     = cards,
        )


class MerchantPool:
    def __init__(self, num_merchants: int,
                 category_weights: Dict[str, float],
                 mcc_pool: List[str],
                 seed: int = 42):
        random.seed(seed)
        self.merchants: List[MerchantProfile] = []

        _ACQUIRER_BINS = ["411111", "422222", "433333", "444444", "455555"]
        _COUNTRIES     = ["840", "826", "978", "036", "124"]

        for i in range(num_merchants):
            mcc      = _random_mcc(mcc_pool)
            category = MCC_CATEGORIES.get(mcc, _weighted_choice(category_weights))
            country  = random.choice(_COUNTRIES)
            name     = _faker_or_fallback("company")

            self.merchants.append(MerchantProfile(
                merchant_id          = f"M{i:05d}",
                acquirer_merchant_id = f"ACQ{i:09d}",
                merchant_name        = name[:22],                 # EMVCo max 40 chars, keep short
                mcc                  = mcc,
                category             = category,
                city                 = _faker_or_fallback("city"),
                country_code         = country,
                acquirer_bin         = random.choice(_ACQUIRER_BINS),
                requestor_id         = f"REQ{i:010d}",
                requestor_name       = name[:25],
            ))

        self._by_mcc: Dict[str, List[MerchantProfile]] = {}
        for m in self.merchants:
            self._by_mcc.setdefault(m.mcc, []).append(m)

    def random_merchant(self,
                        mcc: Optional[str] = None,
                        n: int = 1) -> List[MerchantProfile]:
        pool = self._by_mcc.get(mcc, self.merchants) if mcc else self.merchants
        if not pool:
            pool = self.merchants
        return random.choices(pool, k=n)


# ─── Normal Transaction Generator ─────────────────────────────────────────────

class NormalGenerator:
    """Generates realistic 3DS authentication records for non-fraudulent users."""

    def __init__(self, blueprint: Dict[str, Any],
                 user_pool: UserPool, merchant_pool: MerchantPool):
        self.bp        = blueprint
        self.users     = user_pool
        self.merchants = merchant_pool

        specs = blueprint["Dataset_Specifications"]
        self.start = datetime.fromisoformat(specs["date_range_start"])
        self.end   = datetime.fromisoformat(specs["date_range_end"])

        prof = blueprint["Normal_User_Profile"]
        self.amt_cfg  = prof["transaction_amount"]
        self.tpd_cfg  = prof["transactions_per_day"]
        self.hour_cfg = prof["active_hours"]
        self.day_cfg  = prof["active_days"]
        self.cat_w    = prof["merchant_category_weights"]
        self.cur_w    = _sanitise_weights(prof.get("currency_weights"), {"USD": 1.0})
        self.loc_prob = prof.get("location_change_prob", 0.05)
        self.dev_prob = prof.get("device_change_prob", 0.02)

    def generate(self, target_n: int) -> pd.DataFrame:
        rows: List[Dict] = []
        users = self.users.normal_users or self.users.users
        per_user_txns = self._allocate(target_n, len(users))

        for user, n_txns in zip(users, per_user_txns):
            for _ in range(n_txns):
                rows.append(self._make_row(user))
            if len(rows) >= target_n:
                break

        return pd.DataFrame(rows[:target_n])

    def _allocate(self, total: int, n_users: int) -> List[int]:
        lam    = max(1, total / n_users)
        counts = np.random.poisson(lam, size=n_users).tolist()
        actual = sum(counts) or n_users
        scaled = [int(c * total / actual) for c in counts]
        diff   = total - sum(scaled)
        for i in range(abs(diff)):
            scaled[i % n_users] += 1 if diff > 0 else -1
        return scaled

    def _make_row(self, user: UserProfile) -> Dict:
        merchant = self.merchants.random_merchant()[0]
        iso_alpha = _weighted_choice(self.cur_w)
        currency  = _currency_code(iso_alpha)
        amount    = _sample_amount(
            self.amt_cfg["distribution"],
            self.amt_cfg["min"], self.amt_cfg["max"],
            self.amt_cfg["mean"], self.amt_cfg["std"],
        )
        ts = _sample_timestamp(
            self.start, self.end,
            self.hour_cfg["peak_start"], self.hour_cfg["peak_end"],
            self.hour_cfg["off_peak_weight"],
        )

        cross_border = int(merchant.country_code != user.home_country)

        # 3DS-specific normal behaviour
        trans_status      = random.choices(
            ["Y", "A", "C", "N"], weights=[0.82, 0.07, 0.07, 0.04]
        )[0]
        challenge_done    = trans_status == "C" and random.random() > 0.2
        eci               = "05" if trans_status == "Y" else ("06" if trans_status == "A" else "07")
        new_device        = int(random.random() < self.dev_prob)
        velocity_1h       = random.randint(0, 3)
        velocity_24h      = random.randint(1, 8)
        amt_ratio         = round(amount / max(self.amt_cfg["mean"], 1), 3)

        return {
            # Transaction IDs
            "threeds_server_trans_id":   str(uuid.uuid4()),
            "acs_trans_id":              str(uuid.uuid4()),
            "ds_trans_id":               str(uuid.uuid4()),
            "sdk_trans_id":              str(uuid.uuid4()) if random.random() < 0.3 else "",
            "message_version":           random.choices(["2.3.1", "2.2.0", "2.1.0"],
                                                        weights=[0.6, 0.3, 0.1])[0],
            "device_channel":            random.choices(["02", "01", "03"],
                                                        weights=[0.65, 0.30, 0.05])[0],
            "three_ds_requestor_id":     merchant.requestor_id,
            "three_ds_requestor_name":   merchant.requestor_name,
            # Account / Cardholder
            "acct_number":               _mask_pan(random.choice(user.card_numbers)),
            "card_expiry_date":          user.card_expiry,
            "acct_id":                   user.acct_id,
            "acct_type":                 _enum("acct_type"),
            "acct_info_chg_ind":         _enum("acct_info_chg_ind"),
            "acct_info_open_acct_ind":   user.acct_open_ind,
            "acct_info_ship_addr_usage_ind": _enum("acct_info_ship_addr_usage_ind"),
            "acct_info_txn_activity_day":   random.randint(0, 5),
            "acct_info_txn_activity_year":  random.randint(2, 80),
            "acct_info_prov_attempts_day":  random.randint(0, 2),
            "acct_info_nb_purchase_account":random.randint(1, 30),
            "ship_addr_match":           random.choices(["Y", "N"], weights=[0.8, 0.2])[0],
            "ship_addr_usage_ind":       _enum("ship_addr_usage_ind"),
            "bill_addr_city":            user.home_city,
            "bill_addr_country":         user.home_country,
            "bill_addr_state":           _faker_or_fallback("state_abbr") if _fake else "CA",
            "email":                     user.email_hash,
            # Browser
            "browser_accept_header":     "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "browser_ip":                f"{user.home_ip_prefix}.{random.randint(1,254)}.{random.randint(1,254)}",
            "browser_java_enabled":      random.random() < 0.15,
            "browser_javascript_enabled":True,
            "browser_language":          user.browser_language,
            "browser_color_depth":       _enum("browser_color_depth"),
            "browser_screen_height":     user.screen_h,
            "browser_screen_width":      user.screen_w,
            "browser_tz":                user.browser_tz,
            "browser_user_agent":        _browser_ua(),
            "sdk_app_id":                user.sdk_app_id,
            "sdk_enc_data":              "",
            "sdk_ephem_pub_key":         "",
            "sdk_max_timeout":           5,
            "sdk_reference_number":      f"EMVSDK_{random.randint(100000,999999)}",
            # Merchant
            "merchant_id":               merchant.merchant_id,
            "merchant_name":             merchant.merchant_name,
            "mcc":                       merchant.mcc,
            "acquirer_bin":              merchant.acquirer_bin,
            "acquirer_merchant_id":      merchant.acquirer_merchant_id,
            "merchant_country_code":     merchant.country_code,
            # Purchase
            "purchase_amount":           _purchase_amount_minor(amount),
            "purchase_currency":         currency,
            "purchase_exponent":         2,
            "purchase_date":             ts.strftime("%Y%m%d%H%M%S"),
            "trans_type":                _enum("trans_type"),
            "recurring_expiry":          "",
            "recurring_frequency":       0,
            # Auth request/response
            "three_ds_requestor_auth_ind": _enum("three_ds_requestor_auth_ind"),
            "three_ds_comp_ind":           _enum("three_ds_comp_ind"),
            "acs_challenge_mandated":      "N",
            "authentication_type":         _enum("authentication_type"),
            "trans_status":                trans_status,
            "trans_status_reason":         "" if trans_status == "Y" else _enum("trans_status_reason"),
            "eci":                         eci,
            "authentication_value":        _faker_or_fallback("sha256") if trans_status == "Y" else "",
            "acs_reference_number":        f"ACS{random.randint(100000,999999)}",
            "ds_reference_number":         f"DS{random.randint(1000000,9999999)}",
            "challenge_completed":         challenge_done,
            "challenge_cancel_ind":        "",
            # Prior auth
            "three_ds_requestor_prior_auth_ind": _enum("three_ds_requestor_prior_auth_ind"),
            "prior_auth_method":           _enum("prior_auth_method"),
            "prior_auth_timestamp":        "",
            # Risk signals
            "ship_indicator":              _enum("ship_indicator"),
            "delivery_timeframe":          _enum("delivery_timeframe"),
            "reorder_items_ind":           _enum("reorder_items_ind"),
            "pre_order_purchase_ind":      _enum("pre_order_purchase_ind"),
            "gift_card_amount":            0.0,
            "gift_card_count":             0,
            "purchase_instal_data":        0,
            # Derived ML features
            "velocity_1h":                 velocity_1h,
            "velocity_24h":                velocity_24h,
            "amount_vs_avg_ratio":         amt_ratio,
            "new_device_flag":             new_device,
            "new_shipping_addr_flag":      0,
            "cross_border_flag":           cross_border,
            "high_risk_mcc_flag":          _is_high_risk_mcc(merchant.mcc),
            "time_since_acct_open_days":   random.randint(90, 3000),
            # Ground truth
            "fraud_label":                 0,
            "fraud_pattern":               "normal",
        }


# ─── Fraud Injector ────────────────────────────────────────────────────────────

class FraudInjector:
    """
    Generates 3DS authentication records that exhibit fraud-specific signals.
    Each pattern injects EMVCo-specific anomalies (trans_status, aci signals,
    velocity, IP, device) appropriate to the fraud type.
    """

    def __init__(self, blueprint: Dict[str, Any],
                 user_pool: UserPool, merchant_pool: MerchantPool):
        # Normalise before accessing any keys to guard against LLM shape variance
        self.bp        = _normalise_blueprint(blueprint)
        self.users     = user_pool
        self.merchants = merchant_pool

        specs      = self.bp["Dataset_Specifications"]
        self.start = datetime.fromisoformat(specs["date_range_start"])
        self.end   = datetime.fromisoformat(specs["date_range_end"])

        self.patterns  = self.bp["Fraud_Patterns"]
        self.inj_rules = self.bp["Fraud_Injection_Rules"]
        self.seq_rules = self.bp["Sequence_Rules"]
        self.cur_w     = _sanitise_weights(
            self.bp["Normal_User_Profile"].get("currency_weights"),
            {"USD": 1.0},
        )

        total_w = sum(p["weight"] for p in self.patterns)
        self._pattern_weights = [p["weight"] / total_w for p in self.patterns]

    def generate(self, target_n: int) -> pd.DataFrame:
        rows: List[Dict] = []
        max_per_user = self.inj_rules.get("max_fraud_txns_per_user", 50)

        fraud_users = self.users.fraud_users
        if not fraud_users:
            fraud_users = random.sample(self.users.users,
                                        max(1, len(self.users.users) // 10))

        attempts = 0
        while len(rows) < target_n and attempts < target_n * 3:
            attempts += 1
            user    = random.choice(fraud_users)
            pattern = random.choices(self.patterns,
                                     weights=self._pattern_weights, k=1)[0]
            batch   = self._generate_pattern_batch(user, pattern, max_per_user)
            rows.extend(batch)

        return pd.DataFrame(rows[:target_n])

    def _generate_pattern_batch(self, user: UserProfile,
                                 pattern: Dict, max_txns: int) -> List[Dict]:
        seq_type = pattern.get("sequence_type", "independent")
        params   = pattern.get("params", {})

        if seq_type == "burst":
            return self._burst(user, pattern, params, max_txns)
        elif seq_type == "chain":
            return self._chain(user, pattern, params, max_txns)
        elif seq_type == "network":
            return self._network(user, pattern, params, max_txns)
        else:
            return [self._single_fraud_row(user, pattern, params)]

    # ── Sequence generators ───────────────────────────────────────────────────

    def _burst(self, user: UserProfile, pattern: Dict,
               params: Dict, max_txns: int) -> List[Dict]:
        _bmn = params.get("burst_min_txns", 5)
        _bmx = max(_bmn, min(params.get("burst_max_txns", 20), max_txns))
        n    = random.randint(_bmn, _bmx)
        window_mins = params.get("burst_window_mins", 30)
        anchor = _sample_timestamp(self.start, self.end, 0, 23, 0.1,
                                    params.get("preferred_hours"))
        n_merchants = max(1, params.get("num_merchants", 1))
        merchants   = self.merchants.random_merchant(n=n_merchants)

        rows = []
        for i in range(n):
            offset = random.uniform(0, max(1, window_mins * 60))
            ts     = anchor + timedelta(seconds=offset)
            m      = random.choice(merchants)
            rows.append(self._build_row(user, pattern, params, ts, m,
                                        burst_index=i, burst_total=n))
        return rows

    def _chain(self, user: UserProfile, pattern: Dict,
               params: Dict, max_txns: int) -> List[Dict]:
        _cmn    = params.get("burst_min_txns", 3)
        _cmx    = max(_cmn, min(params.get("burst_max_txns", 8), max_txns))
        n       = random.randint(_cmn, _cmx)
        gap_min = self.seq_rules.get("inter_txn_gap_seconds", {}).get("min", 30)
        gap_max = self.seq_rules.get("inter_txn_gap_seconds", {}).get("max", 300)
        gap_min = min(gap_min, gap_max)

        ts_cur = _sample_timestamp(self.start, self.end, 0, 23, 0.1,
                                    params.get("preferred_hours"))
        merchants = self.merchants.random_merchant(n=max(1, params.get("num_merchants", 3)))

        rows  = []
        a_min = max(0.01, params.get("amount_min", 1.0))
        a_max = params.get("amount_max", 500.0)

        for i in range(n):
            frac   = i / max(n - 1, 1)
            a_mean = a_min + frac * (a_max - a_min)
            a_std  = params.get("amount_std", (a_max - a_min) * 0.1)
            amount = round(float(_clamp(
                max(0.01, np.random.normal(a_mean, a_std)), a_min, a_max
            )), 2)
            m   = random.choice(merchants)
            row = self._build_row(user, pattern, params, ts_cur, m,
                                  amount_override=amount,
                                  chain_index=i, chain_total=n)
            rows.append(row)
            ts_cur += timedelta(seconds=random.uniform(gap_min, gap_max))
        return rows

    def _network(self, user: UserProfile, pattern: Dict,
                 params: Dict, max_txns: int) -> List[Dict]:
        n_accounts  = max(1, params.get("num_accounts", 5))
        n_merchants = max(1, params.get("num_merchants", 3))

        smurf_users = [
            UserProfile(
                user_id          = f"SMURF_{user.user_id}_{i}",
                acct_id          = str(uuid.uuid4())[:12],
                home_city        = user.home_city,
                home_country     = user.home_country,
                home_ip_prefix   = user.home_ip_prefix,
                primary_device   = str(uuid.uuid4())[:8],
                sdk_app_id       = str(uuid.uuid4()),
                pan              = _make_pan(),
                card_expiry      = user.card_expiry,
                email_hash       = _hash_email(f"smurf{i}@fraud.invalid"),
                acct_open_ind    = "01",
                browser_language = user.browser_language,
                browser_tz       = user.browser_tz,
                screen_w         = user.screen_w,
                screen_h         = user.screen_h,
                is_fraudster     = True,
                card_numbers     = [_make_pan()],
            )
            for i in range(n_accounts)
        ]
        merchants = self.merchants.random_merchant(n=n_merchants)
        anchor    = _sample_timestamp(self.start, self.end, 0, 23, 0.1,
                                       params.get("preferred_hours"))
        rows      = []
        per_acct  = max(1, max_txns // n_accounts)

        for su in smurf_users:
            for j in range(random.randint(1, per_acct)):
                offset = timedelta(seconds=random.uniform(0, 3600))
                ts     = anchor + offset
                m      = random.choice(merchants)
                rows.append(self._build_row(su, pattern, params, ts, m,
                                            network_flag=True))
        return rows[:max_txns]

    # ── Row builder ───────────────────────────────────────────────────────────

    def _single_fraud_row(self, user: UserProfile,
                          pattern: Dict, params: Dict) -> Dict:
        ts = _sample_timestamp(self.start, self.end, 0, 23, 0.1,
                                params.get("preferred_hours"))
        m  = self.merchants.random_merchant()[0]
        return self._build_row(user, pattern, params, ts, m)

    def _build_row(
        self,
        user: UserProfile,
        pattern: Dict,
        params: Dict,
        ts: datetime,
        merchant: MerchantProfile,
        amount_override: Optional[float] = None,
        burst_index: int = 0,
        burst_total: int = 1,
        chain_index: int = 0,
        chain_total: int = 1,
        network_flag: bool = False,
    ) -> Dict:

        # ── Amount ────────────────────────────────────────────────────────────
        if amount_override is not None:
            amount = max(0.01, amount_override)
        else:
            amount = _sample_amount(
                "uniform",
                max(0.01, params.get("amount_min", 1.0)),
                params.get("amount_max", 500.0),
                params.get("amount_mean", 50.0),
                params.get("amount_std", 30.0),
            )
            if random.random() < params.get("round_amount_prob", 0.0):
                amount = max(0.01, float(round(amount / 10) * 10))

        # ── IP / Device / Location ─────────────────────────────────────────────
        if random.random() < params.get("foreign_ip_prob", 0.5):
            ip         = f"{random.randint(1,223)}.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(1,254)}"
            foreign_ip = 1
        else:
            ip         = f"{user.home_ip_prefix}.{random.randint(1,254)}.{random.randint(1,254)}"
            foreign_ip = 0

        device_id = (user.primary_device
                     if random.random() < params.get("same_device_prob", 0.5)
                     else str(uuid.uuid4())[:8])
        new_device = int(device_id != user.primary_device)

        ship_same = random.random() < params.get("same_location_prob", 0.3)
        cross_border = int(
            (not ship_same) or (merchant.country_code != user.home_country)
        )
        new_ship_addr = int(not ship_same)

        # ── EMVCo 3DS fraud signals ───────────────────────────────────────────
        # Velocity: fraud bursts show high velocity
        velocity_1h  = max(
            burst_total if burst_total > 1 else 1,
            params.get("velocity_txns_per_hour", random.randint(5, 40)),
        )
        velocity_24h = velocity_1h + random.randint(0, 20)

        # trans_status for fraud: mostly Y (auth succeeded — fraud got through)
        # or N/U (attempt blocked)
        trans_status = random.choices(
            ["Y", "Y", "Y", "N", "U", "A"],
            weights=[0.55, 0.20, 0.10, 0.08, 0.05, 0.02]
        )[0]
        eci = "05" if trans_status == "Y" else ("06" if trans_status == "A" else "07")

        # Challenge: fraud rows rarely get challenged (that's the point)
        acs_challenge = "N" if random.random() < 0.8 else "Y"
        challenge_done = False

        # Account info anomalies for fraud
        acct_open_ind  = random.choices(
            ["01", "02", "03", "04"],
            weights=[0.45, 0.25, 0.20, 0.10]     # new/recently opened account bias
        )[0]
        txn_activity_day = velocity_1h               # unusually high

        # Amount ratio (fraud amounts often far from user's average)
        avg_amt = max(self.bp["Normal_User_Profile"]["transaction_amount"]["mean"], 1)
        amt_ratio = round(amount / avg_amt, 3)

        iso_alpha = _weighted_choice(self.cur_w)
        currency  = _currency_code(iso_alpha)

        return {
            # Transaction IDs
            "threeds_server_trans_id":   str(uuid.uuid4()),
            "acs_trans_id":              str(uuid.uuid4()),
            "ds_trans_id":               str(uuid.uuid4()),
            "sdk_trans_id":              str(uuid.uuid4()) if random.random() < 0.3 else "",
            "message_version":           random.choices(["2.3.1", "2.2.0", "2.1.0"],
                                                        weights=[0.5, 0.35, 0.15])[0],
            "device_channel":            random.choices(["02", "01", "03"],
                                                        weights=[0.55, 0.35, 0.10])[0],
            "three_ds_requestor_id":     merchant.requestor_id,
            "three_ds_requestor_name":   merchant.requestor_name,
            # Account / Cardholder
            "acct_number":               _mask_pan(random.choice(user.card_numbers)),
            "card_expiry_date":          user.card_expiry,
            "acct_id":                   user.acct_id,
            "acct_type":                 _enum("acct_type"),
            "acct_info_chg_ind":         random.choices(
                                             ["01", "02", "03", "04"],
                                             weights=[0.5, 0.25, 0.15, 0.10])[0],
            "acct_info_open_acct_ind":   acct_open_ind,
            "acct_info_ship_addr_usage_ind": random.choices(
                                             ["01", "02", "03", "04"],
                                             weights=[0.45, 0.25, 0.20, 0.10])[0],
            "acct_info_txn_activity_day":   txn_activity_day,
            "acct_info_txn_activity_year":  random.randint(1, 20),
            "acct_info_prov_attempts_day":  random.randint(0, 5),
            "acct_info_nb_purchase_account":random.randint(0, 10),
            "ship_addr_match":           "N" if new_ship_addr else "Y",
            "ship_addr_usage_ind":       random.choices(
                                             ["01", "02", "03", "04"],
                                             weights=[0.5, 0.2, 0.2, 0.1])[0],
            "bill_addr_city":            user.home_city,
            "bill_addr_country":         user.home_country,
            "bill_addr_state":           _faker_or_fallback("state_abbr") if _fake else "CA",
            "email":                     user.email_hash,
            # Browser
            "browser_accept_header":     "text/html,application/xhtml+xml,*/*",
            "browser_ip":                ip,
            "browser_java_enabled":      random.random() < 0.1,
            "browser_javascript_enabled":True,
            "browser_language":          user.browser_language,
            "browser_color_depth":       _enum("browser_color_depth"),
            "browser_screen_height":     user.screen_h,
            "browser_screen_width":      user.screen_w,
            "browser_tz":                user.browser_tz,
            "browser_user_agent":        _browser_ua(),
            "sdk_app_id":                user.sdk_app_id,
            "sdk_enc_data":              "",
            "sdk_ephem_pub_key":         "",
            "sdk_max_timeout":           5,
            "sdk_reference_number":      f"EMVSDK_{random.randint(100000,999999)}",
            # Merchant
            "merchant_id":               merchant.merchant_id,
            "merchant_name":             merchant.merchant_name,
            "mcc":                       merchant.mcc,
            "acquirer_bin":              merchant.acquirer_bin,
            "acquirer_merchant_id":      merchant.acquirer_merchant_id,
            "merchant_country_code":     merchant.country_code,
            # Purchase
            "purchase_amount":           _purchase_amount_minor(amount),
            "purchase_currency":         currency,
            "purchase_exponent":         2,
            "purchase_date":             ts.strftime("%Y%m%d%H%M%S"),
            "trans_type":                _enum("trans_type"),
            "recurring_expiry":          "",
            "recurring_frequency":       0,
            # Auth request/response
            "three_ds_requestor_auth_ind": _enum("three_ds_requestor_auth_ind"),
            "three_ds_comp_ind":           _enum("three_ds_comp_ind"),
            "acs_challenge_mandated":      acs_challenge,
            "authentication_type":         _enum("authentication_type"),
            "trans_status":                trans_status,
            "trans_status_reason":         "" if trans_status == "Y" else _enum("trans_status_reason"),
            "eci":                         eci,
            "authentication_value":        _faker_or_fallback("sha256") if trans_status == "Y" else "",
            "acs_reference_number":        f"ACS{random.randint(100000,999999)}",
            "ds_reference_number":         f"DS{random.randint(1000000,9999999)}",
            "challenge_completed":         challenge_done,
            "challenge_cancel_ind":        "" if not challenge_done else _enum("challenge_cancel_ind"),
            # Prior auth
            "three_ds_requestor_prior_auth_ind": _enum("three_ds_requestor_prior_auth_ind"),
            "prior_auth_method":           _enum("prior_auth_method"),
            "prior_auth_timestamp":        "",
            # Risk signals
            "ship_indicator":              random.choices(
                                               ["01", "03", "05"],
                                               weights=[0.3, 0.4, 0.3])[0],
            "delivery_timeframe":          _enum("delivery_timeframe"),
            "reorder_items_ind":           _enum("reorder_items_ind"),
            "pre_order_purchase_ind":      _enum("pre_order_purchase_ind"),
            "gift_card_amount":            round(amount * random.uniform(0, 0.5), 2)
                                           if random.random() < 0.15 else 0.0,
            "gift_card_count":             random.randint(0, 3) if random.random() < 0.1 else 0,
            "purchase_instal_data":        0,
            # Derived ML features
            "velocity_1h":                 velocity_1h,
            "velocity_24h":                velocity_24h,
            "amount_vs_avg_ratio":         amt_ratio,
            "new_device_flag":             new_device,
            "new_shipping_addr_flag":      new_ship_addr,
            "cross_border_flag":           cross_border,
            "high_risk_mcc_flag":          _is_high_risk_mcc(merchant.mcc),
            "time_since_acct_open_days":   random.randint(0, 90)
                                           if acct_open_ind in ("01", "02") else random.randint(30, 365),
            # Ground truth
            "fraud_label":                 1,
            "fraud_pattern":               pattern.get("pattern_name", "unknown"),
        }


# ─── Top-level Engine ─────────────────────────────────────────────────────────

class DatasetEngine:
    """
    Orchestrates the full EMVCo 3DS dataset generation pipeline from a v2 blueprint.
    No LLM involvement — fully deterministic given a seed.
    """

    def __init__(self, blueprint: Dict[str, Any], seed: int = 42):
        # Normalise at construction time so all downstream code sees a clean blueprint
        self.bp   = _normalise_blueprint(blueprint)
        self.seed = seed
        random.seed(seed)
        np.random.seed(seed)

    def generate(self) -> pd.DataFrame:
        specs         = self.bp["Dataset_Specifications"]
        total_rows    = specs["total_rows"]
        fraud_ratio   = specs["fraud_ratio"]
        num_users     = specs["num_users"]
        num_merchants = specs["num_merchants"]
        inj_rules     = self.bp["Fraud_Injection_Rules"]

        n_fraud  = int(total_rows * fraud_ratio)
        n_normal = total_rows - n_fraud

        # Derive MCC pool from scenario name
        scenario_name = self.bp.get("Fraud_Scenario_Name", "")
        mcc_pool = _mcc_for_scenario(scenario_name)

        user_pool = UserPool(
            num_users        = num_users,
            fraud_user_ratio = inj_rules["fraud_user_ratio"],
            seed             = self.seed,
        )
        merchant_pool = MerchantPool(
            num_merchants    = num_merchants,
            category_weights = self.bp["Normal_User_Profile"]["merchant_category_weights"],
            mcc_pool         = mcc_pool,
            seed             = self.seed,
        )

        normal_gen = NormalGenerator(self.bp, user_pool, merchant_pool)
        normal_df  = normal_gen.generate(n_normal)

        fraud_inj = FraudInjector(self.bp, user_pool, merchant_pool)
        fraud_df  = fraud_inj.generate(n_fraud)

        if inj_rules.get("contaminate_normal_users") and inj_rules.get("contamination_prob", 0) > 0:
            contamination_rows = self._contaminate(
                normal_df, fraud_inj, inj_rules["contamination_prob"]
            )
            fraud_df = pd.concat([fraud_df, contamination_rows], ignore_index=True)

        df = pd.concat([normal_df, fraud_df], ignore_index=True)
        df = df.sample(frac=1, random_state=self.seed).reset_index(drop=True)
        df = df.sort_values("purchase_date").reset_index(drop=True)
        df = df.head(total_rows)
        df = self._add_derived_columns(df)
        df = self._enforce_types(df)

        return df

    def _contaminate(self, normal_df: pd.DataFrame,
                     fraud_inj: FraudInjector,
                     prob: float) -> pd.DataFrame:
        contaminated: List[Dict] = []
        for uid in normal_df["acct_id"].unique():
            if random.random() < prob:
                pattern = random.choice(self.bp["Fraud_Patterns"])
                user    = UserProfile(
                    user_id          = uid,
                    acct_id          = uid,
                    home_city        = "Unknown",
                    home_country     = "840",
                    home_ip_prefix   = "10.0",
                    primary_device   = str(uuid.uuid4())[:8],
                    sdk_app_id       = str(uuid.uuid4()),
                    pan              = _make_pan(),
                    card_expiry      = "2812",
                    email_hash       = _hash_email(f"{uid}@contaminated.invalid"),
                    acct_open_ind    = "01",
                    browser_language = "en-US",
                    browser_tz       = -300,
                    screen_w         = 1920,
                    screen_h         = 1080,
                    is_fraudster     = True,
                    card_numbers     = [_make_pan()],
                )
                params = pattern.get("params", {})
                contaminated.append(fraud_inj._single_fraud_row(user, pattern, params))
        return pd.DataFrame(contaminated)

    def _add_derived_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add time-based features parsed from EMVCo purchase_date (YYYYMMDDHHmmss)."""
        df = df.copy()
        try:
            parsed_ts = pd.to_datetime(df["purchase_date"], format="%Y%m%d%H%M%S", errors="coerce")
        except Exception:
            parsed_ts = pd.to_datetime(df["purchase_date"], errors="coerce")

        df["hour_of_day"] = parsed_ts.dt.hour.fillna(0).astype(int)
        df["day_of_week"] = parsed_ts.dt.dayofweek.fillna(0).astype(int)
        df["is_weekend"]  = df["day_of_week"].isin([5, 6]).astype(int)
        df["purchase_amount_decimal"] = df["purchase_amount"] / 100.0  # minor → decimal
        return df

    def _enforce_types(self, df: pd.DataFrame) -> pd.DataFrame:
        int_cols = [
            "purchase_amount", "purchase_exponent", "recurring_frequency",
            "acct_info_txn_activity_day", "acct_info_txn_activity_year",
            "acct_info_prov_attempts_day", "acct_info_nb_purchase_account",
            "browser_screen_height", "browser_screen_width", "browser_tz",
            "sdk_max_timeout", "velocity_1h", "velocity_24h",
            "new_device_flag", "new_shipping_addr_flag", "cross_border_flag",
            "high_risk_mcc_flag", "time_since_acct_open_days",
            "gift_card_count", "purchase_instal_data",
            "fraud_label", "hour_of_day", "day_of_week", "is_weekend",
        ]
        float_cols = [
            "amount_vs_avg_ratio", "gift_card_amount", "purchase_amount_decimal"
        ]
        bool_cols = [
            "browser_java_enabled", "browser_javascript_enabled", "challenge_completed"
        ]

        for c in int_cols:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0).astype(int)
        for c in float_cols:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0.0).round(4)
        for c in bool_cols:
            if c in df.columns:
                df[c] = df[c].astype(bool)
        for c in df.select_dtypes(include="object").columns:
            df[c] = df[c].fillna("").astype(str)

        return df


# ─── Public save helper ───────────────────────────────────────────────────────

def save_dataset(df: pd.DataFrame, output_path: str, fmt: str = "csv") -> None:
    """Save DataFrame to the specified path and format."""
    import os
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    fmt = fmt.lower()
    if fmt == "csv":
        df.to_csv(output_path, index=False)
    elif fmt == "json":
        df.to_json(output_path, orient="records", date_format="iso", indent=2)
    elif fmt == "parquet":
        df.to_parquet(output_path, index=False)
    elif fmt == "excel":
        df.to_excel(output_path, index=False)
    else:
        df.to_csv(output_path, index=False)