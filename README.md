# Recovery Copilot



An agent that detects revenue slipping away from a merchant — failed
payments and abandoned checkouts — diagnoses *why* each one happened, and
runs a bounded, auditable recovery workflow to win the money back.

---

## 1. The idea in one paragraph

Revenue leaks rarely happen in one clean step. A card expires, a bank
server times out, a customer gets distracted mid-checkout, an auto-pay
mandate lapses. Each of these needs a **different** recovery action — you
don't retry an expired card the same way you retry a network blip. Recovery
Copilot reads a batch of these events, runs them through a transparent
rule-based diagnosis (not a black-box model — auditable by design for a
money-moving system), and executes a capped retry/nudge sequence per event,
logging every single action it takes. It also speaks **Hinglish**, because
that's how a large share of  actual customer base reads a payment
reminder most naturally — the buildathon brief calls this out explicitly as
a differentiator.

## 2. Why the design choices are deliberate, not just "simple"

| Choice | Reasoning |
|---|---|
| Rule-based diagnosis instead of an ML classifier | Failure codes from a payment gateway are already structured data — a decision table is 100% auditable and just as accurate as a model would be here. For a workflow that touches customer money, "we can show exactly why the agent did X" beats a marginal accuracy gain from a black box. |
| Hard-capped retries per root cause (`max_attempts` in `diagnose.py`) | This *is* the "bounded" and "stopping rules" requirement from the brief, enforced in code, not described in prose. |
| Flat CSV audit trail | Any reviewer can open it in Excel. No database, no hidden state. |
| Template messaging by default, LLM personalization optional | The pipeline runs and produces real, measurable results with zero API keys and zero cost. If `ANTHROPIC_API_KEY` is set, the messaging layer calls Claude to warm up the tone — this is where "AI" is used *meaningfully* rather than bolted on everywhere for the sake of it. |


## 3. Architecture

```
synthetic events (CSV)
        │
        ▼
   diagnose.py  ──── rule table: failure_code → root_cause, action,
        │             wait_hours, max_attempts, est_success_prob
        ▼
   recover.py   ──── bounded retry loop per event
        │             • stop on success
        │             • never exceed max_attempts
        │             • space attempts by wait_hours
        │             • escalate to manual review after final failed attempt
        │
        ├──► messaging.py  (template, or Claude API if key is set)
        │
        ▼
   audit.py     ──── every attempt logged: who, why, what action, outcome
        │
        ▼
   pipeline.py  ──── aggregates into recovery-rate metrics
        │
        ▼
   report.py    ──── self-contained HTML report + JSON summary
```

Three entry points sit on top of the same `src/` logic:
- **`main.py`** — zero-dependency-beyond-pandas CLI run, produces the audit
  trail + HTML report + JSON summary. This is the one to run for the actual
  submission artifacts.
- **`api.py`** — Flask REST API layer, so the pipeline can be called by a
  real system  instead of only from the CLI.

## 4. Project structure

```
recovery-copilot/
├── main.py                    # run this: full pipeline, zero setup
├── api.py                     # Flask REST API layer (webhook-ready)
├── app.py                     # optional: interactive Streamlit demo
├── requirements.txt
├── .env.example                # optional ANTHROPIC_API_KEY for AI messaging
├── src/
│   ├── generate_data.py       # synthetic payment-failure + abandonment events
│   ├── diagnose.py            # root-cause rule table (the "brain")
│   ├── recover.py             # bounded retry loop + stopping rules
│   ├── messaging.py           # Hinglish/English templates + optional Claude call
│   ├── audit.py                # writes the audit trail CSV
│   ├── pipeline.py            # orchestration + metrics
│   └── report.py              # HTML report + charts
├── tests/
│   ├── test_diagnose.py       # root-cause rules are valid & bounded
│   ├── test_recover.py        # stopping rules actually stop
│   └── test_pipeline.py       # metrics math is correct
├── data/
│   └── synthetic_events.csv   # generated batch (committed as a working example)
└── outputs/
    ├── audit_trail.csv        # every recovery attempt, logged
    ├── recovery_report.html   # open this in a browser
    └── summary.json           # machine-readable metrics
```

## 5. How to run it

```bash
git clone <your-repo-url>
cd recovery-copilot
pip install -r requirements.txt

python main.py
```

That's it. Open `outputs/recovery_report.html` in a browser.

For the interactive dashboard (nice for the pitch video):
```bash
streamlit run app.py
```

To turn on AI-personalized messaging (optional, not required to demo the
core loop):
```bash
cp .env.example .env
# add your ANTHROPIC_API_KEY to .env, then export it or use python-dotenv
python main.py
```

To run the REST API layer:
```bash
python api.py
# then, in another terminal:
curl http://localhost:5000/api/health
curl http://localhost:5000/api/run
curl http://localhost:5000/api/metrics
curl -X POST http://localhost:5000/api/events -H "Content-Type: application/json" \
  -d '{"event_id":"e1","event_type":"payment_failure","customer_id":"c1",
       "customer_name":"Rahul Sharma","amount":2500,"failure_code":"CARD_EXPIRED",
       "timestamp":"2026-08-31T10:00:00"}'
```

To run the test suite:
```bash
python -m unittest discover tests -v
```

## 6. What the numbers mean (and don't mean)

Running the default seed produces a batch of 200 events (140 payment
failures + 60 checkout abandonments) and reports roughly:
- **~53% of events recovered**
- **~54% of at-risk revenue recovered**

These numbers come from the `est_success_prob` assumptions in
`src/diagnose.py`, which are reasonable but invented placeholders (e.g.
"a bank-timeout retry succeeds ~55% of the time"). **This is stated on the report itself** so it's honest
with anyone reviewing it. The entire point of the architecture is that
these numbers become real the moment you plug in actual historical
recovery rates — nothing else in the pipeline needs to change.

## 7. How this maps to "the bar" for Track 03

- ✅ **Detects revenue at risk** — `generate_data.py` / real webhook data → `diagnose.py`
- ✅ **Determines the right intervention** — root-cause → action mapping is explicit and per-cause
- ✅ **Executes a bounded recovery workflow** — `recover.py`, hard-capped attempts
- ✅ **Measured money recovered across a batch** — `pipeline.py` metrics, shown in the HTML report
- ✅ **Compliant escalation** — unrecovered events explicitly escalate to manual review, not infinite retries
- ✅ **Stopping rules** — max attempts + stop-on-success, enforced in code
- ✅ **Audit trail** — `outputs/audit_trail.csv`, every attempt logged
- ✅ **API/server layer** — `api.py`, Flask endpoints so it's callable by a real webhook, not just a CLI
- ✅ **Tests** — `tests/`, checks that stopping rules actually stop, root-cause rules stay bounded, and recovery-rate math is correct

## 8. Extending this for the real thing

- **Real data**: swap `data/synthetic_events.csv` for webhook
  payloads (payment.failed events, cart/session abandonment events). The
  field names in `generate_data.py` are already modeled on real
  failure-reason vocabulary.
- **Real success rates**: replace `est_success_prob` in `diagnose.py` with
  actual historical recovery rates per failure code — this is a one-line
  change per root cause.
- **Real messaging channel**: `messaging.py` currently returns text; wire
  it to WhatsApp Business API / SMS / email instead of printing to the
  audit log.
- **B2B receivables / mandate retry sequencing**: the same `diagnose.py` →
  `recover.py` pattern extends directly — add new root-cause rows for
  overdue-invoice codes.

## 9. Honest limitations (worth saying out loud in the pitch)

- No live payment gateway integration — this is a synthetic-batch
  demonstration of the decision logic and audit trail, as the track brief
  explicitly allows ("synthetic data" is fine — see Track 04 for
  comparison, which asks for it directly).
- Success probabilities are assumptions, clearly labeled as such.
- The Hinglish templates are hand-written for a fixed set of root causes;
  a production system would want a larger, tested template library or
  reviewed AI-generated variants.

## 10. License

MIT — see `LICENSE`.
