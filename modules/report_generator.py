"""
Shared export helpers: DataFrame -> CSV/Excel bytes, and a full-session
HTML report assembled from whatever's already been computed and cached
in session_state across earlier phases (EDA, forecast, anomalies,
segments, recommendations) — no new analysis runs here, only formatting.
"""
import io
from datetime import datetime

import pandas as pd

from config.branding import (
    APP_NAME,
    BRAND_DARK_COLOR,
    BRAND_PANEL_COLOR,
    BRAND_PRIMARY_COLOR,
    BRAND_POWERED_BY_NAME,
    BRAND_POWERED_BY_URL,
    BRAND_SHOW_POWERED_BY,
)


def to_csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8")


def to_excel_bytes(df: pd.DataFrame, sheet_name: str = "Sheet1") -> bytes:
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name)
    return buffer.getvalue()


def _html_table(df: pd.DataFrame) -> str:
    if df is None or df.empty:
        return "<p><em>No data.</em></p>"
    return df.to_html(index=False, classes="report-table", border=0)


def build_full_html_report(session_state) -> str:
    """
    Assembles every already-computed result currently cached in
    session_state into one self-contained HTML document. Sections that
    haven't been generated yet are simply omitted, not shown as errors —
    this is a snapshot of whatever the user has actually run so far.
    """
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M")
    sections = []

    filename = session_state.get("uploaded_filename", "dataset")
    sections.append(f"<p>Dataset: <strong>{filename}</strong></p>")

    eda_report = session_state.get("eda_report")
    if eda_report:
        summary = eda_report["summary"]
        facts = eda_report["facts"]
        sections.append("<h2>Automated EDA Summary</h2>")
        sections.append(f"<p><strong>Data Quality:</strong> {summary['data_quality_notes']}</p>")
        sections.append(f"<p><strong>Notable Correlations:</strong> {summary['notable_correlations']}</p>")
        sections.append("<h3>Key Findings</h3><ul>" + "".join(f"<li>{f}</li>" for f in summary["key_findings"]) + "</ul>")
        sections.append("<h3>Business Insights</h3><ul>" + "".join(f"<li>{f}</li>" for f in summary["business_insights"]) + "</ul>")
        sections.append("<h3>Recommendations</h3><ul>" + "".join(f"<li>{f}</li>" for f in summary["recommendations"]) + "</ul>")
        if facts.get("outliers"):
            outlier_df = pd.DataFrame(facts["outliers"])
            sections.append("<h3>Detected Outliers</h3>" + _html_table(outlier_df))

    forecast_result = session_state.get("forecast_result")
    if forecast_result:
        sections.append("<h2>Forecast</h2>")
        sections.append(f"<p>Metric: <strong>{forecast_result['metric_col']}</strong>, "
                         f"Horizon: {forecast_result['periods']} periods</p>")
        if forecast_result["expected_growth_pct"] is not None:
            direction = "growth" if forecast_result["expected_growth_pct"] >= 0 else "decline"
            sections.append(f"<p>Expected {direction}: {abs(forecast_result['expected_growth_pct']):.1f}%</p>")
        sections.append("<h3>Forecast Values</h3>" + _html_table(forecast_result["forecast"]))
        sections.append("<p><em>This forecast is a linear trend projection and is not a guaranteed outcome.</em></p>")

    recommendations = session_state.get("recommendations")
    if recommendations:
        sections.append("<h2>AI Recommendations</h2>")
        for rec in recommendations:
            sections.append(
                f"<div class='rec-card'><strong>Priority: {rec['priority']}</strong><br>"
                f"<strong>Finding:</strong> {rec['finding']}<br>"
                f"<strong>Recommendation:</strong> {rec['recommendation']}<br>"
                f"<em>Objective: {rec['expected_business_objective']}</em></div>"
            )

    segmentation_result = session_state.get("segmentation_result")
    if segmentation_result and segmentation_result.get("method") == "rfm":
        from modules.segmentation import get_segment_summary
        summary_df = get_segment_summary(segmentation_result["data"])
        sections.append("<h2>Customer Segmentation (RFM)</h2>" + _html_table(summary_df))

    conversation_history = session_state.get("conversation_history")
    if conversation_history:
        sections.append("<h2>AI Analyst Q&A Log</h2><ul>" + "".join(f"<li>{turn}</li>" for turn in conversation_history) + "</ul>")

    body = "\n".join(sections)

    footer_html = ""
    if BRAND_SHOW_POWERED_BY:
        footer_html = (
            f'<div class="report-footer">Powered by '
            f'<a href="{BRAND_POWERED_BY_URL}">{BRAND_POWERED_BY_NAME}</a></div>'
        )

    html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>{APP_NAME} Report</title>
<style>
  body {{
    font-family: -apple-system, "Segoe UI", Inter, Arial, sans-serif;
    max-width: 900px; margin: 0 auto 40px auto; color: #1a2b30; line-height: 1.55;
    background: #f6fafb;
  }}
  .report-header {{
    background: linear-gradient(120deg, {BRAND_DARK_COLOR} 0%, {BRAND_PANEL_COLOR} 100%);
    color: #ffffff;
    padding: 28px 32px;
    margin-bottom: 28px;
  }}
  .report-header h1 {{ margin: 0; font-size: 1.5rem; }}
  .report-header p {{ margin: 6px 0 0 0; color: rgba(255,255,255,0.82); font-size: 0.9rem; }}
  .report-body {{ padding: 0 32px; }}
  h2 {{ margin-top: 32px; color: {BRAND_DARK_COLOR}; border-bottom: 2px solid {BRAND_PRIMARY_COLOR}; padding-bottom: 6px; }}
  h3 {{ color: {BRAND_PANEL_COLOR}; }}
  .report-table {{ border-collapse: collapse; width: 100%; margin: 12px 0; }}
  .report-table th, .report-table td {{ border: 1px solid #dbe7ea; padding: 6px 10px; text-align: left; }}
  .report-table th {{ background: {BRAND_DARK_COLOR}; color: #ffffff; }}
  .rec-card {{ border: 1px solid #dbe7ea; border-left: 4px solid {BRAND_PRIMARY_COLOR}; border-radius: 6px; padding: 12px; margin: 10px 0; background: #ffffff; }}
  .report-footer {{
    margin-top: 40px; padding: 16px 32px; border-top: 1px solid #dbe7ea;
    font-size: 0.8rem; color: #5a7278;
  }}
  .report-footer a {{ color: {BRAND_PRIMARY_COLOR}; font-weight: 600; text-decoration: none; }}
</style>
</head>
<body>
<div class="report-header">
  <h1>{APP_NAME} — Report</h1>
  <p>Generated {generated_at}</p>
</div>
<div class="report-body">
{body}
</div>
{footer_html}
</body>
</html>"""

    return html