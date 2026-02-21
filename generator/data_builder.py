import random
import numpy as np
import pandas as pd
from faker import Faker

fake = Faker()


def generate_fraud_rows(scenario, fraud_count):
    rows = []

    for _ in range(fraud_count):

        if scenario == "BIN_ATTACK":
            amount = round(random.uniform(0.5, 5.0), 2)
            card_bin = "457891"
            device_type = "desktop"

        elif scenario == "ACCOUNT_TAKEOVER":
            amount = round(random.uniform(500, 5000), 2)
            card_bin = str(random.randint(400000, 499999))
            device_type = random.choice(["mobile", "desktop"])

        rows.append({
            "transaction_id": fake.uuid4(),
            "user_id": fake.uuid4(),
            "timestamp": fake.date_time_between(
                start_date="-2d",
                end_date="now"
            ).isoformat(),
            "amount": amount,
            "currency": "USD",
            "merchant_id": fake.uuid4(),
            "merchant_category": random.choice(
                ["electronics", "travel", "fashion"]
            ),
            "ip_address": fake.ipv4(),
            "country": random.choice(["US", "UK", "IN"]),
            "device_type": device_type,
            "card_bin": card_bin,
            "is_fraud": True
        })

    return rows


def generate_legit_rows(legit_count):
    rows = []

    for _ in range(legit_count):
        rows.append({
            "transaction_id": fake.uuid4(),
            "user_id": fake.uuid4(),
            "timestamp": fake.date_time_between(
                start_date="-30d",
                end_date="now"
            ).isoformat(),
            "amount": round(np.random.normal(80, 20), 2),
            "currency": "USD",
            "merchant_id": fake.uuid4(),
            "merchant_category": random.choice(
                ["grocery", "travel", "fashion"]
            ),
            "ip_address": fake.ipv4(),
            "country": random.choice(["US", "UK", "IN"]),
            "device_type": random.choice(["mobile", "desktop"]),
            "card_bin": str(random.randint(400000, 499999)),
            "is_fraud": False
        })

    return rows


def build_dataset(blueprint, scenario, total_txn, fraud_ratio):
    fraud_count = int(total_txn * fraud_ratio)
    legit_count = total_txn - fraud_count

    fraud_rows = generate_fraud_rows(scenario, fraud_count)
    legit_rows = generate_legit_rows(legit_count)

    all_rows = fraud_rows + legit_rows
    random.shuffle(all_rows)

    return pd.DataFrame(all_rows)