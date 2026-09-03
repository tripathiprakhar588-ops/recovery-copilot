"""
report.py
---------
Turns the metrics + audit trail into a single self-contained HTML file
(charts embedded as base64 PNGs) so it can be opened by anyone, emailed,
or dropped straight into the pitch video with zero setup.
"""

import base64
import io
import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def _fig_to_base64(fig):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=140, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("utf-8")


def _recovery_by_cause_chart(by_cause):
    causes = list(by_cause.keys())
    rates = [
        (v["recovered"] / v["count"] * 100 if v["count"] else 0) for v in by_cause.values()
    ]
    order = sorted(range(len(causes)), key=lambda i: rates[i], reverse=True)
    causes = [causes[i] for i in order]
    rates = [rates[i] for i in order]

    fig, ax = plt.subplots(figsize=(8, 4.5))
    bars = ax.barh(causes, rates, color="#3B82F6")
    ax.set_xlabel("Recovery rate (%)")
    ax.set_title("Recovery rate by root cause")
    ax.invert_yaxis()
    for bar, rate in zip(bars, rates):
        ax.text(bar.get_width() + 1, bar.get_y() + bar.get_height() / 2,
                 f"{rate:.0f}%", va="center", fontsize=9)
    fig.tight_layout()
    return _fig_to_base64(fig)


def _amount_pie_chart(recovered, unrecovered):
    fig, ax = plt.subplots(figsize=(5, 5))
    ax.pie(
        [recovered, unrecovered],
        labels=["Recovered", "Unrecovered"],
        autopct="%1.0f%%",
        colors=["#22C55E", "#EF4444"],
        startangle=90,
    )
    ax.set_title("Revenue at risk: recovered vs unrecovered")
    fig.tight_layout()
    return _fig_to_base64(fig)


def generate_html_report(metrics, audit_rows, out_path, sample_size=25):
    cause_chart_b64 = _recovery_by_cause_chart(metrics["by_cause"])
    pie_chart_b64 = _amount_pie_chart(metrics["recovered_amount"], metrics["unrecovered_amount"])

    sample_rows = audit_rows[:sample_size]
    table_rows_html = "".join(
        f"<tr><td>{r['event_id']}</td><td>{r['root_cause']}</td>"
        f"<td>{r['attempt_number']}</td><td>{r['action_taken']}</td>"
        f"<td>₹{r['amount']:,.0f}</td>"
        f"<td class='outcome-{r['outcome']}'>{r['outcome']}</td></tr>"
        for r in sample_rows
    )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Recovery Copilot — Report</title>
<style>
  body {{ font-family: -apple-system, Segoe UI, Roboto, sans-serif; margin: 0; padding: 40px;
          background: #0B1120; color: #E5E7EB; }}
  h1 {{ font-size: 1.6rem; margin-bottom: 4px; }}
  .subtitle {{ color: #94A3B8; margin-bottom: 32px; }}
  .cards {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 32px; }}
  .card {{ background: #111827; border: 1px solid #1F2937; border-radius: 10px; padding: 18px; }}
  .card .label {{ color: #94A3B8; font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.04em; }}
  .card .value {{ font-size: 1.7rem; font-weight: 700; margin-top: 6px; }}
  .charts {{ display: grid; grid-template-columns: 1.4fr 1fr; gap: 24px; margin-bottom: 32px; }}
  .chart-box {{ background: #111827; border: 1px solid #1F2937; border-radius: 10px; padding: 16px; text-align:center; }}
  img {{ max-width: 100%; }}
  table {{ width: 100%; border-collapse: collapse; background: #111827; border-radius: 10px; overflow: hidden; }}
  th, td {{ padding: 10px 12px; text-align: left; border-bottom: 1px solid #1F2937; font-size: 0.85rem; }}
  th {{ color: #94A3B8; font-weight: 600; text-transform: uppercase; font-size: 0.7rem; }}
  .outcome-recovered {{ color: #22C55E; font-weight: 600; }}
  .outcome-failed {{ color: #F59E0B; }}
  .outcome-unrecovered_escalated {{ color: #EF4444; font-weight: 600; }}
  footer {{ margin-top: 24px; color: #64748B; font-size: 0.8rem; }}
</style>
</head>
<body>
  <h1>Recovery Copilot — Revenue Recovery Report</h1>
  <div class="subtitle">Razorpay AI Buildathon · Track 03 — AI Revenue Recovery · Synthetic batch</div>

  <div class="cards">
    <div class="card"><div class="label">Events processed</div><div class="value">{metrics['total_events']}</div></div>
    <div class="card"><div class="label">Event recovery rate</div><div class="value">{metrics['event_recovery_rate']*100:.0f}%</div></div>
    <div class="card"><div class="label">Revenue at risk</div><div class="value">₹{metrics['total_at_risk']:,.0f}</div></div>
    <div class="card"><div class="label">Revenue recovered</div><div class="value">₹{metrics['recovered_amount']:,.0f}</div></div>
  </div>

  <div class="charts">
    <div class="chart-box"><img src="data:image/png;base64,{cause_chart_b64}"></div>
    <div class="chart-box"><img src="data:image/png;base64,{pie_chart_b64}"></div>
  </div>

  <h2>Audit trail (sample of {len(sample_rows)} of {len(audit_rows)} total attempts)</h2>
  <table>
    <thead><tr><th>Event</th><th>Root cause</th><th>Attempt #</th><th>Action</th><th>Amount</th><th>Outcome</th></tr></thead>
    <tbody>{table_rows_html}</tbody>
  </table>

  <footer>
    Generated by Recovery Copilot. Success probabilities are illustrative assumptions
    documented in src/diagnose.py and README.md, not real Razorpay data.
  </footer>
</body>
</html>"""

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)


def write_summary_json(metrics, out_path):
    # by_cause/by_type contain plain dicts already -> directly serializable
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)
