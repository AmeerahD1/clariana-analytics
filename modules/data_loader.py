"""
Reusable data loading utilities for CSV and Excel files.
Returns (dataframe, error_message) — error_message is None on success.
Every failure path returns a clean message; nothing here lets a raw
exception/stack trace reach the UI. Real technical detail is logged
via utils/logger.py.
"""
import pandas as pd
from io import BytesIO

from utils.logger import log_error

SUPPORTED_EXTENSIONS = (".csv", ".xlsx", ".xls")
MAX_FILE_SIZE_MB = 50


def load_file(uploaded_file):
    """
    Load an uploaded file (Streamlit's UploadedFile object) into a DataFrame.

    Returns:
        (pd.DataFrame or None, str or None) — (dataframe, error_message)
    """
    if uploaded_file is None:
        return None, "No file was uploaded."

    filename = uploaded_file.name.lower()

    if not filename.endswith(SUPPORTED_EXTENSIONS):
        return None, (
            f"Unsupported file type: '{uploaded_file.name}'. "
            f"Please upload a CSV or Excel file (.csv, .xlsx, .xls)."
        )

    raw_bytes = uploaded_file.getvalue()

    size_mb = len(raw_bytes) / (1024 * 1024)
    if size_mb > MAX_FILE_SIZE_MB:
        return None, f"File is too large ({size_mb:.1f} MB). Maximum supported size is {MAX_FILE_SIZE_MB} MB."

    if len(raw_bytes) == 0:
        return None, "The uploaded file is empty."

    try:
        if filename.endswith(".csv"):
            df = _load_csv(raw_bytes)
        else:
            df = _load_excel(raw_bytes)
    except Exception as e:
        log_error("data_loader.load_file", e)
        return None, "Couldn't read this file — it may be corrupted or in an unexpected format."

    if df is None or df.empty:
        return None, "The file was read but contains no data."

    return df, None


def _load_csv(raw_bytes: bytes) -> pd.DataFrame:
    """Try common encodings since real-world CSVs aren't always UTF-8."""
    encodings_to_try = ["utf-8", "latin1", "cp1252"]
    last_error = None

    for encoding in encodings_to_try:
        try:
            return pd.read_csv(BytesIO(raw_bytes), encoding=encoding)
        except UnicodeDecodeError as e:
            last_error = e
            continue
        except pd.errors.EmptyDataError:
            raise ValueError("The CSV file has no columns or rows.")
        except pd.errors.ParserError as e:
            raise ValueError(f"The CSV file is malformed: {e}")

    raise ValueError(f"Could not decode the file with any known encoding. {last_error}")


def _load_excel(raw_bytes: bytes) -> pd.DataFrame:
    try:
        return pd.read_excel(BytesIO(raw_bytes))
    except ValueError as e:
        raise ValueError(f"The Excel file could not be parsed: {e}")