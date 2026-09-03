"""
recover.py
----------
Executes the bounded recovery workflow for a single diagnosed event.

This is the piece the buildathon brief calls out specifically: "Don't just
identify the problem... with compliant escalation, stopping rules, and an
audit trail." So the rules here are explicit and enforced in code, not
just described in a slide:

  STOPPING RULES
  1. Stop immediately once an attempt succeeds.
  2. Never exceed `max_attempts` for that root cause (set in diagnose.py).
  3. Each attempt is spaced by `wait_hours` — we do not re-contact a
     customer back-to-back.
  4. After the final attempt fails, the event is marked `unrecovered` and
     escalated to manual review instead of retried indefinitely.

Outcome simulation: since this is a synthetic batch (no live payment
gateway), we simulate whether an attempt succeeds using the root cause's
`est_success_prob`, with a mild decay per repeat attempt (diminishing
returns — a customer who ignored the first nudge is less likely to
convert on the third). This is clearly a simulation, not a claim about
real recovery rates, and is documented as such in the README.
"""

import random
from datetime import datetime, timedelta

from .messaging import generate_message

random.seed(7)  # separate seed from data generation, still reproducible


def _simulate_attempt_outcome(base_prob: float, attempt_number: int) -> bool:
    decayed_prob = base_prob * (0.75 ** (attempt_number - 1))
    return random.random() < decayed_prob


def recover_event(diagnosed_event: dict) -> list:
    """Runs the bounded recovery loop for one event.
    Returns a list of audit-log rows (one per attempt)."""
    log_rows = []
    ts = datetime.fromisoformat(diagnosed_event["timestamp"])

    for attempt in range(1, diagnosed_event["max_attempts"] + 1):
        attempt_ts = ts + timedelta(hours=diagnosed_event["wait_hours"] * attempt)
        message = generate_message(
            diagnosed_event["root_cause"],
            diagnosed_event["customer_name"],
            diagnosed_event["amount"],
            diagnosed_event["event_id"],
        )
        success = _simulate_attempt_outcome(
            diagnosed_event["est_success_prob"], attempt
        )

        log_rows.append({
            "event_id": diagnosed_event["event_id"],
            "event_type": diagnosed_event["event_type"],
            "customer_id": diagnosed_event["customer_id"],
            "root_cause": diagnosed_event["root_cause"],
            "attempt_number": attempt,
            "attempt_timestamp": attempt_ts.isoformat(),
            "action_taken": diagnosed_event["recommended_action"],
            "message_sent": message,
            "amount": diagnosed_event["amount"],
            "outcome": "recovered" if success else "failed",
        })

        if success:
            break  # stopping rule 1: stop on success

    else:
        # loop completed without break -> exhausted all attempts
        log_rows.append({
            "event_id": diagnosed_event["event_id"],
            "event_type": diagnosed_event["event_type"],
            "customer_id": diagnosed_event["customer_id"],
            "root_cause": diagnosed_event["root_cause"],
            "attempt_number": diagnosed_event["max_attempts"] + 1,
            "attempt_timestamp": attempt_ts.isoformat(),
            "action_taken": "Escalated to manual review (attempts exhausted)",
            "message_sent": "",
            "amount": diagnosed_event["amount"],
            "outcome": "unrecovered_escalated",
        })

    return log_rows
