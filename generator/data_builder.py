

import random
import uuid
import numpy as np
import pandas as pd
from faker import Faker
from datetime import datetime, timedelta

fake = Faker()


# ── Schema (agreed contract) ──────────────────────────────────────────────────

REQUIRED_COLUMNS = [
    "transaction_id",
    "card_id",
    "bin",
    "amount",
    "merchant",
    "merchant_category",
    "country",
    "device",
    "timestamp",
    "is_fraud",
]

# ── Baseline parameters for legitimate transactions ───────────────────────────

LEGIT_MERCHANTS = [
    "Amazon", "Flipkart", "Swiggy", "Zomato", "BigBasket",
    "Myntra", "MakeMyTrip", "BookMyShow", "Nykaa", "Croma",
    "PhonePe", "Paytm Mall", "Tata CLiQ", "Ajio", "Meesho",
]
LEGIT_CATEGORIES = [
    "ecommerce", "food_delivery", "groceries", "fashion",
    "travel", "entertainment", "electronics", "beauty",
]
LEGIT_COUNTRIES = ["IN", "US", "GB", "AE", "SG", "DE", "AU", "CA"]
LEGIT_DEVICES   = ["mobile", "desktop", "tablet"]


# ── Card ID / BIN helpers ─────────────────────────────────────────────────────

def _make_card_id(bin_prefix: str) -> str:
    """Generate a card ID with a proper 6-digit BIN prefix + 10 random digits."""
    suffix = "".join([str(random.randint(0, 9)) for _ in range(10)])
    return f"{bin_prefix}{suffix}"


def _random_bin() -> str:
    """Generate a random 6-digit BIN for legitimate cards."""
    return "".join([str(random.randint(0, 9)) for _ in range(6)])


# ── Amount samplers ───────────────────────────────────────────────────────────

def _sample_amounts(n: int, amt_min: float, amt_max: float, distribution: str) -> np.ndarray:
    """Sample n amounts from the specified distribution within [amt_min, amt_max]."""
    if distribution == "normal":
        mean = (amt_min + amt_max) / 2
        std  = (amt_max - amt_min) / 4
        amounts = np.random.normal(mean, std, n)
    elif distribution == "skewed_low":
        # Beta distribution skewed toward lower end
        amounts = np.random.beta(2, 5, n) * (amt_max - amt_min) + amt_min
    elif distribution == "skewed_high":
        amounts = np.random.beta(5, 2, n) * (amt_max - amt_min) + amt_min
    else:  # uniform (default)
        amounts = np.random.uniform(amt_min, amt_max, n)

    return np.clip(np.round(amounts, 2), amt_min, amt_max)


# ── Fraud row generator (from blueprint) ─────────────────────────────────────

def _generate_fraud_rows(blueprint: dict, count: int, start_date: datetime) -> list[dict]:
    """
    Generates `count` fraud transaction rows by reading the LLM blueprint
    and sampling from the specified distributions using NumPy.
    """
    bp = blueprint
    rows = []

    # ── Derive card pool ──────────────────────────────────────────────────
    num_cards   = min(bp["num_unique_cards"], count)  # can't have more cards than rows
    bin_prefix  = bp["bin_prefix"]
    shared_bin  = bp.get("shared_bin", True)

    card_pool = []
    for _ in range(num_cards):
        if shared_bin:
            card_pool.append(_make_card_id(bin_prefix))
        else:
            card_pool.append(_make_card_id(_random_bin()))

    # ── Sample amounts ────────────────────────────────────────────────────
    amounts = _sample_amounts(
        count, bp["amount_min"], bp["amount_max"], bp["amount_distribution"]
    )

    # ── Generate timestamps ───────────────────────────────────────────────
    window_hours = bp["time_window_hours"]
    clustering   = bp.get("time_clustering", "burst")

    if clustering == "burst":
        # All fraud timestamps packed into the window
        burst_start = start_date + timedelta(days=random.randint(0, 5))
        offsets = np.random.uniform(0, window_hours * 3600, count)
    else:
        # Spread across the full 30-day period
        burst_start = start_date
        offsets = np.random.uniform(0, 30 * 24 * 3600, count)

    offsets.sort()  # chronological within the fraud cluster

    # ── Assign cards to transactions ──────────────────────────────────────
    # Distribute ~velocity_per_card transactions to each card
    velocity = bp["velocity_per_card"]
    card_assignments = []
    for card_id in card_pool:
        card_assignments.extend([card_id] * velocity)

    # Pad or trim to exactly `count`
    while len(card_assignments) < count:
        card_assignments.append(random.choice(card_pool))
    random.shuffle(card_assignments)
    card_assignments = card_assignments[:count]

    # ── Build rows ────────────────────────────────────────────────────────
    merchants  = bp.get("merchants", ["Amazon", "Steam"])
    categories = bp.get("merchant_categories", ["ecommerce"])
    countries  = bp.get("countries", ["US"])
    devices    = bp.get("devices", ["mobile"])

    for i in range(count):
        card_id = card_assignments[i]
        ts = burst_start + timedelta(seconds=float(offsets[i]))

        rows.append({
            "transaction_id":  str(uuid.uuid4()),
            "card_id":         card_id,
            "bin":             card_id[:6],
            "amount":          float(amounts[i]),
            "merchant":        random.choice(merchants),
            "merchant_category": random.choice(categories),
            "country":         random.choice(countries),
            "device":          random.choice(devices),
            "timestamp":       ts.isoformat(),
            "is_fraud":        True,
        })

    return rows


# ── Legitimate row generator ─────────────────────────────────────────────────

def _generate_legit_rows(count: int, start_date: datetime) -> list[dict]:
    """
    Generates `count` realistic non-fraud transactions using Faker + NumPy.
    Amounts normally distributed around $80–$200, spread across 30 days.
    """
    amounts = np.clip(np.random.normal(loc=120, scale=45, size=count), 5.0, 800.0)
    amounts = np.round(amounts, 2)

    rows = []
    for i in range(count):
        bin_prefix = _random_bin()
        card_id    = _make_card_id(bin_prefix)
        ts = start_date + timedelta(
            days=random.randint(0, 29),
            hours=random.randint(6, 23),   # realistic hours
            minutes=random.randint(0, 59),
            seconds=random.randint(0, 59),
        )

        rows.append({
            "transaction_id":  str(uuid.uuid4()),
            "card_id":         card_id,
            "bin":             bin_prefix,
            "amount":          float(amounts[i]),
            "merchant":        random.choice(LEGIT_MERCHANTS),
            "merchant_category": random.choice(LEGIT_CATEGORIES),
            "country":         random.choice(LEGIT_COUNTRIES),
            "device":          random.choice(LEGIT_DEVICES),
            "timestamp":       ts.isoformat(),
            "is_fraud":        False,
        })

    return rows


# ── Main builder ──────────────────────────────────────────────────────────────

def build_dataset(
    blueprint: dict,
    total_volume: int,
    fraud_ratio: float,
    start_date: datetime | None = None,
) -> pd.DataFrame:
    """
    Builds the full labeled dataset from the LLM blueprint.

    Parameters
    ----------
    blueprint    : validated blueprint dict from llm_client
    total_volume : total rows (fraud + legit)
    fraud_ratio  : fraction of fraud rows (e.g. 0.2 = 20%)
    start_date   : base date for all timestamps

    Returns
    -------
    pd.DataFrame with all REQUIRED_COLUMNS, shuffled, labeled
    """
    if start_date is None:
        start_date = datetime.now() - timedelta(days=30)

    fraud_count = max(1, int(total_volume * fraud_ratio))
    legit_count = total_volume - fraud_count

    print(f"[data_builder] Generating {fraud_count} fraud + {legit_count} legit rows...")

    fraud_rows = _generate_fraud_rows(blueprint, fraud_count, start_date)
    legit_rows = _generate_legit_rows(legit_count, start_date)

    all_rows = fraud_rows + legit_rows
    random.shuffle(all_rows)

    df = pd.DataFrame(all_rows, columns=REQUIRED_COLUMNS)
    df.reset_index(drop=True, inplace=True)

    print(
        f"[data_builder] Dataset built: {len(df)} rows | "
        f"{df['is_fraud'].sum()} fraud | {(~df['is_fraud']).sum()} legit"
    )
    return df


# ── CSV export ────────────────────────────────────────────────────────────────

def save_dataset(df: pd.DataFrame, path: str = "transactions.csv") -> None:
    df.to_csv(path, index=False)
    print(f"[data_builder] Saved to {path}")
