"""
Executes a validated analysis plan against a DataFrame using Pandas, and
a validated SQL query against an in-memory SQLite view of the same data.

This is the safety boundary for the whole app: the LLM only ever chooses
from a fixed, named set of operations/aggregations, or writes a SELECT-only
SQL string. Every column name and operation is checked against the real
dataframe before anything runs. Never call eval()/exec() on LLM output.
"""
import re
import sqlite3

import pandas as pd
import streamlit as st

ALLOWED_AGGS = {"sum", "mean", "count", "min", "max"}
ALLOWED_OPERATIONS = {
    "single_value",
    "group_by",
    "filtered_group_by",
    "correlation",
    "describe",
    "multi_metric_group_by",
}

FILTER_OPS = {
    "==": lambda s, v: s == v,
    "!=": lambda s, v: s != v,
    ">": lambda s, v: s > v,
    "<": lambda s, v: s < v,
    ">=": lambda s, v: s >= v,
    "<=": lambda s, v: s <= v,
}

# --------------------------------------------------------------------
# Pandas plan validation (single_value / group_by)
# --------------------------------------------------------------------


def validate_plan(df: pd.DataFrame, plan: dict) -> str | None:
    """Returns an error message if the plan is invalid, else None.
    Only applies to the 'single_value' and 'group_by' operations —
    the other operation types validate inline in their own executor."""
    if plan.get("operation") not in ALLOWED_OPERATIONS:
        return f"Unsupported operation: {plan.get('operation')}"

    if plan.get("agg") not in ALLOWED_AGGS:
        return f"Unsupported aggregation: {plan.get('agg')}"

    metric = plan.get("metric")
    if metric not in df.columns:
        return f"Column '{metric}' does not exist in the dataset."
    if plan["agg"] != "count" and not pd.api.types.is_numeric_dtype(df[metric]):
        return f"Column '{metric}' is not numeric, cannot apply '{plan['agg']}'."

    group_by = plan.get("group_by")
    if plan["operation"] == "group_by":
        if group_by not in df.columns:
            return f"Group-by column '{group_by}' does not exist in the dataset."

    return None


# --------------------------------------------------------------------
# Phase 8 — advanced Pandas operations
# --------------------------------------------------------------------


def _coerce_filter_value(series: pd.Series, raw_value):
    """Casts the filter value to match the column's dtype so comparisons work."""
    if pd.api.types.is_numeric_dtype(series):
        try:
            return float(raw_value)
        except (TypeError, ValueError):
            raise ValueError(f"Filter value '{raw_value}' is not numeric, but the column is.")
    return str(raw_value)


def execute_filtered_group_by(df: pd.DataFrame, plan: dict):
    filter_col = plan.get("filter_column")
    filter_op = plan.get("filter_op")
    filter_value = plan.get("filter_value")
    metric = plan.get("metric")
    agg = plan.get("agg")
    group_by = plan.get("group_by")

    if filter_col not in df.columns:
        raise ValueError(f"Filter column '{filter_col}' does not exist.")
    if filter_op not in FILTER_OPS:
        raise ValueError(f"Unsupported filter operator: {filter_op}")
    if metric not in df.columns:
        raise ValueError(f"Column '{metric}' does not exist.")
    if agg not in ALLOWED_AGGS:
        raise ValueError(f"Unsupported aggregation: {agg}")

    coerced_value = _coerce_filter_value(df[filter_col], filter_value)
    mask = FILTER_OPS[filter_op](df[filter_col], coerced_value)
    filtered = df[mask]

    if filtered.empty:
        return pd.DataFrame(columns=[metric])

    if group_by:
        if group_by not in df.columns:
            raise ValueError(f"Group-by column '{group_by}' does not exist.")
        result = filtered.groupby(group_by)[metric].agg(agg).reset_index()
        result.columns = [group_by, metric]
        ascending = plan.get("sort", "desc") == "asc"
        result = result.sort_values(metric, ascending=ascending)
        top_n = plan.get("top_n")
        if top_n:
            result = result.head(top_n)
        return result.reset_index(drop=True)
    else:
        return getattr(filtered[metric], agg)()


def execute_correlation(df: pd.DataFrame, plan: dict) -> float:
    metric_a = plan.get("metric_a")
    metric_b = plan.get("metric_b")

    for col in (metric_a, metric_b):
        if col not in df.columns:
            raise ValueError(f"Column '{col}' does not exist.")
        if not pd.api.types.is_numeric_dtype(df[col]):
            raise ValueError(f"Column '{col}' is not numeric, cannot compute correlation.")

    return df[metric_a].corr(df[metric_b])


def execute_describe(df: pd.DataFrame, plan: dict) -> pd.DataFrame:
    metric = plan.get("metric")
    if metric not in df.columns:
        raise ValueError(f"Column '{metric}' does not exist.")
    if not pd.api.types.is_numeric_dtype(df[metric]):
        raise ValueError(f"Column '{metric}' is not numeric.")

    stats = df[metric].describe()
    result = stats.reset_index()
    result.columns = ["Statistic", metric]
    return result


def execute_multi_metric_group_by(df: pd.DataFrame, plan: dict) -> pd.DataFrame:
    metrics = plan.get("metrics", [])
    agg = plan.get("agg")
    group_by = plan.get("group_by")

    if not metrics:
        raise ValueError("No metrics specified.")
    for m in metrics:
        if m not in df.columns:
            raise ValueError(f"Column '{m}' does not exist.")
        if not pd.api.types.is_numeric_dtype(df[m]):
            raise ValueError(f"Column '{m}' is not numeric.")
    if agg not in {"sum", "mean"}:
        raise ValueError(f"Unsupported aggregation for multi-metric: {agg}")
    if group_by not in df.columns:
        raise ValueError(f"Group-by column '{group_by}' does not exist.")

    result = df.groupby(group_by)[metrics].agg(agg).reset_index()
    top_n = plan.get("top_n")
    if top_n:
        result = result.head(top_n)
    return result


# --------------------------------------------------------------------
# Dispatcher — routes a plan to the right executor by "operation"
# --------------------------------------------------------------------


def execute_plan(df: pd.DataFrame, plan: dict):
    """
    Executes a validated plan. Dispatches to the right executor based on
    plan["operation"]. Raises ValueError on any invalid/unsupported plan.
    """
    operation = plan.get("operation")

    if operation == "single_value":
        error = validate_plan(df, plan)
        if error:
            raise ValueError(error)
        return getattr(df[plan["metric"]], plan["agg"])()

    elif operation == "group_by":
        error = validate_plan(df, plan)
        if error:
            raise ValueError(error)
        metric, agg, group_by = plan["metric"], plan["agg"], plan["group_by"]
        grouped = df.groupby(group_by)[metric].agg(agg).reset_index()
        grouped.columns = [group_by, metric]
        ascending = plan.get("sort", "desc") == "asc"
        grouped = grouped.sort_values(metric, ascending=ascending)
        top_n = plan.get("top_n")
        if top_n:
            grouped = grouped.head(top_n)
        return grouped.reset_index(drop=True)

    elif operation == "filtered_group_by":
        return execute_filtered_group_by(df, plan)

    elif operation == "correlation":
        return execute_correlation(df, plan)

    elif operation == "describe":
        return execute_describe(df, plan)

    elif operation == "multi_metric_group_by":
        return execute_multi_metric_group_by(df, plan)

    else:
        raise ValueError(f"Unsupported operation: {operation}")


# --------------------------------------------------------------------
# Phase 7 — SQL execution (read-only, validated, in-memory SQLite)
# --------------------------------------------------------------------

DESTRUCTIVE_KEYWORDS = {
    "DROP", "DELETE", "UPDATE", "INSERT", "ALTER",
    "TRUNCATE", "CREATE", "REPLACE", "ATTACH", "PRAGMA",
}

TABLE_NAME = "dataset"


@st.cache_resource(show_spinner=False)
def build_sqlite_connection(df: pd.DataFrame) -> sqlite3.Connection:
    """
    Loads the DataFrame into an in-memory SQLite database as a single
    table. Cached via st.cache_resource, keyed on the DataFrame's content —
    if the filtered/cleaned data changes at all, the hash changes and a
    fresh connection/table is built automatically. Multiple SQL questions
    against unchanged data reuse one connection instead of reloading the
    table on every single query.
    """
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    df.to_sql(TABLE_NAME, conn, index=False, if_exists="replace")
    return conn


def get_sql_schema_description(df: pd.DataFrame) -> str:
    """Compact schema text for the SQL-generation prompt, including the table name."""
    lines = [f"Table name: {TABLE_NAME}", "Columns:"]
    for col, dtype in df.dtypes.items():
        lines.append(f"- {col} ({dtype})")
    return "\n".join(lines)


def _strip_sql_comments(sql: str) -> str:
    """Removes -- line comments and /* */ block comments before keyword
    checking, so a blocked keyword can't be hidden behind a comment marker."""
    no_line_comments = re.sub(r"--.*?(\n|$)", " ", sql)
    no_block_comments = re.sub(r"/\*.*?\*/", " ", no_line_comments, flags=re.DOTALL)
    return no_block_comments


def validate_sql(sql: str) -> str | None:
    """
    Returns an error message if the SQL is unsafe or malformed, else None.
    Only single SELECT statements are permitted. Comments are stripped
    before validation so a blocked keyword can't be hidden inside one.
    """
    if not sql or not sql.strip():
        return "Empty SQL query."

    cleaned = _strip_sql_comments(sql).strip().rstrip(";")

    if ";" in cleaned:
        return "Multiple statements are not allowed."

    if not re.match(r"^\s*SELECT\b", cleaned, re.IGNORECASE):
        return "Only SELECT statements are allowed."

    upper_sql = cleaned.upper()
    for keyword in DESTRUCTIVE_KEYWORDS:
        if re.search(rf"\b{keyword}\b", upper_sql):
            return f"Query contains a disallowed keyword: {keyword}"

    return None


def execute_sql(df: pd.DataFrame, sql: str) -> pd.DataFrame:
    """
    Validates and executes a SELECT query against the dataframe (loaded
    into a cached in-memory SQLite table — see build_sqlite_connection).
    Raises ValueError if invalid.
    """
    error = validate_sql(sql)
    if error:
        raise ValueError(error)

    conn = build_sqlite_connection(df)
    try:
        result = pd.read_sql_query(sql, conn)
    except Exception as e:
        raise ValueError(f"SQL execution failed: {e}")

    return result