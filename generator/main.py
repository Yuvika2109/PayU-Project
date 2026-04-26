

import pandas as pd
from datetime import datetime, timedelta

try:
    from prompt_builder import build_prompt
    from llm_client     import get_fraud_blueprint
    from data_builder   import build_dataset, save_dataset
except ImportError:
    from .prompt_builder import build_prompt
    from .llm_client     import get_fraud_blueprint
    from .data_builder   import build_dataset, save_dataset


# ── Minimum volume guardrail ──────────────────────────────────────────────────
MIN_VOLUME = 100   # never generate fewer than 100 rows


# ── Integration contract ──────────────────────────────────────────────────────

def run_generation(
    scenario: str,
    total_volume: int = 200,
    fraud_ratio: float = 0.2,
) -> pd.DataFrame:
    """
    PUBLIC FUNCTION — called by Student 4's Streamlit UI.

    Parameters
    ----------
    scenario      : free-text description of the fraud scenario
                    e.g. "BIN attack where fraudsters test cards rapidly"
                    or just "BIN Attack" / "Account Takeover"
    total_volume  : total number of transactions (fraud + legit), min 100
    fraud_ratio   : fraction that should be fraud, e.g. 0.2 for 20%

    Returns
    -------
    pd.DataFrame with columns:
        transaction_id, card_id, bin, amount, merchant,
        merchant_category, country, device, timestamp, is_fraud
    """
    # Enforce minimums
    total_volume = max(total_volume, MIN_VOLUME)
    fraud_ratio  = max(0.05, min(fraud_ratio, 0.95))

    fraud_count = max(1, int(total_volume * fraud_ratio))

    print(f"\n{'='*60}")
    print(f"  FraudSynth — Generation Pipeline")
    print(f"  Scenario     : {scenario[:80]}")
    print(f"  Total volume : {total_volume}")
    print(f"  Fraud ratio  : {fraud_ratio:.0%}  →  {fraud_count} fraud rows")
    print(f"{'='*60}\n")

    # Step 1 — Build prompt asking for a blueprint
    prompt = build_prompt(scenario=scenario, fraud_count=fraud_count)

    # Step 2 — Get blueprint from Ollama (single LLM call)
    blueprint = get_fraud_blueprint(prompt)
    print(f"[main] Blueprint summary:")
    print(f"       Amount range : ${blueprint['amount_min']:.2f} – ${blueprint['amount_max']:.2f}")
    print(f"       Velocity     : {blueprint['velocity_per_card']} txns/card")
    print(f"       Unique cards : {blueprint['num_unique_cards']}")
    print(f"       BIN prefix   : {blueprint['bin_prefix']}")
    print(f"       Clustering   : {blueprint['time_clustering']}")

    # Step 3 — Build dataset programmatically from blueprint
    df = build_dataset(
        blueprint=blueprint,
        total_volume=total_volume,
        fraud_ratio=fraud_ratio,
        start_date=datetime.now() - timedelta(days=15),
    )

    print(f"\n  Generation complete — {df.shape[0]} rows, "
          f"{df['is_fraud'].sum()} fraud, {(~df['is_fraud']).sum()} legit.\n")
    return df


# ── CLI entry point ───────────────────────────────────────────────────────────

def _ask_input(prompt_text: str, default: str = "") -> str:
    raw = input(prompt_text).strip()
    return raw if raw else default


if __name__ == "__main__":
    print("=" * 60)
    print("  PayU FraudSynth — Data Generator")
    print("=" * 60)

    scenario = _ask_input(
        "\nDescribe the fraud scenario (or type 'BIN Attack' / 'Account Takeover'):\n> "
    )
    if not scenario:
        scenario = "BIN Attack"
        print(f"  Using default: {scenario}")

    vol_str = _ask_input("Total transactions [200]: ", "200")
    total_volume = int(vol_str) if vol_str.isdigit() else 200

    pct_str = _ask_input("Fraud percentage [20]: ", "20")
    try:
        fraud_ratio = float(pct_str) / 100
    except ValueError:
        fraud_ratio = 0.2

    output_path = _ask_input("Output filename [transactions.csv]: ", "transactions.csv")

    df = run_generation(
        scenario=scenario,
        total_volume=total_volume,
        fraud_ratio=fraud_ratio,
    )

    save_dataset(df, path=output_path)

    print(f"\nSample (first 5 rows):")
    print(df.head().to_string(index=False))
    print(f"\nDataset saved to: {output_path}")
    print(f"Total: {len(df)} rows | {df['is_fraud'].sum()} fraud | {(~df['is_fraud']).sum()} legit")