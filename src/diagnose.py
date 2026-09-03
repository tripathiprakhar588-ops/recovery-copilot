"""
diagnose.py
-----------
Rule-based root-cause classifier. Deliberately NOT a black-box ML model:
for a money-moving workflow, a transparent decision table is easier to
audit, easier to defend to a judge/reviewer, and just as effective when
failure codes are already structured (which they are, from any payment
gateway webhook).

Each root cause carries the metadata the recovery engine needs:
  - recommended_action : human-readable description of the intervention
  - wait_hours          : how long to wait before attempting recovery
  - max_attempts        : hard cap on retries (this is the "bounded" part)
  - est_success_prob    : assumed probability a single recovery attempt
                           succeeds. THESE ARE ILLUSTRATIVE ASSUMPTIONS,
                           documented here and in the README, not claims
                           about real-world Razorpay data. Swap in real
                           historical rates once available.
"""

ROOT_CAUSE_RULES = {
    "INSUFFICIENT_FUNDS": {
        "root_cause": "insufficient_funds",
        "recommended_action": "Delay retry to allow salary/balance refresh, send reminder nudge",
        "wait_hours": 48,
        "max_attempts": 3,
        "est_success_prob": 0.35,
    },
    "CARD_EXPIRED": {
        "root_cause": "expired_card",
        "recommended_action": "Send update-payment-method link, no auto-retry",
        "wait_hours": 2,
        "max_attempts": 2,
        "est_success_prob": 0.28,
    },
    "BANK_SERVER_TIMEOUT": {
        "root_cause": "bank_timeout",
        "recommended_action": "Immediate auto-retry (transient failure)",
        "wait_hours": 1,
        "max_attempts": 3,
        "est_success_prob": 0.55,
    },
    "OTP_MISMATCH": {
        "root_cause": "otp_failure",
        "recommended_action": "Prompt fresh OTP flow immediately",
        "wait_hours": 0,
        "max_attempts": 2,
        "est_success_prob": 0.50,
    },
    "ISSUER_DECLINED": {
        "root_cause": "issuer_decline",
        "recommended_action": "Suggest alternate payment method, do not retry same card",
        "wait_hours": 6,
        "max_attempts": 2,
        "est_success_prob": 0.22,
    },
    "DAILY_LIMIT_EXCEEDED": {
        "root_cause": "limit_exceeded",
        "recommended_action": "Delay to next day, then retry",
        "wait_hours": 24,
        "max_attempts": 2,
        "est_success_prob": 0.40,
    },
    "NETWORK_ERROR": {
        "root_cause": "network_drop",
        "recommended_action": "Immediate auto-retry (transient failure)",
        "wait_hours": 1,
        "max_attempts": 3,
        "est_success_prob": 0.60,
    },
    "MANDATE_EXPIRED": {
        "root_cause": "mandate_expired",
        "recommended_action": "Send e-mandate re-authorization link, no auto-retry",
        "wait_hours": 4,
        "max_attempts": 2,
        "est_success_prob": 0.25,
    },
    # checkout_abandonment stages are reused via the same "failure_code" column
    "otp_screen": {
        "root_cause": "abandon_at_otp",
        "recommended_action": "Immediate nudge: OTP expired, tap to resend",
        "wait_hours": 0.5,
        "max_attempts": 2,
        "est_success_prob": 0.45,
    },
    "payment_page": {
        "root_cause": "abandon_at_payment",
        "recommended_action": "Nudge with saved-cart link + incentive-free reminder",
        "wait_hours": 2,
        "max_attempts": 2,
        "est_success_prob": 0.30,
    },
    "review_page": {
        "root_cause": "abandon_at_review",
        "recommended_action": "Nudge: items still in cart, price/stock unchanged",
        "wait_hours": 3,
        "max_attempts": 2,
        "est_success_prob": 0.32,
    },
    "address_page": {
        "root_cause": "abandon_at_address",
        "recommended_action": "Nudge to complete address + resume checkout link",
        "wait_hours": 3,
        "max_attempts": 2,
        "est_success_prob": 0.28,
    },
}


def diagnose(event: dict) -> dict:
    """Given a raw event row, attach root-cause metadata. Unknown codes
    fall back to a conservative single-attempt manual-review bucket so the
    pipeline never silently drops an event."""
    code = event["failure_code"]
    rule = ROOT_CAUSE_RULES.get(code, {
        "root_cause": "unclassified",
        "recommended_action": "Route to manual review",
        "wait_hours": 24,
        "max_attempts": 1,
        "est_success_prob": 0.15,
    })
    return {**event, **rule}
