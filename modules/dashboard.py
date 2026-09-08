"""
Auto-adapting sales dashboard logic. Every function checks for the
columns it needs and returns None/empty gracefully if they're missing —
never assumes the uploaded dataset is a sales dataset.

KPI/trend functions are cached via st.cache_data: they're pure functions
of the DataFrame, so re-running them on an unchanged filtered_df during
an unrelated Streamlit rerun is wasted work.
"""
import pandas as pd
import streamlit as st

COLUMN_ALIASES = {
    "revenue": ["Revenue", "revenue", "Sales", "sales", "Total_Revenue"],
    "profit": ["Profit", "profit", "Total_Profit"],
    "quantity": ["Quantity", "quantity", "Qty", "Units_Sold"],
    "order_id": ["Order_ID", "order_id", "OrderID", "Invoice_ID"],
    "customer_id": ["Customer_ID", "customer_id", "CustomerID"],
    "date": ["Order_Date", "order_date", "Date", "date"],
    "category": ["Category", "category"],
    "product": ["Product", "product", "Product_Name"],
    "region": ["Region", "region"],
}


def find_column(df: pd.DataFrame, field: str) -> str | None:
    """Find the actual column name in df matching a known field alias."""
    for candidate in COLUMN_ALIASES.get(field, []):
        if candidate in df.columns:
            return candidate
    return None


def detect_available_columns(df: pd.DataFrame) -> dict:
    """Returns {field_name: actual_column_name_or_None} for all known fields."""
    return {field: find_column(df, field) for field in COLUMN_ALIASES}


@st.cache_data(show_spinner=False)
def compute_kpis(df: pd.DataFrame, cols: dict) -> dict:
    """
    Computes whichever KPIs are possible given the columns that exist.
    Returns a dict where a missing KPI is simply absent (not zero —
    zero would be misleading; absence is honest about "we don't know").
    """
    kpis = {}

    if cols["revenue"]:
        kpis["Total Revenue"] = df[cols["revenue"]].sum()
        kpis["Average Order Value"] = df[cols["revenue"]].mean()

    if cols["order_id"]:
        kpis["Total Orders"] = df[cols["order_id"]].nunique()

    if cols["customer_id"]:
        kpis["Total Customers"] = df[cols["customer_id"]].nunique()

    if cols["quantity"]:
        kpis["Total Quantity"] = df[cols["quantity"]].sum()

    if cols["profit"]:
        kpis["Total Profit"] = df[cols["profit"]].sum()
        kpis["Average Profit"] = df[cols["profit"]].mean()

    return kpis


@st.cache_data(show_spinner=False)
def get_revenue_trend(df: pd.DataFrame, cols: dict) -> pd.DataFrame | None:
    """Monthly revenue trend, if both a date and revenue column exist."""
    if not cols["date"] or not cols["revenue"]:
        return None
    if not pd.api.types.is_datetime64_any_dtype(df[cols["date"]]):
        return None

    trend = (
        df.dropna(subset=[cols["date"]])
        .set_index(cols["date"])
        .resample("ME")[cols["revenue"]]
        .sum()
        .reset_index()
    )
    trend.columns = ["Month", "Revenue"]
    return trend


@st.cache_data(show_spinner=False)
def get_profit_trend(df: pd.DataFrame, cols: dict) -> pd.DataFrame | None:
    if not cols["date"] or not cols["profit"]:
        return None
    if not pd.api.types.is_datetime64_any_dtype(df[cols["date"]]):
        return None

    trend = (
        df.dropna(subset=[cols["date"]])
        .set_index(cols["date"])
        .resample("ME")[cols["profit"]]
        .sum()
        .reset_index()
    )
    trend.columns = ["Month", "Profit"]
    return trend


@st.cache_data(show_spinner=False)
def get_grouped_totals(df: pd.DataFrame, group_field: str, value_field: str, cols: dict, top_n: int = 10) -> pd.DataFrame | None:
    """Generic: total of value_field grouped by group_field, top N descending."""
    group_col = cols.get(group_field)
    value_col = cols.get(value_field)
    if not group_col or not value_col:
        return None

    grouped = (
        df.groupby(group_col)[value_col]
        .sum()
        .sort_values(ascending=False)
        .head(top_n)
        .reset_index()
    )
    grouped.columns = [group_col, value_col]
    return grouped