"""
core/dataset_engine.py

Static, deterministic fraud dataset engine.
Reads a validated v2 blueprint and generates a synthetic dataset
WITHOUT relying on an LLM to write generation code.

Architecture
------------
1. UserPool        – builds a fixed set of realistic user profiles
2. MerchantPool    – builds a fixed set of merchants
3. NormalGenerator – generates baseline transaction streams per user
4. FraudInjector   – overlays fraud patterns on top of normal activity
5. DatasetEngine   – orchestrates everything and returns a DataFrame
"""

from __future__ import annotations

import random
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

try:
    from faker import Faker
    _fake = Faker()
    Faker.seed(42)
except ImportError:
    _fake = None


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _clamp(val: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, val))


def _weighted_choice(weights_dict: Dict[str, float]) -> str:
    keys   = list(weights_dict.keys())
    probs  = [weights_dict[k] for k in keys]
    total  = sum(probs)
    probs  = [p / total for p in probs]
    return random.choices(keys, weights=probs, k=1)[0]


def _sanitise_weights(weights_dict, fallback: dict) -> dict:
    """
    Ensure a weights dict has at least one numeric value.
    Returns fallback if the dict is missing, empty, or has no numeric values.
    Strips non-numeric entries so _weighted_choice never crashes.
    """
    if not isinstance(weights_dict, dict) or not weights_dict:
        return fallback
    clean = {k: v for k, v in weights_dict.items() if isinstance(v, (int, float))}
    return clean if clean else fallback


def _sample_amount(dist: str, mn: float, mx: float,
                   mean: float, std: float) -> float:
    """Sample a transaction amount from the configured distribution."""
    if dist == "lognormal":
        sigma = std / mean if mean > 0 else 0.5
        mu    = np.log(mean) - 0.5 * sigma ** 2
        v     = np.random.lognormal(mu, sigma)
    elif dist == "normal":
        v = np.random.normal(mean, std)
    elif dist == "pareto":
        b = mean / (mean - mn) if mean > mn else 2.0
        v = (np.random.pareto(b) + 1) * mn
    else:  # uniform
        v = np.random.uniform(mn, mx)
    return round(float(_clamp(max(0.01, v), mn, mx)), 2)


def _sample_timestamp(start: datetime, end: datetime,
                       peak_start: int, peak_end: int,
                       off_peak_weight: float,
                       preferred_hours: Optional[List[int]] = None) -> datetime:
    """Sample a datetime biased toward peak or preferred hours."""
    delta = (end - start).total_seconds()
    ts    = start + timedelta(seconds=random.uniform(0, delta))

    if preferred_hours:
        if random.random() > 0.15:
            ts = ts.replace(hour=random.choice(preferred_hours),
                            minute=random.randint(0, 59),
                            second=random.randint(0, 59))
    else:
        hour = ts.hour
        in_peak = peak_start <= hour <= peak_end
        if not in_peak and random.random() > off_peak_weight:
            ts = ts.replace(
                hour=random.randint(peak_start, peak_end),
                minute=random.randint(0, 59),
                second=random.randint(0, 59),
            )
    return ts


def _faker_or_fallback(method: str, *args, **kwargs):
    """Call faker method if available, else return a placeholder."""
    if _fake:
        return getattr(_fake, method)(*args, **kwargs)
    return f"fake_{method}_{random.randint(1000, 9999)}"


# ─── Data Classes ─────────────────────────────────────────────────────────────

@dataclass
class UserProfile:
    user_id: str
    home_city: str
    home_ip_prefix: str
    primary_device: str
    is_fraudster: bool = False
    card_numbers: List[str] = field(default_factory=list)


@dataclass
class MerchantProfile:
    merchant_id: str
    category: str
    city: str


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

    def _make_user(self, uid: str, is_fraudster: bool) -> UserProfile:
        ip_a = random.randint(10, 220)
        ip_b = random.randint(0, 255)
        cards = [_faker_or_fallback("credit_card_number", card_type="visa")
                 for _ in range(random.randint(1, 3))]
        return UserProfile(
            user_id        = uid,
            home_city      = _faker_or_fallback("city"),
            home_ip_prefix = f"{ip_a}.{ip_b}",
            primary_device = str(uuid.uuid4())[:8],
            is_fraudster   = is_fraudster,
            card_numbers   = cards,
        )


class MerchantPool:
    def __init__(self, num_merchants: int,
                 category_weights: Dict[str, float], seed: int = 42):
        random.seed(seed)
        self.merchants: List[MerchantProfile] = []
        for i in range(num_merchants):
            cat = _weighted_choice(category_weights)
            self.merchants.append(MerchantProfile(
                merchant_id = f"M{i:05d}",
                category    = cat,
                city        = _faker_or_fallback("city"),
            ))
        self._by_category: Dict[str, List[MerchantProfile]] = {}
        for m in self.merchants:
            self._by_category.setdefault(m.category, []).append(m)

    def random_merchant(self,
                        category: Optional[str] = None,
                        n: int = 1) -> List[MerchantProfile]:
        pool = self._by_category.get(category, self.merchants) if category else self.merchants
        if not pool:
            pool = self.merchants
        return random.choices(pool, k=n)


# ─── Normal Transaction Generator ─────────────────────────────────────────────

class NormalGenerator:
    """Generates realistic baseline transactions for non-fraudulent users."""

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

        df = pd.DataFrame(rows[:target_n])
        return df

    def _allocate(self, total: int, n_users: int) -> List[int]:
        lam    = max(1, total / n_users)
        counts = np.random.poisson(lam, size=n_users).tolist()
        actual = sum(counts)
        if actual == 0:
            counts = [1] * n_users
            actual = n_users
        scaled = [int(c * total / actual) for c in counts]
        diff   = total - sum(scaled)
        for i in range(abs(diff)):
            scaled[i % n_users] += 1 if diff > 0 else -1
        return scaled

    def _make_row(self, user: UserProfile) -> Dict:
        cat      = _weighted_choice(self.cat_w)
        merchant = self.merchants.random_merchant(category=cat)[0]
        currency = _weighted_choice(self.cur_w)
        amount   = _sample_amount(
            self.amt_cfg["distribution"],
            self.amt_cfg["min"], self.amt_cfg["max"],
            self.amt_cfg["mean"], self.amt_cfg["std"],
        )
        ts = _sample_timestamp(
            self.start, self.end,
            self.hour_cfg["peak_start"], self.hour_cfg["peak_end"],
            self.hour_cfg["off_peak_weight"],
        )
        location = (
            _faker_or_fallback("city")
            if random.random() < self.loc_prob
            else user.home_city
        )
        device_id = (
            str(uuid.uuid4())[:8]
            if random.random() < self.dev_prob
            else user.primary_device
        )
        ip   = f"{user.home_ip_prefix}.{random.randint(1, 254)}.{random.randint(1, 254)}"
        card = random.choice(user.card_numbers)

        return {
            "transaction_id":     str(uuid.uuid4()),
            "timestamp":          ts,
            "user_id":            user.user_id,
            "card_number":        card,
            "bin_number":         card[:6],
            "merchant_id":        merchant.merchant_id,
            "merchant_category":  merchant.category,
            "transaction_amount": amount,
            "currency":           currency,
            "location":           location,
            "device_id":          device_id,
            "ip_address":         ip,
            "foreign_ip_flag":    0,
            "fraud_label":        0,
        }


# ─── Fraud Injector ────────────────────────────────────────────────────────────

class FraudInjector:
    """
    Reads the blueprint's Fraud_Patterns and Sequence_Rules to generate
    fraud transactions that are statistically distinguishable from normal ones.
    """

    def __init__(self, blueprint: Dict[str, Any],
                 user_pool: UserPool, merchant_pool: MerchantPool):
        self.bp        = blueprint
        self.users     = user_pool
        self.merchants = merchant_pool

        specs      = blueprint["Dataset_Specifications"]
        self.start = datetime.fromisoformat(specs["date_range_start"])
        self.end   = datetime.fromisoformat(specs["date_range_end"])

        self.patterns  = blueprint["Fraud_Patterns"]
        self.inj_rules = blueprint["Fraud_Injection_Rules"]
        self.seq_rules = blueprint["Sequence_Rules"]
        self.cur_w     = _sanitise_weights(
            blueprint["Normal_User_Profile"].get("currency_weights"),
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

    def _generate_pattern_batch(
        self, user: UserProfile, pattern: Dict, max_txns: int
    ) -> List[Dict]:
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
        """Many transactions in a short time window against few merchants."""
        _bmn = params.get("burst_min_txns", 5)
        _bmx = max(_bmn, min(params.get("burst_max_txns", 20), max_txns))
        n = random.randint(_bmn, _bmx)
        window_mins = params.get("burst_window_mins", 30)

        anchor = _sample_timestamp(
            self.start, self.end, 0, 23, 0.1,
            params.get("preferred_hours"),
        )

        n_merchants = max(1, params.get("num_merchants", 1))
        merchants   = self.merchants.random_merchant(n=n_merchants)

        rows = []
        for i in range(n):
            offset_secs = random.uniform(0, max(1, window_mins * 60))
            ts = anchor + timedelta(seconds=offset_secs)
            m  = random.choice(merchants)
            rows.append(self._build_row(user, pattern, params, ts, m))
        return rows

    def _chain(self, user: UserProfile, pattern: Dict,
               params: Dict, max_txns: int) -> List[Dict]:
        """Sequential escalating transactions — each follows the last."""
        _cmn = params.get("burst_min_txns", 3)
        _cmx = max(_cmn, min(params.get("burst_max_txns", 8), max_txns))
        n = random.randint(_cmn, _cmx)
        gap_min = self.seq_rules.get("inter_txn_gap_seconds", {}).get("min", 30)
        gap_max = self.seq_rules.get("inter_txn_gap_seconds", {}).get("max", 300)
        gap_min = min(gap_min, gap_max)

        ts_cur = _sample_timestamp(
            self.start, self.end, 0, 23, 0.1,
            params.get("preferred_hours"),
        )
        n_merchants = max(1, params.get("num_merchants", 3))
        merchants   = self.merchants.random_merchant(n=n_merchants)

        rows = []
        a_min = max(0.01, params.get("amount_min", 1.0))
        a_max = params.get("amount_max", 500.0)
        for i in range(n):
            frac   = i / max(n - 1, 1)
            a_mean = a_min + frac * (a_max - a_min)
            a_std  = params.get("amount_std", (a_max - a_min) * 0.1)
            amount = round(float(_clamp(
                max(0.01, np.random.normal(a_mean, a_std)), a_min, a_max
            )), 2)

            m = random.choice(merchants)
            row = self._build_row(user, pattern, params, ts_cur, m,
                                  amount_override=amount)
            rows.append(row)
            ts_cur += timedelta(seconds=random.uniform(gap_min, gap_max))
        return rows

    def _network(self, user: UserProfile, pattern: Dict,
                 params: Dict, max_txns: int) -> List[Dict]:
        """Multi-account / smurfing pattern."""
        n_accounts  = max(1, params.get("num_accounts", 5))
        n_merchants = max(1, params.get("num_merchants", 3))

        smurf_users = [
            UserProfile(
                user_id        = f"SMURF_{user.user_id}_{i}",
                home_city      = user.home_city,
                home_ip_prefix = user.home_ip_prefix,
                primary_device = str(uuid.uuid4())[:8],
                is_fraudster   = True,
                card_numbers   = [_faker_or_fallback("credit_card_number",
                                                      card_type="visa")],
            )
            for i in range(n_accounts)
        ]
        merchants = self.merchants.random_merchant(n=n_merchants)
        anchor    = _sample_timestamp(
            self.start, self.end, 0, 23, 0.1,
            params.get("preferred_hours"),
        )
        rows = []
        per_account = max(1, max_txns // n_accounts)
        for su in smurf_users:
            for j in range(random.randint(1, per_account)):
                offset = timedelta(seconds=random.uniform(0, 3600))
                ts     = anchor + offset
                m      = random.choice(merchants)
                rows.append(self._build_row(su, pattern, params, ts, m))
        return rows[:max_txns]

    # ── Row builder ───────────────────────────────────────────────────────────

    def _single_fraud_row(self, user: UserProfile,
                          pattern: Dict, params: Dict) -> Dict:
        ts = _sample_timestamp(
            self.start, self.end, 0, 23, 0.1,
            params.get("preferred_hours"),
        )
        m = self.merchants.random_merchant()[0]
        return self._build_row(user, pattern, params, ts, m)

    def _build_row(self, user: UserProfile, pattern: Dict, params: Dict,
                   ts: datetime, merchant: MerchantProfile,
                   amount_override: Optional[float] = None) -> Dict:
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

        if random.random() < params.get("foreign_ip_prob", 0.5):
            ip         = f"{random.randint(1,223)}.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(1,254)}"
            foreign_ip = 1
        else:
            ip         = f"{user.home_ip_prefix}.{random.randint(1,254)}.{random.randint(1,254)}"
            foreign_ip = 0

        if random.random() < params.get("same_device_prob", 0.5):
            device_id = user.primary_device
        else:
            device_id = str(uuid.uuid4())[:8]

        if random.random() < params.get("same_location_prob", 0.3):
            location = user.home_city
        else:
            location = _faker_or_fallback("city")

        card = random.choice(user.card_numbers)

        return {
            "transaction_id":     str(uuid.uuid4()),
            "timestamp":          ts,
            "user_id":            user.user_id,
            "card_number":        card,
            "bin_number":         card[:6],
            "merchant_id":        merchant.merchant_id,
            "merchant_category":  merchant.category,
            "transaction_amount": amount,
            "currency":           _weighted_choice(self.cur_w),
            "location":           location,
            "device_id":          device_id,
            "ip_address":         ip,
            "foreign_ip_flag":    foreign_ip,
            "fraud_label":        1,
        }


# ─── Top-level Engine ─────────────────────────────────────────────────────────

class DatasetEngine:
    """
    Orchestrates the full dataset generation pipeline from a v2 blueprint.
    No LLM involvement — fully deterministic given a seed.
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
        num_users     = specs["num_users"]
        num_merchants = specs["num_merchants"]
        inj_rules     = self.bp["Fraud_Injection_Rules"]

        n_fraud  = int(total_rows * fraud_ratio)
        n_normal = total_rows - n_fraud

        user_pool = UserPool(
            num_users        = num_users,
            fraud_user_ratio = inj_rules["fraud_user_ratio"],
            seed             = self.seed,
        )
        merchant_pool = MerchantPool(
            num_merchants    = num_merchants,
            category_weights = self.bp["Normal_User_Profile"]["merchant_category_weights"],
            seed             = self.seed,
        )

        normal_gen = NormalGenerator(self.bp, user_pool, merchant_pool)
        normal_df  = normal_gen.generate(n_normal)

        fraud_inj = FraudInjector(self.bp, user_pool, merchant_pool)
        fraud_df  = fraud_inj.generate(n_fraud)

        if inj_rules.get("contaminate_normal_users") and inj_rules.get("contamination_prob", 0) > 0:
            contamination_rows = self._contaminate(
                normal_df, fraud_inj,
                inj_rules["contamination_prob"],
            )
            fraud_df = pd.concat([fraud_df, contamination_rows], ignore_index=True)

        df = pd.concat([normal_df, fraud_df], ignore_index=True)
        df = df.sample(frac=1, random_state=self.seed).reset_index(drop=True)
        df = df.sort_values("timestamp").reset_index(drop=True)
        df = df.head(total_rows)
        df = self._add_derived_columns(df)
        df = self._enforce_types(df)

        return df

    def _contaminate(self, normal_df: pd.DataFrame,
                     fraud_inj: FraudInjector,
                     prob: float) -> pd.DataFrame:
        contaminated: List[Dict] = []
        for uid in normal_df["user_id"].unique():
            if random.random() < prob:
                pattern = random.choice(self.bp["Fraud_Patterns"])
                user    = UserProfile(
                    user_id        = uid,
                    home_city      = "Unknown",
                    home_ip_prefix = "10.0",
                    primary_device = str(uuid.uuid4())[:8],
                    is_fraudster   = True,
                    card_numbers   = ["4" + "".join([str(random.randint(0, 9)) for _ in range(15)])],
                )
                params = pattern.get("params", {})
                contaminated.append(fraud_inj._single_fraud_row(user, pattern, params))
        return pd.DataFrame(contaminated)

    def _add_derived_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df["hour_of_day"] = pd.to_datetime(df["timestamp"]).dt.hour
        df["day_of_week"] = pd.to_datetime(df["timestamp"]).dt.dayofweek
        df["is_weekend"]  = df["day_of_week"].isin([5, 6]).astype(int)
        df["amount_log"]  = np.log1p(df["transaction_amount"])
        return df

    def _enforce_types(self, df: pd.DataFrame) -> pd.DataFrame:
        df["timestamp"]          = pd.to_datetime(df["timestamp"])
        df["transaction_amount"] = df["transaction_amount"].astype(float).round(2)
        df["fraud_label"]        = df["fraud_label"].astype(int)
        df["foreign_ip_flag"]    = df["foreign_ip_flag"].astype(int)
        df["hour_of_day"]        = df["hour_of_day"].astype(int)
        df["day_of_week"]        = df["day_of_week"].astype(int)
        df["is_weekend"]         = df["is_weekend"].astype(int)
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