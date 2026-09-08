"""
Builds interactive filter widgets from whatever columns actually exist in
the dataset, and applies them to produce one filtered DataFrame that every
downstream section (dashboard, AI analyst, EDA) reads from consistently.
"""
import pandas as pd
import streamlit as st

from modules.dashboard import COLUMN_ALIASES, find_column

# Fields we offer as filters, in the order they'll appear in the UI.
FILTERABLE_FIELDS = ["date", "region", "category", "product", "customer_segment", "payment_method"]

# Extend dashboard's alias map with the two customer/payment fields it
# doesn't already define, so find_column works for those too.
EXTRA_ALIASES = {
    "customer_segment": ["Customer_Segment", "customer_segment", "Segment"],
    "payment_method": ["Payment_Method", "payment_method", "Payment"],
}


def _find_column(df: pd.DataFrame, field: str) -> str | None:
    if field in COLUMN_ALIASES:
        return find_column(df, field)
    for candidate in EXTRA_ALIASES.get(field, []):
        if candidate in df.columns:
            return candidate
    return None


def render_filters(df: pd.DataFrame) -> dict:
    """
    Renders filter widgets for whichever fields exist in df. Returns a
    dict of {actual_column_name: selected_value_or_range}, omitting any
    field that isn't present or wasn't narrowed from its default ("All").
    """
    active_filters = {}

    available = {field: _find_column(df, field) for field in FILTERABLE_FIELDS}
    present_fields = {f: c for f, c in available.items() if c is not None}

    if not present_fields:
        st.caption("No standard filterable columns (date, region, category, etc.) found in this dataset.")
        return active_filters

    cols = st.columns(len(present_fields))

    for widget_col, (field, actual_col) in zip(cols, present_fields.items()):
        with widget_col:
            if field == "date" and pd.api.types.is_datetime64_any_dtype(df[actual_col]):
                min_date = df[actual_col].min()
                max_date = df[actual_col].max()
                if pd.notna(min_date) and pd.notna(max_date):
                    date_range = st.date_input(
                        "Date range", value=(min_date.date(), max_date.date()),
                        min_value=min_date.date(), max_value=max_date.date(),
                    )
                    if isinstance(date_range, tuple) and len(date_range) == 2:
                        active_filters[actual_col] = ("date_range", date_range[0], date_range[1])
            else:
                options = ["All"] + sorted(df[actual_col].dropna().unique().tolist(), key=str)
                selected = st.selectbox(actual_col.replace("_", " "), options=options, key=f"filter_{actual_col}")
                if selected != "All":
                    active_filters[actual_col] = ("equals", selected)

    return active_filters


def apply_filters(df: pd.DataFrame, active_filters: dict) -> pd.DataFrame:
    """Applies the filter dict from render_filters to produce a narrowed DataFrame."""
    filtered = df.copy()

    for col, spec in active_filters.items():
        if spec[0] == "equals":
            filtered = filtered[filtered[col] == spec[1]]
        elif spec[0] == "date_range":
            start_date, end_date = spec[1], spec[2]
            filtered = filtered[
                (filtered[col].dt.date >= start_date) & (filtered[col].dt.date <= end_date)
            ]

    return filtered


def describe_active_filters(active_filters: dict) -> str:
    """One-line human-readable summary, e.g. 'Region = North, Category = Electronics'."""
    if not active_filters:
        return "No filters applied — showing all data."
    parts = []
    for col, spec in active_filters.items():
        if spec[0] == "equals":
            parts.append(f"{col} = {spec[1]}")
        elif spec[0] == "date_range":
            parts.append(f"{col} between {spec[1]} and {spec[2]}")
    return "Active filters: " + ", ".join(parts)