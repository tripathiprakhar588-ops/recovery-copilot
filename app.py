"""
app.py
------
Optional interactive dashboard for the demo/pitch video. Not required to
run the core pipeline (main.py does that with zero dependencies beyond
pandas/matplotlib) but makes a much better 5-minute video than reading a
CSV on screen.

Run with:
    pip install streamlit
    streamlit run app.py
"""

import os
import random

import pandas as pd
import streamlit as st

from src.generate_data import generate_payment_failures, generate_checkout_abandonment, write_csv
from src.pipeline import run_pipeline

st.set_page_config(page_title="Recovery Copilot", layout="wide")

st.title("Recovery Copilot")
st.caption("Razorpay AI Buildathon · Track 03 — AI Revenue Recovery")

with st.sidebar:
    st.header("Batch settings")
    n_failures = st.slider("Payment failures", 20, 300, 140)
    n_abandon = st.slider("Checkout abandonments", 10, 150, 60)
    seed = st.number_input("Random seed", value=42, step=1)
    run_btn = st.button("Generate & run recovery", type="primary")

DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)
events_path = os.path.join(DATA_DIR, "synthetic_events.csv")

if run_btn or not os.path.exists(events_path):
    random.seed(seed)
    events = generate_payment_failures(n_failures) + generate_checkout_abandonment(n_abandon)
    random.shuffle(events)
    write_csv(events, events_path)

audit_rows, metrics = run_pipeline(events_path)
audit_df = pd.DataFrame(audit_rows)

col1, col2, col3, col4 = st.columns(4)
col1.metric("Events processed", metrics["total_events"])
col2.metric("Event recovery rate", f"{metrics['event_recovery_rate']*100:.0f}%")
col3.metric("Revenue at risk", f"₹{metrics['total_at_risk']:,.0f}")
col4.metric("Revenue recovered", f"₹{metrics['recovered_amount']:,.0f}",
            f"{metrics['amount_recovery_rate']*100:.0f}% recovered")

st.subheader("Recovery rate by root cause")
cause_df = pd.DataFrame([
    {"root_cause": k, "recovery_rate": v["recovered"] / v["count"] * 100 if v["count"] else 0,
     "events": v["count"]}
    for k, v in metrics["by_cause"].items()
]).sort_values("recovery_rate", ascending=False)
st.bar_chart(cause_df.set_index("root_cause")["recovery_rate"])

st.subheader("Audit trail")
outcome_filter = st.multiselect(
    "Filter by outcome", options=audit_df["outcome"].unique().tolist(),
    default=audit_df["outcome"].unique().tolist(),
)
st.dataframe(
    audit_df[audit_df["outcome"].isin(outcome_filter)],
    use_container_width=True, height=400,
)

st.caption(
    "Success probabilities are illustrative assumptions (see src/diagnose.py), "
    "not real Razorpay data. Swap in real historical rates once available."
)
