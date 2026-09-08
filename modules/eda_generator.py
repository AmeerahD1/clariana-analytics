"""
Automated end-to-end EDA: runs profiling, correlation, and outlier
detection across the whole dataset, then asks the LLM for one
executive-summary pass over the computed facts (never raw data).

The fact-gathering functions (correlations, outliers, build_eda_facts)
are cached via st.cache_data — they're pure functions of the DataFrame,
so an unrelated Streamlit rerun shouldn't redo this work. The LLM call
itself (generate_eda_report) is left uncached here since it's already
gated behind an explicit button click in app.py — call_llm_raw is
cached at the ai_analyzer.py level regardless, so repeat identical
reports still get memoization.
"""
import json
import pandas as pd
import streamlit as st

from modules.data_profiler import get_overview, get_data_quality, get_numerical_stats
from modules.data_cleaner import detect_outliers_iqr
from prompts.insight_prompt import EDA_SYSTEM_PROMPT

REQUIRED_KEYS = {
    "key_findings", "data_quality_notes", "notable_correlations",
    "business_insights", "recommendations",
}


@st.cache_data(show_spinner=False)
def compute_correlations(df: pd.DataFrame, threshold: float = 0.5) -> list[dict]:
    """Returns notable numeric correlations above the given absolute threshold."""
    numeric_df = df.select_dtypes(include="number")
    if numeric_df.shape[1] < 2:
        return []

    corr_matrix = numeric_df.corr()
    pairs = []
    seen = set()
    for col_a in corr_matrix.columns:
        for col_b in corr_matrix.columns:
            if col_a == col_b or (col_b, col_a) in seen:
                continue
            seen.add((col_a, col_b))
            value = corr_matrix.loc[col_a, col_b]
            if pd.notna(value) and abs(value) >= threshold:
                pairs.append({"column_a": col_a, "column_b": col_b, "correlation": round(float(value), 3)})

    pairs.sort(key=lambda p: abs(p["correlation"]), reverse=True)
    return pairs[:10]


@st.cache_data(show_spinner=False)
def compute_outlier_summary(df: pd.DataFrame) -> list[dict]:
    """Runs IQR-based outlier detection (from data_cleaner.py) across all numeric columns."""
    numeric_cols = df.select_dtypes(include="number").columns.tolist()
    summary = []
    for col in numeric_cols:
        outliers = detect_outliers_iqr(df, col)
        if not outliers.empty:
            summary.append({"column": col, "outlier_count": len(outliers)})
    return summary


@st.cache_data(show_spinner=False)
def build_eda_facts(df: pd.DataFrame) -> dict:
    """Assembles every computed fact the EDA report is based on, all reused
    from existing modules — no new raw-data access beyond what's already
    validated elsewhere in the app."""
    overview = get_overview(df)
    quality = get_data_quality(df)
    numerical_stats = get_numerical_stats(df)
    correlations = compute_correlations(df)
    outliers = compute_outlier_summary(df)

    return {
        "overview": overview,
        "data_quality": quality,
        "numerical_stats": numerical_stats.to_dict(orient="records") if not numerical_stats.empty else [],
        "correlations": correlations,
        "outliers": outliers,
    }


def validate_eda_summary(summary: dict) -> str | None:
    if not isinstance(summary, dict):
        return "EDA summary is not a JSON object."
    missing = REQUIRED_KEYS - summary.keys()
    if missing:
        return f"EDA summary is missing required fields: {', '.join(missing)}"
    for key in ("key_findings", "business_insights", "recommendations"):
        if not isinstance(summary[key], list) or not summary[key]:
            return f"Field '{key}' must be a non-empty list."
    for key in ("data_quality_notes", "notable_correlations"):
        if not isinstance(summary[key], str) or not summary[key].strip():
            return f"Field '{key}' must be a non-empty string."
    return None


def generate_eda_report(client_call, df: pd.DataFrame) -> dict:
    """
    client_call: same (system_prompt, user_message) -> str function used
    by insight_generator.py — reuses whichever LLM client ai_analyzer.py
    already has configured.

    Returns {"facts": {...}, "summary": {...}} or raises ValueError.
    """
    facts = build_eda_facts(df)
    user_message = f"Computed facts about the dataset:\n{json.dumps(facts, default=str)}"

    raw_text = client_call(EDA_SYSTEM_PROMPT, user_message).strip()
    raw_text = raw_text.removeprefix("```json").removeprefix("```").removesuffix("```").strip()

    try:
        summary = json.loads(raw_text)
    except json.JSONDecodeError:
        raise ValueError(f"AI did not return valid JSON for the EDA report. Raw response: {raw_text}")

    error = validate_eda_summary(summary)
    if error:
        raise ValueError(error)

    return {"facts": facts, "summary": summary}


def render_report_markdown(report: dict) -> str:
    """Builds a downloadable Markdown version of the full EDA report."""
    facts = report["facts"]
    summary = report["summary"]
    overview = facts["overview"]
    quality = facts["data_quality"]

    lines = ["# Automated EDA Report", ""]
    lines.append("## Dataset Overview")
    lines.append(f"- Rows: {overview['rows']}")
    lines.append(f"- Columns: {overview['columns']}")
    lines.append(f"- Numeric columns: {len(overview['numeric_columns'])}")
    lines.append(f"- Categorical columns: {len(overview['categorical_columns'])}")
    lines.append("")

    lines.append("## Data Quality")
    lines.append(f"- Missing cells: {quality['missing_total']} ({quality['missing_pct_of_all_cells']}%)")
    lines.append(f"- Duplicate rows: {quality['duplicate_rows']}")
    lines.append(f"- Notes: {summary['data_quality_notes']}")
    lines.append("")

    lines.append("## Notable Correlations")
    lines.append(summary["notable_correlations"])
    lines.append("")

    lines.append("## Key Findings")
    for item in summary["key_findings"]:
        lines.append(f"- {item}")
    lines.append("")

    lines.append("## Business Insights")
    for item in summary["business_insights"]:
        lines.append(f"- {item}")
    lines.append("")

    lines.append("## Recommendations")
    for item in summary["recommendations"]:
        lines.append(f"- {item}")
    lines.append("")

    if facts["outliers"]:
        lines.append("## Detected Outliers (IQR method)")
        for o in facts["outliers"]:
            lines.append(f"- {o['column']}: {o['outlier_count']} outlier rows")

    return "\n".join(lines)