"""
messaging.py
------------
Generates the recovery nudge sent to the customer for a given root cause.

Two modes, chosen automatically:
  1. TEMPLATE MODE (default, no API key needed) -> fast, free, deterministic.
     This is what runs out of the box so anyone can clone the repo and see
     results with zero setup.
  2. AI MODE (if ANTHROPIC_API_KEY is set in the environment) -> calls the
     Claude API to lightly personalize the template's tone using the
     customer's name, amount and root cause. This is the "meaningful use
     of AI" layer on top of a system that is honest about not NEEDING an
     LLM call for every decision (only the messaging layer benefits).

Templates are bilingual (Hinglish + English) because the track explicitly
calls out Hinglish voice/text recovery as a differentiator for the Indian
market.
"""

import os

TEMPLATES = {
    "insufficient_funds": (
        "Hi {name}, aapka payment of ₹{amount} complete nahi ho paaya "
        "(insufficient balance). Jab convenient ho, dobara try kar sakte hain: {link}"
    ),
    "expired_card": (
        "Hi {name}, your card on file has expired, so ₹{amount} could not be charged. "
        "Update your payment method here: {link}"
    ),
    "bank_timeout": (
        "Hi {name}, your bank's server took too long to respond for ₹{amount}. "
        "We're retrying automatically — no action needed right now."
    ),
    "otp_failure": (
        "Hi {name}, the OTP entered didn't match for your ₹{amount} payment. "
        "Please try again: {link}"
    ),
    "issuer_decline": (
        "Hi {name}, your bank declined the ₹{amount} charge. Aap doosra payment "
        "method try kar sakte hain: {link}"
    ),
    "limit_exceeded": (
        "Hi {name}, aapki daily transaction limit cross ho gayi thi for ₹{amount}. "
        "Kal retry karenge, ya aap abhi kar sakte hain: {link}"
    ),
    "network_drop": (
        "Hi {name}, a network issue interrupted your ₹{amount} payment. "
        "We're retrying automatically."
    ),
    "mandate_expired": (
        "Hi {name}, your auto-pay mandate has expired, so ₹{amount} could not be collected. "
        "Re-authorize here to avoid service interruption: {link}"
    ),
    "abandon_at_otp": (
        "Hi {name}, your OTP session timed out. Your cart (₹{amount}) is still saved: {link}"
    ),
    "abandon_at_payment": (
        "Hi {name}, looks like you didn't finish checking out. Your ₹{amount} cart is "
        "waiting for you: {link}"
    ),
    "abandon_at_review": (
        "Hi {name}, your items (₹{amount}) are still in your cart at the same price: {link}"
    ),
    "abandon_at_address": (
        "Hi {name}, aap almost done the! Bas address confirm karke apna ₹{amount} "
        "order complete karein: {link}"
    ),
    "unclassified": (
        "Hi {name}, we noticed an issue with your ₹{amount} transaction and a specialist "
        "will follow up shortly."
    ),
}

DUMMY_LINK = "https://pay.example.com/resume/{event_id}"


def _template_message(root_cause: str, name: str, amount: float, event_id: str) -> str:
    template = TEMPLATES.get(root_cause, TEMPLATES["unclassified"])
    return template.format(
        name=name.split()[0],
        amount=f"{amount:,.0f}",
        link=DUMMY_LINK.format(event_id=event_id),
    )


def _ai_message(root_cause: str, name: str, amount: float, event_id: str) -> str:
    """Only called if ANTHROPIC_API_KEY is present. Falls back to the
    template silently on any error so a flaky network never breaks the
    recovery loop -- resilience matters more than a fancier sentence."""
    try:
        import anthropic
        client = anthropic.Anthropic()
        base = _template_message(root_cause, name, amount, event_id)
        resp = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=120,
            messages=[{
                "role": "user",
                "content": (
                    "Rewrite this payment-recovery nudge to sound warmer and more "
                    "natural in casual Hinglish, keep it under 30 words, keep the "
                    f"link placeholder exactly as-is: {base}"
                ),
            }],
        )
        return resp.content[0].text.strip()
    except Exception:
        return _template_message(root_cause, name, amount, event_id)


def generate_message(root_cause: str, name: str, amount: float, event_id: str) -> str:
    if os.environ.get("ANTHROPIC_API_KEY"):
        return _ai_message(root_cause, name, amount, event_id)
    return _template_message(root_cause, name, amount, event_id)
