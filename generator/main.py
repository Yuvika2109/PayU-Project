from prompt_builder import build_prompt
from llm_client import call_llm
from data_builder import build_dataset


def get_user_input():
    print("Select Scenario:")
    print("1. BIN_ATTACK")
    print("2. ACCOUNT_TAKEOVER")

    choice = input("Enter choice (1 or 2): ")

    if choice == "1":
        scenario = "BIN_ATTACK"
    elif choice == "2":
        scenario = "ACCOUNT_TAKEOVER"
    else:
        raise ValueError("Invalid scenario selected")

    total_txn = int(input("Enter total number of transactions: "))
    fraud_ratio = float(input("Enter fraud ratio (e.g., 0.02 for 2%): "))

    return scenario, total_txn, fraud_ratio


def main():
    scenario, total_txn, fraud_ratio = get_user_input()

    prompt = build_prompt(scenario)
    blueprint = call_llm(prompt)

    df = build_dataset(blueprint, scenario, total_txn, fraud_ratio)

    file_name = f"{scenario.lower()}_dataset.csv"
    df.to_csv(file_name, index=False)

    print(f"\nDataset generated successfully: {file_name}")


if __name__ == "__main__":
    main()