import unittest

from src.diagnose import diagnose


class TestDiagnose(unittest.TestCase):
    def _event(self, failure_code):
        return {
            "event_id": "test_001",
            "event_type": "payment_failure",
            "customer_id": "cust_1",
            "customer_name": "Test User",
            "amount": 1000.0,
            "payment_method": "UPI",
            "failure_code": failure_code,
            "is_subscription": False,
            "customer_segment": "new",
            "timestamp": "2026-08-31T10:00:00",
        }

    def test_known_failure_code_maps_to_correct_root_cause(self):
        result = diagnose(self._event("CARD_EXPIRED"))
        self.assertEqual(result["root_cause"], "expired_card")
        self.assertIn("max_attempts", result)
        self.assertIn("wait_hours", result)
        self.assertIn("est_success_prob", result)

    def test_every_known_code_has_bounded_attempts(self):
        """Every rule must cap retries -- this is the 'stopping rules'
        requirement, checked structurally so nobody can accidentally add
        an unbounded rule later."""
        from src.diagnose import ROOT_CAUSE_RULES
        for code, rule in ROOT_CAUSE_RULES.items():
            self.assertGreaterEqual(rule["max_attempts"], 1, f"{code} has no attempt cap")
            self.assertLessEqual(rule["max_attempts"], 5, f"{code} attempt cap looks unbounded")

    def test_unknown_failure_code_falls_back_gracefully(self):
        """An unrecognized code must never crash the pipeline -- it should
        route to a conservative manual-review bucket instead."""
        result = diagnose(self._event("SOME_NEW_CODE_NOT_IN_TABLE"))
        self.assertEqual(result["root_cause"], "unclassified")
        self.assertEqual(result["max_attempts"], 1)

    def test_success_probabilities_are_valid_probabilities(self):
        from src.diagnose import ROOT_CAUSE_RULES
        for code, rule in ROOT_CAUSE_RULES.items():
            self.assertGreaterEqual(rule["est_success_prob"], 0.0)
            self.assertLessEqual(rule["est_success_prob"], 1.0)


if __name__ == "__main__":
    unittest.main()
