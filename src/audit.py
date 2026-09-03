"""
audit.py
--------
Every action the agent takes gets written to a flat, human-readable audit
trail. This is intentionally boring and simple (a CSV) rather than a
database, because for a money-adjacent workflow, "any reviewer can open
this in Excel and check our work" beats a clever schema.
"""

import csv


AUDIT_FIELDS = [
    "event_id", "event_type", "customer_id", "root_cause", "attempt_number",
    "attempt_timestamp", "action_taken", "message_sent", "amount", "outcome",
]


def write_audit_trail(rows, path):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=AUDIT_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
