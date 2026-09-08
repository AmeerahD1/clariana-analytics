"""
Flags unusual values in numeric columns using the IQR method (same
statistical foundation as data_cleaner.py's outlier detector), then
attaches an identifying record, a risk level, and a plain-language reason
to each flagged row — turning a cleaning-stage signal into a proper
anomaly detection feature.

Cached via st.cache_data — pure functions of the DataFrame.
"""
import pandas as pd
import streamlit as st

from modules.dashboard import find_column


def _get_id_column(df: pd.DataFrame) -> str | None:
    """Reuses the same order_id alias detection from dashboard.py so the
    'Record' column in results is a meaningful identifier, not a raw index."""
    return find_column(df, "order_id")


def _classify_risk(value: float, lower_bound: float, upper_bound: float, iqr: float) -> str:
    """
    Risk scales with how many IQRs beyond the bound the value sits —
    a value just past the fence is a mild anomaly; one many IQRs out
    is a high-risk one worth investigating first.
    """
    if iqr == 0:
        return "Medium"

    if value > upper_bound:
        distance = (value - upper_bound) / iqr
    else:
        distance = (lower_bound - value) / iqr

    if distance >= 3:
        return "High"
    elif distance >= 1:
        return "Medium"
    return "Low"


@st.cache_data(show_spinner=False)
def detect_anomalies(df: pd.DataFrame, column: str) -> pd.DataFrame:
    """
    Returns a DataFrame with one row per anomalous record in `column`:
    Record, Value, Expected Range, Risk Level, Reason.
    Empty DataFrame if the column isn't numeric or has no anomalies.
    """
    if column not in df.columns or not pd.api.types.is_numeric_dtype(df[column]):
        return pd.DataFrame(columns=["Record", "Value", "Expected Range", "Risk Level", "Reason"])

    q1 = df[column].quantile(0.25)
    q3 = df[column].quantile(0.75)
    iqr = q3 - q1
    lower_bound = q1 - 1.5 * iqr
    upper_bound = q3 + 1.5 * iqr

    mask = (df[column] < lower_bound) | (df[column] > upper_bound)
    flagged = df[mask].copy()

    if flagged.empty:
        return pd.DataFrame(columns=["Record", "Value", "Expected Range", "Risk Level", "Reason"])

    id_col = _get_id_column(df)
    expected_range_text = f"{lower_bound:,.2f} to {upper_bound:,.2f}"

    rows = []
    for idx, row in flagged.iterrows():
        value = row[column]
        record_label = str(row[id_col]) if id_col else f"Row {idx}"
        risk = _classify_risk(value, lower_bound, upper_bound, iqr)

        if value > upper_bound:
            reason = f"{column} is significantly higher than the typical range for this dataset."
        else:
            reason = f"{column} is significantly lower than the typical range for this dataset."

        rows.append({
            "Record": record_label,
            "Value": round(float(value), 2),
            "Expected Range": expected_range_text,
            "Risk Level": risk,
            "Reason": reason,
        })

    result = pd.DataFrame(rows)
    risk_order = {"High": 0, "Medium": 1, "Low": 2}
    result["_sort"] = result["Risk Level"].map(risk_order)
    result = result.sort_values("_sort").drop(columns="_sort").reset_index(drop=True)
    return result


@st.cache_data(show_spinner=False)
def get_anomaly_summary(df: pd.DataFrame, columns: list[str]) -> dict:
    """Returns {column: anomaly_count} across multiple columns, for a quick overview."""
    summary = {}
    for col in columns:
        anomalies = detect_anomalies(df, col)
        if not anomalies.empty:
            summary[col] = len(anomalies)
    return summary