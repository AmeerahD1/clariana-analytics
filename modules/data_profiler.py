"""
Data profiling utilities. Pure functions — read-only, no mutation.
Used to render the profiling dashboard in app.py.

Cached via st.cache_data: these are pure functions of the DataFrame, so
re-running them on an unchanged filtered_df during an unrelated Streamlit
rerun (which happens on every widget interaction anywhere on the page)
would otherwise be wasted work.
"""
import pandas as pd
import numpy as np
import streamlit as st


@st.cache_data(show_spinner=False)
def get_overview(df: pd.DataFrame) -> dict:
    """High-level shape/composition of the dataset."""
    numeric_cols = df.select_dtypes(include=np.number).columns.tolist()
    datetime_cols = df.select_dtypes(include="datetime64").columns.tolist()
    categorical_cols = [
        c for c in df.columns if c not in numeric_cols and c not in datetime_cols
    ]

    return {
        "rows": len(df),
        "columns": df.shape[1],
        "memory_usage_mb": round(df.memory_usage(deep=True).sum() / (1024 ** 2), 2),
        "numeric_columns": numeric_cols,
        "categorical_columns": categorical_cols,
        "datetime_columns": datetime_cols,
    }


@st.cache_data(show_spinner=False)
def get_data_quality(df: pd.DataFrame) -> dict:
    """Missing values, duplicates, and per-column uniqueness."""
    missing_total = int(df.isna().sum().sum())
    duplicate_rows = int(df.duplicated().sum())

    unique_counts = df.nunique().to_dict()

    suspicious = []
    for col in df.columns:
        n_unique = unique_counts[col]
        if n_unique == 1:
            suspicious.append(f"'{col}' has only one unique value")
        elif n_unique == len(df) and len(df) > 1 and df[col].dtype == object:
            suspicious.append(f"'{col}' is entirely unique (likely an identifier)")

    return {
        "missing_total": missing_total,
        "missing_pct_of_all_cells": round(missing_total / (df.shape[0] * df.shape[1]) * 100, 2) if len(df) else 0,
        "duplicate_rows": duplicate_rows,
        "unique_counts": unique_counts,
        "suspicious_columns": suspicious,
    }


@st.cache_data(show_spinner=False)
def get_numerical_stats(df: pd.DataFrame) -> pd.DataFrame:
    """Descriptive stats for numeric columns, in a display-friendly shape."""
    numeric_df = df.select_dtypes(include=np.number)
    if numeric_df.empty:
        return pd.DataFrame()

    stats = numeric_df.describe().T
    stats = stats.rename(columns={
        "count": "Count", "mean": "Mean", "std": "Std Dev",
        "min": "Min", "25%": "Q1", "50%": "Median", "75%": "Q3", "max": "Max",
    })
    stats = stats.round(2)
    stats.index.name = "Column"
    return stats.reset_index()


@st.cache_data(show_spinner=False)
def get_categorical_analysis(df: pd.DataFrame, max_categories: int = 10) -> dict:
    """
    For each categorical column: unique count, and top values by frequency.
    Returns {column_name: {"unique_count": int, "top_values": pd.DataFrame}}
    """
    numeric_cols = df.select_dtypes(include=np.number).columns.tolist()
    datetime_cols = df.select_dtypes(include="datetime64").columns.tolist()
    categorical_cols = [
        c for c in df.columns if c not in numeric_cols and c not in datetime_cols
    ]

    result = {}
    for col in categorical_cols:
        value_counts = df[col].value_counts(dropna=True).head(max_categories)
        top_df = value_counts.reset_index()
        top_df.columns = [col, "Count"]
        result[col] = {
            "unique_count": df[col].nunique(),
            "top_values": top_df,
        }
    return result