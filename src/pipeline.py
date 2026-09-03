"""
pipeline.py
-----------
Wires the whole loop together:
    load events -> diagnose -> recover (bounded loop) -> audit trail -> metrics

This is the module main.py and app.py both call. Keeping it separate from
the CLI/UI means the same logic powers a terminal run, a Streamlit demo,
or (later) a real webhook handler without duplication.
"""

import csv
from collections import defaultdict

from .diagnose import diagnose
from .recover import recover_event


def load_events(path):
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = []
        for row in reader:
            row["amount"] = float(row["amount"])
            row["is_subscription"] = row["is_subscription"] == "True"
            rows.append(row)
        return rows


def run_pipeline(events_path):
    events = load_events(events_path)

    audit_rows = []
    for event in events:
        diagnosed = diagnose(event)
        audit_rows.extend(recover_event(diagnosed))

    metrics = compute_metrics(events, audit_rows)
    return audit_rows, metrics


def compute_metrics(events, audit_rows):
    amount_by_event = {e["event_id"]: e["amount"] for e in events}
    type_by_event = {e["event_id"]: e["event_type"] for e in events}

    final_outcome = {}
    root_cause_by_event = {}
    for row in audit_rows:
        eid = row["event_id"]
        final_outcome[eid] = row["outcome"]  # last write wins -> final attempt
        root_cause_by_event[eid] = row["root_cause"]

    total_at_risk = sum(amount_by_event.values())
    recovered_amount = sum(
        amount_by_event[eid] for eid, outcome in final_outcome.items()
        if outcome == "recovered"
    )
    unrecovered_amount = total_at_risk - recovered_amount

    by_cause = defaultdict(lambda: {"count": 0, "recovered": 0, "at_risk": 0.0, "recovered_amt": 0.0})
    for eid, outcome in final_outcome.items():
        cause = root_cause_by_event[eid]
        by_cause[cause]["count"] += 1
        by_cause[cause]["at_risk"] += amount_by_event[eid]
        if outcome == "recovered":
            by_cause[cause]["recovered"] += 1
            by_cause[cause]["recovered_amt"] += amount_by_event[eid]

    by_type = defaultdict(lambda: {"count": 0, "recovered": 0})
    for eid, outcome in final_outcome.items():
        etype = type_by_event[eid]
        by_type[etype]["count"] += 1
        if outcome == "recovered":
            by_type[etype]["recovered"] += 1

    total_events = len(final_outcome)
    recovered_events = sum(1 for o in final_outcome.values() if o == "recovered")
    total_attempts = len(audit_rows)

    return {
        "total_events": total_events,
        "recovered_events": recovered_events,
        "event_recovery_rate": recovered_events / total_events if total_events else 0,
        "total_at_risk": total_at_risk,
        "recovered_amount": recovered_amount,
        "unrecovered_amount": unrecovered_amount,
        "amount_recovery_rate": recovered_amount / total_at_risk if total_at_risk else 0,
        "total_attempts": total_attempts,
        "avg_attempts_per_event": total_attempts / total_events if total_events else 0,
        "by_cause": dict(by_cause),
        "by_type": dict(by_type),
    }
