"""
generate_data.py
-----------------
Creates a synthetic batch of two revenue-leak event types, mirroring what a
real Razorpay merchant's data would look like:

  1. payment_failure      -> a payment attempt that failed (card/UPI/netbanking)
  2. checkout_abandonment -> a customer who left before completing checkout

No real user data is used anywhere. Names are drawn from a small public list
of common Indian first/last names purely for realism in the demo.

Run directly to write CSVs into ../data/
"""

import csv
import random
from datetime import datetime, timedelta

random.seed(42)  # reproducible batch -> reproducible recovery metrics

FIRST_NAMES = [
    "Aarav", "Vivaan", "Aditya", "Vihaan", "Arjun", "Sai", "Reyansh",
    "Ishaan", "Kabir", "Rohan", "Ananya", "Diya", "Priya", "Isha",
    "Saanvi", "Myra", "Anika", "Kavya", "Riya", "Neha",
]
LAST_NAMES = [
    "Sharma", "Verma", "Gupta", "Iyer", "Nair", "Reddy", "Singh",
    "Mehta", "Joshi", "Kapoor", "Chatterjee", "Bhatt", "Rao", "Malhotra",
]

PAYMENT_METHODS = ["UPI", "Card", "NetBanking", "Wallet"]
DEVICES = ["mobile", "desktop"]
SEGMENTS = ["new", "returning", "high_value"]

# Failure codes modelled loosely on real gateway/issuer decline reasons.
# weight = how commonly this failure occurs in a typical batch
FAILURE_CODES = [
    ("INSUFFICIENT_FUNDS", 0.22),
    ("CARD_EXPIRED", 0.12),
    ("BANK_SERVER_TIMEOUT", 0.16),
    ("OTP_MISMATCH", 0.14),
    ("ISSUER_DECLINED", 0.13),
    ("DAILY_LIMIT_EXCEEDED", 0.09),
    ("NETWORK_ERROR", 0.09),
    ("MANDATE_EXPIRED", 0.05),
]

ABANDON_STAGES = [
    ("otp_screen", 0.30),
    ("payment_page", 0.35),
    ("review_page", 0.20),
    ("address_page", 0.15),
]


def _weighted_choice(pairs):
    options, weights = zip(*pairs)
    return random.choices(options, weights=weights, k=1)[0]


def _random_name():
    return f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"


def _random_timestamp(days_back=14):
    now = datetime(2026, 8, 31, 10, 0, 0)
    delta = timedelta(
        days=random.randint(0, days_back),
        hours=random.randint(0, 23),
        minutes=random.randint(0, 59),
    )
    return now - delta


def generate_payment_failures(n=140):
    rows = []
    for i in range(n):
        is_sub = random.random() < 0.25
        code = _weighted_choice(FAILURE_CODES)
        # subscriptions are far more likely to fail via MANDATE_EXPIRED
        if is_sub and random.random() < 0.4:
            code = "MANDATE_EXPIRED"
        rows.append({
            "event_id": f"pay_{i+1:04d}",
            "event_type": "payment_failure",
            "customer_id": f"cust_{random.randint(1000, 4999)}",
            "customer_name": _random_name(),
            "amount": round(random.uniform(299, 24999), 2),
            "payment_method": random.choice(PAYMENT_METHODS),
            "failure_code": code,
            "is_subscription": is_sub,
            "customer_segment": random.choice(SEGMENTS),
            "timestamp": _random_timestamp().isoformat(),
        })
    return rows


def generate_checkout_abandonment(n=60):
    rows = []
    for i in range(n):
        rows.append({
            "event_id": f"cart_{i+1:04d}",
            "event_type": "checkout_abandonment",
            "customer_id": f"cust_{random.randint(1000, 4999)}",
            "customer_name": _random_name(),
            "amount": round(random.uniform(199, 15999), 2),
            "payment_method": "",
            "failure_code": _weighted_choice(ABANDON_STAGES),  # reused as "stage_dropped"
            "is_subscription": False,
            "customer_segment": random.choice(SEGMENTS),
            "timestamp": _random_timestamp().isoformat(),
        })
    return rows


def write_csv(rows, path):
    fieldnames = [
        "event_id", "event_type", "customer_id", "customer_name", "amount",
        "payment_method", "failure_code", "is_subscription",
        "customer_segment", "timestamp",
    ]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    import os
    out_dir = os.path.join(os.path.dirname(__file__), "..", "data")
    os.makedirs(out_dir, exist_ok=True)

    events = generate_payment_failures(140) + generate_checkout_abandonment(60)
    random.shuffle(events)
    path = os.path.join(out_dir, "synthetic_events.csv")
    write_csv(events, path)
    print(f"Wrote {len(events)} synthetic events to {path}")
