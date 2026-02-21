import pandas as pd
from datetime import datetime

from prompt_builder import build_prompt, SUPPORTED_SCENARIOS
from llm_client     import generate_fraud_transactions
from data_builder   import build_dataset, save_dataset


# ── Integration contract ──────────────────────────────────────────────────────

def run_generation(
    scenario: str,
    total_volume: int,
    fraud_ratio: float,
) -> pd.DataFrame:
    """
    PUBLIC FUNCTION — called by Student 4's Streamlit UI.

    Parameters
    ----------
    scenario      : "BIN Attack" or "Account Takeover"
    total_volume  : total number of transactions to generate (fraud + legit)
    fraud_ratio   : fraction that should be fraud, e.g. 0.1 for 10%

    Returns
    -------
    pd.DataFrame with columns:
        transaction_id, card_id, bin, amount, merchant,
        country, device, timestamp, is_fraud
    """
    print(f"\n{'='*60}")
    print(f"  Starting generation pipeline")
    print(f"  Scenario     : {scenario}")
    print(f"  Total volume : {total_volume}")
    print(f"  Fraud ratio  : {fraud_ratio:.0%}  →  {int(total_volume * fraud_ratio)} fraud rows")
    print(f"{'='*60}\n")

    fraud_count    = max(1, int(total_volume * fraud_ratio))
    prompt         = build_prompt(scenario=scenario, fraud_count=fraud_count)
    raw_fraud_rows = generate_fraud_transactions(prompt, total_needed=fraud_count)

    df = build_dataset(
        fraud_rows=raw_fraud_rows,
        total_volume=total_volume,
        fraud_ratio=fraud_ratio,
        start_date=datetime.now(),
    )

    print(f"\n  Generation complete — {df.shape[0]} rows ready.")
    return df


# ── Interactive input collection ──────────────────────────────────────────────

def _ask_scenario() -> str:
    """Presents a numbered menu and returns the chosen scenario name."""
    print("\nSelect a fraud scenario:")
    for i, name in enumerate(SUPPORTED_SCENARIOS, start=1):
        print(f"  {i}. {name}")

    while True:
        raw = input("Enter number: ").strip()
        if raw.isdigit() and 1 <= int(raw) <= len(SUPPORTED_SCENARIOS):
            return SUPPORTED_SCENARIOS[int(raw) - 1]
        print(f"  Please enter a number between 1 and {len(SUPPORTED_SCENARIOS)}.")


def _ask_volume() -> int:
    """Asks for total transaction volume with basic validation."""
    while True:
        raw = input("Total number of transactions to generate (e.g. 200): ").strip()
        if raw.isdigit() and int(raw) > 0:
            return int(raw)
        print("  Please enter a positive whole number.")


def _ask_fraud_ratio() -> float:
    """Asks for fraud ratio as a percentage and converts to a float."""
    while True:
        raw = input("Fraud percentage (e.g. 10 for 10%): ").strip()
        try:
            value = float(raw)
            if 0 < value < 100:
                return round(value / 100, 4)
            print("  Please enter a value between 1 and 99.")
        except ValueError:
            print("  Please enter a number (e.g. 10).")


def _ask_output_path() -> str:
    """Asks where to save the CSV, defaulting to transactions.csv."""
    raw = input("Output filename [transactions.csv]: ").strip()
    return raw if raw else "transactions.csv"


# ── Main entry point ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("  PayU Fraud Data Generator")
    print("=" * 60)

    scenario     = _ask_scenario()
    total_volume = _ask_volume()
    fraud_ratio  = _ask_fraud_ratio()
    output_path  = _ask_output_path()

    df = run_generation(
        scenario=scenario,
        total_volume=total_volume,
        fraud_ratio=fraud_ratio,
    )

    save_dataset(df, path=output_path)

    print(f"\nSample (first 5 rows):")
    print(df.head().to_string(index=False))
    print(f"\nFull dataset saved to: {output_path}")