"""
api.py
------
Thin Flask API layer over the same src/ pipeline that main.py and app.py
use. This is what turns Recovery Copilot from "a script you run locally"
into something a real system (e.g. a Razorpay webhook, or your own
merchant dashboard) could actually call.

Endpoints
---------
GET  /api/health          -> liveness check
POST /api/events          -> ingest one or more raw events, run them
                              through diagnose + bounded recovery
                              immediately, return the audit rows + outcome
GET  /api/run             -> regenerate a fresh synthetic batch and run
                              the full pipeline (same as `python main.py`
                              but over HTTP)
GET  /api/metrics         -> latest computed metrics as JSON
GET  /api/audit-trail     -> latest audit trail as JSON
GET  /api/report          -> serves the generated HTML report

Run with:
    python api.py
    # then e.g. curl http://localhost:5000/api/health
"""

import os
import random

from flask import Flask, jsonify, request, send_file

from src.generate_data import generate_payment_failures, generate_checkout_abandonment, write_csv
from src.diagnose import diagnose
from src.recover import recover_event
from src.pipeline import run_pipeline, compute_metrics
from src.audit import write_audit_trail
from src.report import generate_html_report, write_summary_json

app = Flask(__name__)

BASE_DIR = os.path.dirname(__file__)
DATA_DIR = os.path.join(BASE_DIR, "data")
OUT_DIR = os.path.join(BASE_DIR, "outputs")
EVENTS_PATH = os.path.join(DATA_DIR, "synthetic_events.csv")
AUDIT_PATH = os.path.join(OUT_DIR, "audit_trail.csv")
REPORT_PATH = os.path.join(OUT_DIR, "recovery_report.html")
SUMMARY_PATH = os.path.join(OUT_DIR, "summary.json")

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(OUT_DIR, exist_ok=True)

REQUIRED_EVENT_FIELDS = {
    "event_id", "event_type", "customer_id", "customer_name",
    "amount", "failure_code", "timestamp",
}


@app.get("/api/health")
def health():
    return jsonify({"status": "ok", "service": "recovery-copilot"})


@app.post("/api/events")
def ingest_events():
    """Accepts either a single event object or a list of event objects.
    Runs each one through diagnose + the bounded recovery loop immediately
    and returns the resulting audit rows -- this is the endpoint a real
    webhook (e.g. Razorpay payment.failed) would call."""
    payload = request.get_json(force=True, silent=True)
    if payload is None:
        return jsonify({"error": "Request body must be JSON"}), 400

    events = payload if isinstance(payload, list) else [payload]

    missing = []
    for i, e in enumerate(events):
        gaps = REQUIRED_EVENT_FIELDS - set(e.keys())
        if gaps:
            missing.append({"index": i, "missing_fields": sorted(gaps)})
    if missing:
        return jsonify({"error": "Missing required fields", "details": missing}), 400

    all_audit_rows = []
    for e in events:
        e = dict(e)
        e.setdefault("payment_method", "")
        e.setdefault("is_subscription", False)
        e.setdefault("customer_segment", "unknown")
        e["amount"] = float(e["amount"])
        diagnosed = diagnose(e)
        all_audit_rows.extend(recover_event(diagnosed))

    return jsonify({"events_processed": len(events), "audit_rows": all_audit_rows}), 200


@app.get("/api/run")
def run_full_batch():
    """Regenerates a synthetic batch and runs the complete pipeline --
    the HTTP equivalent of `python main.py`."""
    n_failures = int(request.args.get("failures", 140))
    n_abandon = int(request.args.get("abandonments", 60))
    seed = int(request.args.get("seed", 42))

    random.seed(seed)
    events = generate_payment_failures(n_failures) + generate_checkout_abandonment(n_abandon)
    random.shuffle(events)
    write_csv(events, EVENTS_PATH)

    audit_rows, metrics = run_pipeline(EVENTS_PATH)
    write_audit_trail(audit_rows, AUDIT_PATH)
    generate_html_report(metrics, audit_rows, REPORT_PATH)
    write_summary_json(metrics, SUMMARY_PATH)

    return jsonify({
        "message": "Pipeline run complete",
        "events_processed": metrics["total_events"],
        "metrics": metrics,
        "report_url": "/api/report",
    })


@app.get("/api/metrics")
def get_metrics():
    if not os.path.exists(SUMMARY_PATH):
        return jsonify({"error": "No run yet. Call /api/run first."}), 404
    import json
    with open(SUMMARY_PATH) as f:
        return jsonify(json.load(f))


@app.get("/api/audit-trail")
def get_audit_trail():
    if not os.path.exists(AUDIT_PATH):
        return jsonify({"error": "No run yet. Call /api/run first."}), 404
    import csv
    with open(AUDIT_PATH, newline="") as f:
        rows = list(csv.DictReader(f))
    return jsonify({"count": len(rows), "rows": rows})


@app.get("/api/report")
def get_report():
    if not os.path.exists(REPORT_PATH):
        return jsonify({"error": "No run yet. Call /api/run first."}), 404
    return send_file(REPORT_PATH)


if __name__ == "__main__":
    app.run(debug=True, port=5000)
