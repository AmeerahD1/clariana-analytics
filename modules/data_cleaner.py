"""
Data cleaning utilities. Each function DETECTS an issue and returns
information about it — actual modification only happens when the
caller (app.py) explicitly applies it, after the user has seen and
approved what will change.
"""
import pandas as pd
import numpy as np


def detect_missing_values(df: pd.DataFrame) -> pd.DataFrame:
    """Returns a summary of missing values per column."""
    missing_count = df.isna().sum()
    missing_pct = (missing_count / len(df) * 100).round(2)
    summary = pd.DataFrame({
        "Column": missing_count.index,
        "Missing Count": missing_count.values,
        "Missing %": missing_pct.values,
    })
    return summary[summary["Missing Count"] > 0].reset_index(drop=True)


def detect_duplicates(df: pd.DataFrame) -> tuple[int, pd.DataFrame]:
    """Returns (duplicate_count, the duplicate rows themselves)."""
    dup_mask = df.duplicated(keep="first")
    return dup_mask.sum(), df[dup_mask]


def detect_invalid_dates(df: pd.DataFrame, date_column: str) -> pd.DataFrame:
    """Returns rows where the date column fails to parse."""
    if date_column not in df.columns:
        return pd.DataFrame()
    parsed = pd.to_datetime(df[date_column], errors="coerce", format="mixed")
    invalid_mask = parsed.isna() & df[date_column].notna()
    return df[invalid_mask]


def detect_negative_values(df: pd.DataFrame, columns_should_be_positive: list[str]) -> dict:
    """
    Checks specified numeric columns for negative values where they
    shouldn't logically occur (e.g. Quantity, Revenue, Unit_Price).
    Returns {column: count_of_negative_rows}.
    """
    result = {}
    for col in columns_should_be_positive:
        if col in df.columns and pd.api.types.is_numeric_dtype(df[col]):
            neg_count = (df[col] < 0).sum()
            if neg_count > 0:
                result[col] = int(neg_count)
    return result


def detect_outliers_iqr(df: pd.DataFrame, column: str) -> pd.DataFrame:
    """
    Flags outliers in a numeric column using the IQR method
    (values outside Q1 - 1.5*IQR to Q3 + 1.5*IQR).
    """
    if column not in df.columns or not pd.api.types.is_numeric_dtype(df[column]):
        return pd.DataFrame()

    q1 = df[column].quantile(0.25)
    q3 = df[column].quantile(0.75)
    iqr = q3 - q1
    lower_bound = q1 - 1.5 * iqr
    upper_bound = q3 + 1.5 * iqr

    outlier_mask = (df[column] < lower_bound) | (df[column] > upper_bound)
    return df[outlier_mask]


def detect_inconsistent_categories(df: pd.DataFrame, column: str) -> dict:
    """
    Flags categorical values that look like the same thing but differ
    in casing/whitespace (e.g. 'Credit Card' vs 'credit card').
    Returns {normalized_value: [original_variants]}.
    """
    if column not in df.columns:
        return {}

    unique_vals = df[column].dropna().unique()
    normalized_groups = {}
    for val in unique_vals:
        key = str(val).strip().lower()
        normalized_groups.setdefault(key, []).append(val)

    # Only return groups where there's more than one variant
    return {k: v for k, v in normalized_groups.items() if len(v) > 1}


def apply_cleaning(
    df: pd.DataFrame,
    remove_duplicates: bool = False,
    fix_dates_column: str | None = None,
    standardize_categories_column: str | None = None,
) -> tuple[pd.DataFrame, dict]:
    """
    Applies ONLY the cleaning steps the user has explicitly checked.
    Returns (cleaned_df, summary_of_changes).
    """
    cleaned = df.copy()
    summary = {"original_rows": len(df)}

    if remove_duplicates:
        before = len(cleaned)
        cleaned = cleaned.drop_duplicates(keep="first")
        summary["duplicates_removed"] = before - len(cleaned)

    if fix_dates_column and fix_dates_column in cleaned.columns:
        cleaned[fix_dates_column] = pd.to_datetime(
            cleaned[fix_dates_column], errors="coerce", format="mixed"
        )
        summary["dates_converted_column"] = fix_dates_column
        summary["invalid_dates_now_null"] = int(cleaned[fix_dates_column].isna().sum())

    if standardize_categories_column and standardize_categories_column in cleaned.columns:
        col = standardize_categories_column
        cleaned[col] = cleaned[col].astype(str).str.strip().str.title()
        summary["standardized_column"] = col

    summary["cleaned_rows"] = len(cleaned)
    return cleaned, summary