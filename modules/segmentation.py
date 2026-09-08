"""
RFM (Recency, Frequency, Monetary) customer segmentation, with rule-based
quintile scoring as the primary, explainable method, and K-Means clustering
offered as an optional alternative on the same RFM features.

compute_rfm is cached via st.cache_data — the groupby/aggregation is the
expensive part and is a pure function of the DataFrame.
"""
import pandas as pd
import numpy as np
import streamlit as st
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler


@st.cache_data(show_spinner=False)
def compute_rfm(df: pd.DataFrame, customer_col: str, date_col: str, revenue_col: str) -> pd.DataFrame:
    """
    Computes Recency (days since last order), Frequency (number of
    distinct orders), and Monetary (total revenue) per customer.
    """
    clean = df.dropna(subset=[customer_col, date_col, revenue_col])
    reference_date = clean[date_col].max() + pd.Timedelta(days=1)

    rfm = clean.groupby(customer_col).agg(
        Recency=(date_col, lambda x: (reference_date - x.max()).days),
        Frequency=(date_col, "count"),
        Monetary=(revenue_col, "sum"),
    ).reset_index()

    return rfm


def score_rfm(rfm: pd.DataFrame) -> pd.DataFrame:
    """
    Scores each RFM dimension 1-5 by quintile. Lower recency is better
    (scored inverse); higher frequency/monetary are better (scored direct).
    """
    scored = rfm.copy()

    def safe_qcut(series, ascending):
        try:
            if not ascending:
                return pd.qcut(series, 5, labels=[1, 2, 3, 4, 5], duplicates="drop").astype(int)
            else:
                return pd.qcut(series, 5, labels=[5, 4, 3, 2, 1], duplicates="drop").astype(int)
        except ValueError:
            ranks = series.rank(method="first", ascending=ascending)
            bins = pd.qcut(ranks, min(5, series.nunique()), labels=False, duplicates="drop") + 1
            return bins if ascending else (6 - bins)

    scored["R_Score"] = safe_qcut(scored["Recency"], ascending=True)
    scored["F_Score"] = safe_qcut(scored["Frequency"], ascending=False)
    scored["M_Score"] = safe_qcut(scored["Monetary"], ascending=False)
    scored["RFM_Score"] = scored["R_Score"] + scored["F_Score"] + scored["M_Score"]

    return scored


def assign_segments(scored_rfm: pd.DataFrame) -> pd.DataFrame:
    """Maps combined RFM scores to business-friendly segment labels."""
    def label(row):
        r, f, m = row["R_Score"], row["F_Score"], row["M_Score"]
        if r >= 4 and f >= 4 and m >= 4:
            return "Champions"
        elif r >= 3 and f >= 3:
            return "Loyal Customers"
        elif r >= 4 and f <= 2:
            return "Potential Loyalists"
        elif r <= 2 and f >= 3:
            return "At Risk"
        else:
            return "Low-Value"

    result = scored_rfm.copy()
    result["Segment"] = result.apply(label, axis=1)
    return result


def run_kmeans_segmentation(rfm: pd.DataFrame, n_clusters: int = 4) -> pd.DataFrame:
    """
    Optional alternative: K-Means clustering on standardized RFM features.
    Returns the same rfm frame with a numeric 'Cluster' column added —
    clusters are NOT auto-labeled with business names, since that
    interpretation genuinely requires looking at the resulting centers.
    """
    features = rfm[["Recency", "Frequency", "Monetary"]]
    scaled = StandardScaler().fit_transform(features)

    model = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
    clusters = model.fit_predict(scaled)

    result = rfm.copy()
    result["Cluster"] = clusters
    return result


def get_segment_summary(segmented_rfm: pd.DataFrame) -> pd.DataFrame:
    """Aggregates each segment's size and average RFM values — this is
    what gets handed to the LLM for explanation, never raw customer data."""
    summary = segmented_rfm.groupby("Segment").agg(
        Customer_Count=("Segment", "count"),
        Avg_Recency_Days=("Recency", "mean"),
        Avg_Frequency=("Frequency", "mean"),
        Avg_Monetary=("Monetary", "mean"),
    ).round(1).reset_index()
    return summary.sort_values("Avg_Monetary", ascending=False)