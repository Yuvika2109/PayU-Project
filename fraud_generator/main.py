"""
main.py  (v3)
Entry point for the Agentic Synthetic Fraud Dataset Generator.

Usage
-----
    python main.py                           # Interactive mode
    python main.py --scenario "..."          # CLI one-liner
    python main.py --demo bin_attack         # Built-in demo
    python main.py --blueprint path.json     # Skip LLM, use existing blueprint
"""

from __future__ import annotations

import argparse
import json
import sys
import textwrap
from pathlib import Path

_ROOT = Path(__file__).parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# NEW (v3): import interpreter separately so we can call it before the pipeline
from agents.scenario_interpreter import ScenarioInterpreterAgent
from core.pipeline import FraudDataPipeline
from utils.logger import get_logger

logger = get_logger("main")

DEMO_SCENARIOS = {
    "bin_attack": textwrap.dedent("""\
        Fraud Scenario: BIN Attack
        Rows: 10000
        Fraud Ratio: 5%
        Output Format: CSV
    """),
    "card_testing": textwrap.dedent("""\
        Fraud Scenario: Card Testing Fraud
        Rows: 5000
        Fraud Ratio: 8%
        Output Format: CSV
    """),
    "account_takeover": textwrap.dedent("""\
        Fraud Scenario: Account Takeover
        Rows: 20000
        Fraud Ratio: 3%
        Output Format: CSV
    """),
    "money_laundering": textwrap.dedent("""\
        Fraud Scenario: Money Laundering
        Rows: 5000
        Fraud Ratio: 33%
        Output Format: CSV
    """),
}

BANNER = """
╔══════════════════════════════════════════════════════════════════╗
║   Agentic Synthetic Fraud Dataset Generator  v3.0               ║
║   LLM → Quantitative Blueprint → Static Engine → Dataset        ║
╚══════════════════════════════════════════════════════════════════╝
"""

INTERACTIVE_HELP = """
Describe your fraud scenario in any of these formats:

  ① Plain English (just say what you want):
  ─────────────────────────────────────────────────────────────────
  "Generate a BIN attack dataset with 50,000 transactions,
   about 5% fraud. Save as CSV."

  "I need money laundering data — 10k rows, one-third fraud
   ratio, output in parquet."

  "Create card testing fraud data. 20 thousand transactions,
   8 percent fraud, JSON output please."

  ② Labelled format:                  ③ Inline shorthand:
  ─────────────────────────────────   ─────────────────────────────
  Fraud Scenario: Money Laundering    Money Laundering, 5000, 33%, csv
  Rows: 5000
  Fraud Ratio: 33%
  Output Format: CSV

Type 'demo' for a quick BIN Attack demo, 'quit' to exit.
"""


def _print_result(result) -> None:
    sep = "─" * 62
    if result.success:
        fraud_pct = 100.0 * result.fraud_rows / max(result.rows_generated, 1)
        print(f"\n{sep}")
        print("✅  PIPELINE COMPLETE")
        print(sep)
        print(f"  Scenario      : {result.scenario_params.get('scenario_name')}")
        print(f"  Total rows    : {result.rows_generated:,}")
        print(f"  Fraud rows    : {result.fraud_rows:,}  ({fraud_pct:.1f}%)")
        print(f"  Output file   : {result.output_path}")
        print(f"  Duration      : {result.duration_seconds:.1f}s")
        print(sep)
    else:
        print(f"\n{sep}")
        print("❌  PIPELINE FAILED")
        print(sep)
        print(f"  Error: {result.error}")
        print(sep)


# NEW (v3): echoes parsed params to the user BEFORE the slow blueprint LLM call
def _print_interpreted(params: dict) -> None:
    """Echo back what the interpreter extracted so the user can confirm."""
    sep = "─" * 62
    print(f"\n{sep}")
    print("🔍  INTERPRETED AS")
    print(sep)
    print(f"  Scenario      : {params.get('scenario_name', '—')}")
    print(f"  Fraud type    : {params.get('fraud_type', '—')}")
    print(f"  Total rows    : {params.get('rows', 0):,}")
    print(f"  Fraud ratio   : {params.get('fraud_ratio', 0) * 100:.1f}%")
    print(f"  Output format : {params.get('output_format', '—').upper()}")
    print(sep)
    print("  Generating blueprint…\n")


def run_interactive() -> None:
    print(BANNER)
    print(INTERACTIVE_HELP)

    # NEW (v3): one interpreter instance reused across the whole session
    interpreter = ScenarioInterpreterAgent()

    while True:
        try:
            lines: list[str] = []
            print("▶ ", end="", flush=True)

            while True:
                line = input()
                low  = line.lower().strip()
                if low in ("quit", "exit", "q"):
                    print("Goodbye!")
                    sys.exit(0)
                if low == "demo":
                    lines = [DEMO_SCENARIOS["bin_attack"]]
                    break
                if line == "" and lines:
                    break
                lines.append(line)
                # Single-line inline input — submit immediately
                if len(lines) == 1 and ("," in lines[0] or not lines[0]):
                    break

            raw = "\n".join(lines).strip()
            if not raw:
                print("No input — please try again.\n")
                continue

            print()

            # NEW (v3): interpret first → show params immediately → then run pipeline
            # This means the user sees "INTERPRETED AS" BEFORE the slow LLM call,
            # not after it (old behaviour printed it after pipeline returned).
            scenario_params = interpreter.interpret(raw)
            _print_interpreted(scenario_params)

            # run_from_params skips re-interpretation inside the pipeline
            result = FraudDataPipeline().run_from_params(scenario_params)
            _print_result(result)

            if result.blueprint:
                snippet = {k: result.blueprint[k] for k in (
                    "Fraud_Scenario_Name", "Fraud_Type", "Dataset_Specifications"
                ) if k in result.blueprint}
                print("\nBlueprint summary:")
                print(json.dumps(snippet, indent=2))
            print()

        except (KeyboardInterrupt, EOFError):
            print("\nInterrupted. Goodbye!")
            sys.exit(0)


def run_cli(scenario: str) -> int:
    # NEW (v3): interpret → show params → run, same pattern as interactive
    interpreter = ScenarioInterpreterAgent()
    scenario_params = interpreter.interpret(scenario)
    _print_interpreted(scenario_params)
    result = FraudDataPipeline().run_from_params(scenario_params)
    _print_result(result)
    return 0 if result.success else 1


def run_from_blueprint(blueprint_path: str) -> int:
    """Skip LLM entirely — load an existing blueprint and generate the dataset."""
    import json
    from core.dataset_engine import DatasetEngine, save_dataset
    from config.model_config import OUTPUT_DIR

    logger.info("Loading blueprint from: %s", blueprint_path)
    with open(blueprint_path, encoding="utf-8") as fh:
        blueprint = json.load(fh)

    engine = DatasetEngine(blueprint, seed=42)
    df     = engine.generate()

    specs  = blueprint.get("Dataset_Specifications", {})
    fmt    = specs.get("output_format", "csv")
    safe   = blueprint.get("Fraud_Scenario_Name", "fraud").lower().replace(" ", "_")
    output = str(Path(OUTPUT_DIR) / f"{safe}_synthetic_dataset.{fmt}")

    import os; os.makedirs(OUTPUT_DIR, exist_ok=True)
    save_dataset(df, output, fmt)

    fraud_rows = int(df["fraud_label"].sum())
    print(f"\n✅  Dataset generated from blueprint")
    print(f"   Rows: {len(df):,}   Fraud: {fraud_rows:,}   Output: {output}")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Agentic Synthetic Fraud Dataset Generator v3",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            Examples:
              python main.py
              python main.py --demo money_laundering
              python main.py --scenario "BIN Attack, 100000, 5%, csv"
              python main.py --scenario "Generate a money laundering dataset, 10k rows, 33% fraud, parquet"
              python main.py --blueprint output/synthetic_datasets/bin_attack_blueprint.json
        """),
    )
    parser.add_argument("--scenario",  type=str,
                        help="Scenario string — plain English, labelled, or inline")
    parser.add_argument("--blueprint", type=str,
                        help="Path to existing blueprint JSON (skips LLM)")
    parser.add_argument(
        "--demo", nargs="?", const="bin_attack",
        choices=list(DEMO_SCENARIOS.keys()),
        help="Run a built-in demo (default: bin_attack)",
    )
    args = parser.parse_args()

    if args.blueprint:
        sys.exit(run_from_blueprint(args.blueprint))
    elif args.demo:
        sys.exit(run_cli(DEMO_SCENARIOS[args.demo]))
    elif args.scenario:
        sys.exit(run_cli(args.scenario))
    else:
        run_interactive()


if __name__ == "__main__":
    main()