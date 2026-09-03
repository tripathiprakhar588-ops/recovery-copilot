import unittest

from src.pipeline import compute_metrics


class TestMetrics(unittest.TestCase):
    def test_recovery_rate_matches_hand_calculated_example(self):
        """A tiny, fully hand-checkable batch: 2 events, 1 recovered."""
        events = [
            {"event_id": "e1", "event_type": "payment_failure", "amount": 100.0},
            {"event_id": "e2", "event_type": "payment_failure", "amount": 300.0},
        ]
        audit_rows = [
            {"event_id": "e1", "root_cause": "bank_timeout", "outcome": "failed"},
            {"event_id": "e1", "root_cause": "bank_timeout", "outcome": "recovered"},
            {"event_id": "e2", "root_cause": "bank_timeout", "outcome": "failed"},
            {"event_id": "e2", "root_cause": "bank_timeout", "outcome": "unrecovered_escalated"},
        ]
        metrics = compute_metrics(events, audit_rows)

        self.assertEqual(metrics["total_events"], 2)
        self.assertEqual(metrics["recovered_events"], 1)
        self.assertAlmostEqual(metrics["event_recovery_rate"], 0.5)
        self.assertAlmostEqual(metrics["total_at_risk"], 400.0)
        self.assertAlmostEqual(metrics["recovered_amount"], 100.0)
        self.assertAlmostEqual(metrics["unrecovered_amount"], 300.0)

    def test_empty_batch_does_not_divide_by_zero(self):
        metrics = compute_metrics([], [])
        self.assertEqual(metrics["total_events"], 0)
        self.assertEqual(metrics["event_recovery_rate"], 0)
        self.assertEqual(metrics["amount_recovery_rate"], 0)


if __name__ == "__main__":
    unittest.main()
