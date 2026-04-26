
import random
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

LEGIT_CATEGORIES = [
    "ecommerce", "food_delivery", "groceries", "fashion",
    "travel", "entertainment", "electronics", "beauty",
]
LEGIT_DEVICES = ["mobile", "desktop", "tablet"]


# ── Card ID / BIN helpers ─────────────────────────────────────────────────────

def _make_card_id(bin_prefix: str) -> str:
    """Generate a card ID with a proper 6-digit BIN prefix + 10 random digits."""
    suffix = fake.numerify(text="##########")  # Faker: 10 random digits
    return f"{bin_prefix}{suffix}"


def _random_bin() -> str:
    """Generate a random 6-digit BIN for legitimate cards."""
    return fake.numerify(text="######")  # Faker: 6 random digits


# ── Amount samplers ───────────────────────────────────────────────────────────

def _sample_amounts(n: int, amt_min: float, amt_max: float, distribution: str) -> np.ndarray:
    """Sample n amounts from the specified distribution within [amt_min, amt_max]."""
    if distribution == "normal":
        mean = (amt_min + amt_max) / 2
        std  = (amt_max - amt_min) / 4
        amounts = np.random.normal(mean, std, n)
    elif distribution == "skewed_low":
        amounts = np.random.beta(2, 5, n) * (amt_max - amt_min) + amt_min
    elif distribution == "skewed_high":
        amounts = np.random.beta(5, 2, n) * (amt_max - amt_min) + amt_min
    else:  # uniform (default)
        amounts = np.random.uniform(amt_min, amt_max, n)

    return np.clip(np.round(amounts, 2), amt_min, amt_max)


# ── Fraud row generator (from blueprint) ─────────────────────────────────────

def _generate_fraud_rows(blueprint: dict, count: int, start_date: datetime) -> list[dict]:
    """
    Generates fraud rows from the LLM blueprint using NumPy for distributions.
    Faker used only for transaction_id (uuid) and card number generation.
    All statistical patterns come from the blueprint.
    """
    bp = blueprint
    rows = []

    # ── Derive card pool ──────────────────────────────────────────────────
    num_cards  = min(bp["num_unique_cards"], count)
    bin_prefix = bp["bin_prefix"]
    shared_bin = bp.get("shared_bin", True)

    card_pool = []
    for _ in range(num_cards):
        if shared_bin:
            card_pool.append(_make_card_id(bin_prefix))
        else:
            card_pool.append(_make_card_id(_random_bin()))

    # ── Sample amounts (NumPy) ────────────────────────────────────────────
    amounts = _sample_amounts(
        count, bp["amount_min"], bp["amount_max"], bp["amount_distribution"]
    )

    # ── Generate timestamps (NumPy) ───────────────────────────────────────
    window_hours = bp["time_window_hours"]
    clustering   = bp.get("time_clustering", "burst")

    if clustering == "burst":
        burst_start = start_date + timedelta(days=random.randint(0, 5))
        offsets = np.random.uniform(0, window_hours * 3600, count)
    else:
        burst_start = start_date
        offsets = np.random.uniform(0, 30 * 24 * 3600, count)

    offsets.sort()

    # ── Assign cards to transactions ──────────────────────────────────────
    velocity = bp["velocity_per_card"]
    card_assignments = []
    for card_id in card_pool:
        card_assignments.extend([card_id] * velocity)

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
            "transaction_id":    fake.uuid4(),           # Faker
            "card_id":           card_id,
            "bin":               card_id[:6],
            "amount":            float(amounts[i]),       # NumPy
            "merchant":          random.choice(merchants),
            "merchant_category": random.choice(categories),
            "country":           random.choice(countries),
            "device":            random.choice(devices),
            "timestamp":         ts.isoformat(),
            "is_fraud":          True,
        })

    return rows


# ── Legitimate row generator ─────────────────────────────────────────────────

def _generate_legit_rows(count: int, start_date: datetime) -> list[dict]:
    """
    Generates realistic non-fraud transactions.

    Faker handles:  transaction IDs, card numbers, merchant names,
                    countries, timestamps
    NumPy handles:  amount distribution (normal around $120)
    """
    # NumPy — amounts normally distributed around typical spend
    amounts = np.clip(np.random.normal(loc=120, scale=45, size=count), 5.0, 800.0)
    amounts = np.round(amounts, 2)

    end_date = start_date + timedelta(days=30)

    rows = []
    for i in range(count):
        bin_prefix = _random_bin()                      # Faker: 6 random digits
        card_id    = _make_card_id(bin_prefix)          # Faker: BIN + 10 digits

        # Faker: realistic timestamp spread across 30 days
        ts = fake.date_time_between(
            start_date=start_date,
            end_date=end_date,
        )

        rows.append({
            "transaction_id":    fake.uuid4(),              # Faker: unique UUID
            "card_id":           card_id,                   # Faker: card number
            "bin":               bin_prefix,                # Faker: 6-digit BIN
            "amount":            float(amounts[i]),          # NumPy: normal distribution
            "merchant":          fake.company(),             # Faker: realistic company names
            "merchant_category": random.choice(LEGIT_CATEGORIES),
            "country":           fake.country_code(),        # Faker: diverse countries
            "device":            random.choice(LEGIT_DEVICES),
            "timestamp":         ts.isoformat(),             # Faker: spread timestamps
            "is_fraud":          False,
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
