import random
import pandas as pd
from faker import Faker
from datetime import datetime, timedelta

fake = Faker()


# ── Schema ────────────────────────────────────────────────────────────────────
# Must match the agreed shared schema from the team's Google Doc.
# Adjust field names here if the team changes the spec.

REQUIRED_FIELDS = [
    "transaction_id",
    "card_id",
    "bin",
    "amount",
    "merchant",
    "country",
    "device",
    "timestamp",
    "is_fraud",
]

MERCHANT_LIST = [
    "Amazon", "Flipkart", "Swiggy", "Zomato", "BigBasket",
    "Myntra", "MakeMyTrip", "BookMyShow", "Nykaa", "Croma",
]

COUNTRY_LIST = ["IN", "US", "GB", "AE", "SG", "DE", "AU", "CA"]
DEVICE_LIST  = ["mobile", "desktop", "tablet"]


# ── Legitimate transaction generator ─────────────────────────────────────────

def _generate_legitimate_transactions(count: int, start_date: datetime) -> list[dict]:
    """
    Uses Faker to produce `count` realistic, non-fraud transactions.
    Amounts are normally distributed around a typical basket size.
    Timestamps are spread across 30 days from start_date.
    """
    rows = []
    for _ in range(count):
        amount = round(max(5.0, random.gauss(mu=80, sigma=30)), 2)  # realistic spend
        timestamp = start_date + timedelta(
            days=random.randint(0, 29),
            hours=random.randint(0, 23),
            minutes=random.randint(0, 59),
        )
        card_id = fake.bothify(text="CARD-####-####-####")
        bin_val = card_id[5:9]  # first 4 digits after "CARD-"

        rows.append({
            "transaction_id": fake.uuid4(),
            "card_id":        card_id,
            "bin":            bin_val,
            "amount":         amount,
            "merchant":       random.choice(MERCHANT_LIST),
            "country":        random.choice(COUNTRY_LIST),
            "device":         random.choice(DEVICE_LIST),
            "timestamp":      timestamp.isoformat(),
            "is_fraud":       False,
        })
    return rows


# ── Fraud row validator ───────────────────────────────────────────────────────

def _validate_and_clean_fraud_rows(raw_rows: list[dict]) -> list[dict]:
    """
    Filters out rows from LLM output that are missing required fields
    or have wrong data types. Marks all surviving rows as is_fraud=True.
    """
    clean = []
    for row in raw_rows:
        # Check every required field is present
        if not all(field in row for field in REQUIRED_FIELDS if field != "is_fraud"):
            continue

        # Coerce types where possible; skip if unrecoverable
        try:
            row["amount"]    = float(row["amount"])
            row["timestamp"] = str(row["timestamp"])
            row["is_fraud"]  = True  # LLM rows are always fraud
        except (ValueError, TypeError):
            continue

        clean.append(row)
    return clean


# ── Main builder ──────────────────────────────────────────────────────────────

def build_dataset(
    fraud_rows: list[dict],
    total_volume: int,
    fraud_ratio: float,
    start_date: datetime | None = None,
) -> pd.DataFrame:
    """
    Combines LLM-generated fraud rows with Faker-generated legit rows.

    Parameters
    ----------
    fraud_rows   : list of dicts returned by llm_client (already parsed JSON)
    total_volume : total number of rows in the final dataset
    fraud_ratio  : fraction of rows that should be fraud (e.g. 0.1 = 10%)
    start_date   : base date for timestamps; defaults to 30 days ago

    Returns
    -------
    pd.DataFrame  shuffled, with all REQUIRED_FIELDS present
    """
    if start_date is None:
        start_date = datetime.now() - timedelta(days=30)

    # Validate and cap fraud rows to what was requested
    target_fraud_count = int(total_volume * fraud_ratio)
    clean_fraud = _validate_and_clean_fraud_rows(fraud_rows)

    if len(clean_fraud) < target_fraud_count:
        print(
            f"[data_builder] Warning: LLM returned {len(clean_fraud)} valid fraud rows, "
            f"but {target_fraud_count} were requested. Using what's available."
        )

    fraud_rows_final = clean_fraud[:target_fraud_count]

    # Generate legit rows to fill the remainder
    legit_count       = total_volume - len(fraud_rows_final)
    legit_rows        = _generate_legitimate_transactions(legit_count, start_date)

    # Merge, shuffle, and return
    all_rows = fraud_rows_final + legit_rows
    random.shuffle(all_rows)

    df = pd.DataFrame(all_rows, columns=REQUIRED_FIELDS)
    df.reset_index(drop=True, inplace=True)

    print(
        f"[data_builder] Dataset built: {len(df)} rows | "
        f"{df['is_fraud'].sum()} fraud | {(~df['is_fraud']).sum()} legit"
    )
    return df


# ── CSV export ────────────────────────────────────────────────────────────────

def save_dataset(df: pd.DataFrame, path: str = "transactions.csv") -> None:
    """Saves the DataFrame to CSV. Called after Student 2 adds rule_triggered."""
    df.to_csv(path, index=False)
    print(f"[data_builder] Saved to {path}")
