"""
Automatic chart selection and rendering. Decides chart type from the
plan's operation + the actual result shape — no LLM call needed here,
since the plan already encodes enough structure to choose correctly.

render_chart is wrapped so a chart-generation failure never crashes the
page — the table/number result already rendered successfully before this
runs, so a chart error is logged and simply omitted, not fatal.
"""
import pandas as pd
import plotly.express as px

from utils.logger import log_error


def choose_chart_type(plan: dict, result) -> str | None:
    """
    Returns one of: "bar", "line", "pie", "scatter", "histogram", "box",
    "heatmap", "area", or None if no chart is appropriate for this result.
    """
    operation = plan.get("operation")

    if not isinstance(result, pd.DataFrame):
        return None

    if result.empty or len(result) < 1:
        return None

    if operation == "group_by" or operation == "filtered_group_by":
        group_col = result.columns[0]
        if pd.api.types.is_datetime64_any_dtype(result[group_col]):
            return "line"
        if len(result) <= 6 and "top_n" not in plan:
            return "pie"
        return "bar"

    if operation == "correlation":
        return None

    if operation == "describe":
        return "box"

    if operation == "multi_metric_group_by":
        return "bar"

    return None


def render_chart(plan: dict, result, chart_type: str):
    """
    Builds a Plotly figure for the given chart_type. Returns a Figure or
    None. Any failure here is caught and logged rather than raised — a
    broken chart should never take down the rest of the page.
    """
    if chart_type is None or not isinstance(result, pd.DataFrame) or result.empty:
        return None

    try:
        operation = plan.get("operation")

        if chart_type == "bar" and operation in ("group_by", "filtered_group_by"):
            group_col, metric_col = result.columns[0], result.columns[1]
            return px.bar(result, x=group_col, y=metric_col, title=f"{metric_col} by {group_col}")

        if chart_type == "pie" and operation in ("group_by", "filtered_group_by"):
            group_col, metric_col = result.columns[0], result.columns[1]
            return px.pie(result, names=group_col, values=metric_col, title=f"{metric_col} share by {group_col}")

        if chart_type == "line" and operation in ("group_by", "filtered_group_by"):
            group_col, metric_col = result.columns[0], result.columns[1]
            return px.line(result, x=group_col, y=metric_col, markers=True, title=f"{metric_col} over {group_col}")

        if chart_type == "box" and operation == "describe":
            stat_col, value_col = result.columns[0], result.columns[1]
            return px.bar(result, x=stat_col, y=value_col, title=f"Distribution summary: {value_col}")

        if chart_type == "bar" and operation == "multi_metric_group_by":
            group_col = result.columns[0]
            metric_cols = result.columns[1:].tolist()
            return px.bar(
                result, x=group_col, y=metric_cols, barmode="group",
                title=f"{', '.join(metric_cols)} by {group_col}",
            )

        return None
    except Exception as e:
        log_error("render_chart", e)
        return None