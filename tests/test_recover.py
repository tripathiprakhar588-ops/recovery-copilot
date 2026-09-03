import unittest

from src.diagnose import diagnose
from src.recover import recover_event


class TestRecover(unittest.TestCase):
    def _diagnosed_event(self, failure_code="INSUFFICIENT_FUNDS"):
        raw = {
            "event_id": "test_recover_001",
            "event_type": "payment_failure",
            "customer_id": "cust_1",
            "customer_name": "Test User",
            "amount": 5000.0,
            "payment_method": "UPI",
            "failure_code": failure_code,
            "is_subscription": False,
            "customer_segment": "new",
            "timestamp": "2026-08-31T10:00:00",
        }
        return diagnose(raw)

    def test_never_exceeds_max_attempts(self):
        """Core stopping-rule guarantee: total logged attempts (including
        the final escalation row, if any) never exceeds max_attempts + 1."""
        event = self._diagnosed_event()
        log = recover_event(event)
        real_attempts = [r for r in log if r["outcome"] != "unrecovered_escalated"]
        self.assertLessEqual(len(real_attempts), event["max_attempts"])

    def test_stops_immediately_on_success(self):
        """If any attempt succeeds, no further attempts should follow it."""
        event = self._diagnosed_event()
        log = recover_event(event)
        outcomes = [r["outcome"] for r in log]
        if "recovered" in outcomes:
            success_index = outcomes.index("recovered")
            self.assertEqual(success_index, len(outcomes) - 1,
                              "an attempt was logged after a successful recovery")

    def test_exhausted_attempts_escalate_not_retry_forever(self):
        """Force a root cause that will realistically fail every simulated
        attempt in most seeds (low probability) and confirm the loop ends
        in an explicit escalation row rather than looping indefinitely."""
        event = self._diagnosed_event("ISSUER_DECLINED")
        log = recover_event(event)
        # Either it recovered within the cap, or it explicitly escalated --
        # there is no third outcome, which is exactly the point.
        self.assertIn(log[-1]["outcome"], {"recovered", "unrecovered_escalated"})

    def test_every_row_has_required_audit_fields(self):
        event = self._diagnosed_event()
        log = recover_event(event)
        required = {
            "event_id", "event_type", "customer_id", "root_cause",
            "attempt_number", "attempt_timestamp", "action_taken",
            "message_sent", "amount", "outcome",
        }
        for row in log:
            self.assertTrue(required.issubset(row.keys()))


if __name__ == "__main__":
    unittest.main()
