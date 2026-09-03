"""
main.py
-------
One command, full loop:
    python main.py

1. Generates a fresh synthetic batch of 200 revenue-leak events
   (140 failed payments + 60 abandoned checkouts)
2. Diagnoses root cause for each
3. Runs the bounded recovery workflow (retries, waits, stopping rules)
4. Writes the audit trail (outputs/audit_trail.csv)
5. Writes a human-readable HTML report (outputs/recovery_report.html)
6. Writes a machine-readable summary (outputs/summary.json)
7. Prints headline numbers to the terminal
"""

import os

from src.generate_data import generate_payment_failures, generate_checkout_abandonment, write_csv
from src.pipeline import run_pipeline
from src.audit import write_audit_trail
from src.report import generate_html_report, write_summary_json

BASE_DIR = os.path.dirname(__file__)
DATA_DIR = os.path.join(BASE_DIR, "data")
OUT_DIR = os.path.join(BASE_DIR, "outputs")


def main():
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(OUT_DIR, exist_ok=True)

    print("→ Generating synthetic event batch...")
    import random
    random.seed(42)
    events = generate_payment_failures(140) + generate_checkout_abandonment(60)
    random.shuffle(events)
    events_path = os.path.join(DATA_DIR, "synthetic_events.csv")
    write_csv(events, events_path)
    print(f"  {len(events)} events written to {events_path}")

    print("→ Running diagnosis + bounded recovery workflow...")
    audit_rows, metrics = run_pipeline(events_path)

    audit_path = os.path.join(OUT_DIR, "audit_trail.csv")
    write_audit_trail(audit_rows, audit_path)
    print(f"  Audit trail ({len(audit_rows)} attempt rows) written to {audit_path}")

    report_path = os.path.join(OUT_DIR, "recovery_report.html")
    generate_html_report(metrics, audit_rows, report_path)
    print(f"  HTML report written to {report_path}")

    summary_path = os.path.join(OUT_DIR, "summary.json")
    write_summary_json(metrics, summary_path)
    print(f"  Summary JSON written to {summary_path}")

    print("\n--- Headline numbers ---")
    print(f"Events processed:      {metrics['total_events']}")
    print(f"Event recovery rate:   {metrics['event_recovery_rate']*100:.1f}%")
    print(f"Revenue at risk:       ₹{metrics['total_at_risk']:,.0f}")
    print(f"Revenue recovered:     ₹{metrics['recovered_amount']:,.0f} "
          f"({metrics['amount_recovery_rate']*100:.1f}%)")
    print(f"Total recovery attempts made: {metrics['total_attempts']}")


if __name__ == "__main__":
    main()
