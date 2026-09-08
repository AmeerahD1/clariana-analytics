import json

import streamlit as st
import pandas as pd
import plotly.express as px
from streamlit_option_menu import option_menu

from modules.data_loader import load_file
from modules.data_cleaner import (
    detect_missing_values,
    detect_duplicates,
    detect_invalid_dates,
    detect_negative_values,
    detect_outliers_iqr,
    detect_inconsistent_categories,
    apply_cleaning,
)
from modules.filters import render_filters, apply_filters, describe_active_filters
from modules.data_profiler import (
    get_overview,
    get_data_quality,
    get_numerical_stats,
    get_categorical_analysis,
)
from modules.dashboard import (
    detect_available_columns,
    compute_kpis,
    get_revenue_trend,
    get_profit_trend,
    get_grouped_totals,
)
from modules.query_engine import execute_plan, execute_sql
from modules.ai_analyzer import (
    interpret_question,
    explain_result,
    interpret_question_sql,
    call_llm_raw,
    summarize_turn_for_history,
)
from modules.visualization import choose_chart_type, render_chart
from modules.insight_generator import generate_insight
from modules.eda_generator import generate_eda_report, render_report_markdown
from modules.forecasting import get_numeric_columns, get_date_columns, run_forecast
from modules.anomaly_detection import detect_anomalies, get_anomaly_summary
from modules.segmentation import (
    compute_rfm,
    score_rfm,
    assign_segments,
    run_kmeans_segmentation,
    get_segment_summary,
)
from prompts.insight_prompt import SEGMENTATION_SYSTEM_PROMPT
from modules.recommendation_engine import gather_available_findings, generate_recommendations
from modules.report_generator import to_csv_bytes, to_excel_bytes, build_full_html_report
from utils.validators import sanitize_question
from utils.theme import apply_theme, apply_plotly_theme
from config.branding import (
    APP_NAME,
    BRAND_TAGLINE,
    BRAND_MARK,
    BRAND_LOGO_URL,
    BRAND_PAGE_ICON,
    BRAND_PRIMARY_COLOR,
    BRAND_PRIMARY_LIGHT,
    BRAND_PANEL_COLOR,
    BRAND_POWERED_BY_NAME,
    BRAND_POWERED_BY_URL,
    BRAND_SHOW_POWERED_BY,
)

# ============================================================
# PAGE CONFIG + STYLING
# ============================================================

st.set_page_config(page_title=APP_NAME, page_icon=BRAND_PAGE_ICON, layout="wide")

apply_theme()
apply_plotly_theme()


def render_header(icon: str, title: str, subtitle: str = ""):
    """Consistent gradient banner header used at the top of every page,
    replacing plain st.header() calls for a more branded, less generic look."""
    subtitle_html = f"<p>{subtitle}</p>" if subtitle else ""
    st.markdown(f"""
    <div class="page-header">
        <h1>{icon} {title}</h1>
        {subtitle_html}
    </div>
    """, unsafe_allow_html=True)

PAGE_DEFS = [
    ("Dashboard", "house-door-fill"),
    ("Data Upload", "cloud-arrow-up-fill"),
    ("Data Explorer", "search"),
    ("Analytics", "bar-chart-line-fill"),
    ("AI Analyst", "robot"),
    ("Visualization", "graph-up-arrow"),
    ("Forecasting", "moon-stars-fill"),
    ("Anomaly Detection", "exclamation-triangle-fill"),
    ("Customer Segmentation", "people-fill"),
    ("AI Recommendations", "lightbulb-fill"),
    ("Reports", "file-earmark-text-fill"),
]
PAGE_NAMES = [name for name, _ in PAGE_DEFS]
PAGE_ICONS = [icon for _, icon in PAGE_DEFS]


def get_active_data():
    """
    Returns the DataFrame every page (other than Data Explorer, which owns
    the filter widgets) should read from: the most recently filtered
    version if the user has visited Data Explorer, otherwise a sensible
    fallback (cleaned data, or raw data if cleaning hasn't been applied).
    Same session_state keys used throughout Phases 2-22 — nothing about
    what's computed changes here, only how pages access it.
    """
    if "filtered_df" in st.session_state:
        return st.session_state["filtered_df"]
    return st.session_state.get("cleaned_df", st.session_state["raw_df"])


def empty_state(message: str):
    st.info(f"ℹ️ {message}")


# ============================================================
# PAGE: 🏠 Dashboard (home / welcome)
# ============================================================

def page_home():
    render_header(BRAND_PAGE_ICON, APP_NAME, BRAND_TAGLINE)

    if "raw_df" not in st.session_state:
        st.markdown("### Welcome 👋")
        st.write(
            "Upload a CSV or Excel file to get started. Once loaded, you'll be able to "
            "clean, explore, filter, and ask natural-language questions about your data — "
            "with AI-generated insights, forecasts, anomaly detection, customer "
            "segmentation, and exportable reports along the way."
        )
        empty_state("Head to **📂 Data Upload** in the sidebar to begin.")
        return

    df = st.session_state["raw_df"]
    filtered_df = get_active_data()

    st.success(f"Currently working with **{st.session_state['uploaded_filename']}**")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Rows (raw)", f"{len(df):,}")
    c2.metric("Rows in view", f"{len(filtered_df):,}", help="Reflects any filters applied in Data Explorer.")
    c3.metric("Columns", df.shape[1])
    c4.metric(
        "Cleaning applied", "Yes" if "cleaned_df" in st.session_state else "Not yet",
        help="Visit Data Upload to review and apply cleaning actions.",
    )

    st.divider()
    st.markdown("#### Where to go next")

    shortcuts = [
        ("🔍", "Data Explorer", "Profile the dataset and apply filters."),
        ("📊", "Analytics", "KPIs, trends, and category breakdowns."),
        ("🤖", "AI Analyst", "Ask questions in plain English."),
        ("📈", "Visualization", "One-click automated EDA report."),
        ("🔮", "Forecasting", "Project a metric forward in time."),
        ("⚠️", "Anomaly Detection", "Spot unusual values automatically."),
        ("👥", "Customer Segmentation", "RFM and K-Means grouping."),
        ("💡", "AI Recommendations", "A prioritized action list."),
        ("📄", "Reports", "Export everything as one file."),
    ]
    nav_cols = st.columns(3)
    for i, (icon, title, desc) in enumerate(shortcuts):
        with nav_cols[i % 3]:
            with st.container(border=True):
                st.markdown(f"##### {icon} {title}")
                st.caption(desc)
                if st.button("Open →", key=f"nav_card_{title}", use_container_width=True):
                    st.session_state["pending_nav"] = title
                    st.rerun()


# ============================================================
# PAGE: 📂 Data Upload (Upload + Cleaning)
# ============================================================

def page_upload():
    render_header("📂", "Data Upload", "Bring in a CSV or Excel file to get started.")

    uploaded_file = st.file_uploader(
        "Upload a CSV or Excel file",
        type=["csv", "xlsx", "xls"],
        help="Files up to 50 MB. Supported formats: .csv, .xlsx, .xls",
    )

    if uploaded_file is not None:
        if "raw_df" not in st.session_state or st.session_state.get("uploaded_filename") != uploaded_file.name:
            df_loaded, error = load_file(uploaded_file)
            if error:
                st.error(error)
            else:
                st.session_state["raw_df"] = df_loaded
                st.session_state["uploaded_filename"] = uploaded_file.name
                st.session_state.pop("cleaned_df", None)
                st.session_state.pop("filtered_df", None)

    if "raw_df" not in st.session_state:
        empty_state("Upload a file above to get started.")
        return

    df = st.session_state["raw_df"]

    st.success(f"Loaded '{st.session_state['uploaded_filename']}' successfully.")

    col1, col2 = st.columns(2)
    col1.metric("Rows", df.shape[0])
    col2.metric("Columns", df.shape[1])

    st.subheader("Preview (first 10 rows)")
    st.dataframe(df.head(10), use_container_width=True)

    st.subheader("Column Names & Data Types")
    dtype_df = df.dtypes.reset_index()
    dtype_df.columns = ["Column", "Data Type"]
    st.dataframe(dtype_df, use_container_width=True)

    # --------------------------------------------------------------
    st.markdown("### 🧹 Data Cleaning")

    missing_summary = detect_missing_values(df)
    dup_count, dup_rows = detect_duplicates(df)

    date_col_candidates = [c for c in df.columns if "date" in c.lower()]
    date_col = date_col_candidates[0] if date_col_candidates else None
    invalid_dates = detect_invalid_dates(df, date_col) if date_col else pd.DataFrame()

    positive_cols = [c for c in ["Quantity", "Unit_Price", "Revenue", "Cost"] if c in df.columns]
    negative_summary = detect_negative_values(df, positive_cols)

    category_col_candidates = [c for c in df.columns if "payment" in c.lower() or "method" in c.lower()]
    category_col = category_col_candidates[0] if category_col_candidates else None
    inconsistent = detect_inconsistent_categories(df, category_col) if category_col else {}

    col_a, col_b, col_c, col_d = st.columns(4)
    col_a.metric("Missing (cols affected)", len(missing_summary))
    col_b.metric("Duplicate Rows", dup_count)
    col_c.metric("Invalid Dates", len(invalid_dates))
    col_d.metric("Negative-Value Issues", sum(negative_summary.values()))

    with st.expander("🔍 View detailed issues"):
        if not missing_summary.empty:
            st.write("**Missing Values**")
            st.dataframe(missing_summary, use_container_width=True)
        else:
            st.write("No missing values detected.")

        if dup_count > 0:
            st.write(f"**Duplicate Rows ({dup_count})**")
            st.dataframe(dup_rows.head(10), use_container_width=True)

        if date_col and not invalid_dates.empty:
            st.write(f"**Invalid Dates in '{date_col}' ({len(invalid_dates)})**")
            st.dataframe(invalid_dates[[date_col]].head(10), use_container_width=True)

        if negative_summary:
            st.write("**Negative Values Found**")
            st.json(negative_summary)

        if inconsistent:
            st.write(f"**Inconsistent Categories in '{category_col}'**")
            st.json(inconsistent)

    st.subheader("Choose Cleaning Actions")
    do_remove_dupes = st.checkbox(
        f"Remove {dup_count} duplicate rows", value=(dup_count > 0), disabled=(dup_count == 0),
        help="Keeps the first occurrence of each duplicated row.",
    )
    do_fix_dates = st.checkbox(
        f"Convert '{date_col}' to proper date type (invalid dates become blank)" if date_col else "No date column detected",
        value=(date_col is not None),
        disabled=(date_col is None),
        help="Required before trend charts, forecasting, or segmentation can use this column.",
    )
    do_standardize = st.checkbox(
        f"Standardize '{category_col}' text formatting" if category_col else "No category column detected",
        value=(category_col is not None),
        disabled=(category_col is None),
        help="Normalizes casing/whitespace so 'north' and 'North' aren't treated as different categories.",
    )

    if st.button("Apply Cleaning", type="primary"):
        cleaned_df, summary = apply_cleaning(
            df,
            remove_duplicates=do_remove_dupes,
            fix_dates_column=date_col if do_fix_dates else None,
            standardize_categories_column=category_col if do_standardize else None,
        )
        st.session_state["cleaned_df"] = cleaned_df
        st.session_state.pop("filtered_df", None)
        st.success("Cleaning applied.")
        st.json(summary)

    if "cleaned_df" in st.session_state:
        st.subheader("Cleaned Data Preview")
        st.dataframe(st.session_state["cleaned_df"].head(10), use_container_width=True)
        empty_state("Head to **🔍 Data Explorer** to profile and filter this data.")


# ============================================================
# PAGE: 🔍 Data Explorer (Filters + Profiling)
# ============================================================

def page_explorer():
    render_header("🔍", "Data Explorer", "Filter your data and review profiling stats.")

    df = st.session_state["raw_df"]
    base_df = st.session_state.get("cleaned_df", df)

    st.subheader("🔎 Filters")
    active_filters = render_filters(base_df)
    filtered_df = apply_filters(base_df, active_filters)

    st.session_state["filtered_df"] = filtered_df
    st.session_state["active_filters"] = active_filters

    st.caption(describe_active_filters(active_filters))
    st.caption(f"Showing {len(filtered_df)} of {len(base_df)} rows.")

    dl_col1, dl_col2 = st.columns(2)
    dl_col1.download_button(
        "📥 Download filtered data (CSV)", data=to_csv_bytes(filtered_df),
        file_name="filtered_data.csv", mime="text/csv",
    )
    dl_col2.download_button(
        "📥 Download filtered data (Excel)", data=to_excel_bytes(filtered_df, "Filtered Data"),
        file_name="filtered_data.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

    st.divider()

    # --------------------------------------------------------------
    st.subheader("📊 Data Profiling")

    profile_df = filtered_df
    if not active_filters:
        st.caption("Profiling all cleaned data — apply filters above to profile a subset instead.")
    else:
        st.caption("Profiling the filtered data.")

    overview = get_overview(profile_df)
    quality = get_data_quality(profile_df)

    st.markdown("**Dataset Overview**")
    o1, o2, o3 = st.columns(3)
    o1.metric("Rows", overview["rows"])
    o2.metric("Columns", overview["columns"])
    o3.metric("Memory Usage (MB)", overview["memory_usage_mb"])

    o4, o5, o6 = st.columns(3)
    o4.metric("Numeric Columns", len(overview["numeric_columns"]))
    o5.metric("Categorical Columns", len(overview["categorical_columns"]))
    o6.metric("Date Columns", len(overview["datetime_columns"]))

    st.markdown("**Data Quality**")
    q1, q2, q3 = st.columns(3)
    q1.metric("Missing Cells", quality["missing_total"])
    q2.metric("Missing % of All Cells", f"{quality['missing_pct_of_all_cells']}%")
    q3.metric("Duplicate Rows", quality["duplicate_rows"])

    if quality["suspicious_columns"]:
        st.warning("**Suspicious columns:**\n" + "\n".join(f"- {s}" for s in quality["suspicious_columns"]))

    st.markdown("**Numerical Statistics**")
    numerical_stats = get_numerical_stats(profile_df)
    if not numerical_stats.empty:
        st.dataframe(numerical_stats, use_container_width=True)
    else:
        empty_state("No numeric columns found in this dataset.")

    st.markdown("**Categorical Analysis**")
    categorical_analysis = get_categorical_analysis(profile_df)
    if categorical_analysis:
        cat_tabs = st.tabs(list(categorical_analysis.keys()))
        for tab, (col_name, info) in zip(cat_tabs, categorical_analysis.items()):
            with tab:
                st.write(f"**{info['unique_count']}** unique values")
                st.bar_chart(info["top_values"].set_index(col_name)["Count"])
                st.dataframe(info["top_values"], use_container_width=True)
    else:
        empty_state("No categorical columns found in this dataset.")


# ============================================================
# PAGE: 📊 Analytics (KPI Dashboard)
# ============================================================

def page_analytics():
    render_header("📊", "Analytics Dashboard", "Key metrics, trends, and category breakdowns.")

    dash_df = get_active_data()
    cols = detect_available_columns(dash_df)

    kpis = compute_kpis(dash_df, cols)

    if not kpis:
        empty_state(
            "No recognizable sales columns (Revenue, Orders, Customers, etc.) "
            "were found in this dataset, so a sales dashboard isn't available. "
            "Visit 🔍 Data Explorer for general profiling instead."
        )
        return

    st.subheader("Key Metrics")
    kpi_cols = st.columns(len(kpis))
    for kpi_col, (label, value) in zip(kpi_cols, kpis.items()):
        if "Average" in label or "Revenue" in label or "Profit" in label:
            kpi_col.metric(label, f"₹{value:,.2f}")
        else:
            kpi_col.metric(label, f"{value:,.0f}")

    st.subheader("Trends & Breakdowns")

    revenue_trend = get_revenue_trend(dash_df, cols)
    if revenue_trend is not None and not revenue_trend.empty:
        st.write("**Revenue Trend (Monthly)**")
        st.line_chart(revenue_trend.set_index("Month"))
    elif cols["date"] and cols["revenue"]:
        st.caption("Revenue trend needs the date column converted first — apply date cleaning in Data Upload.")

    profit_trend = get_profit_trend(dash_df, cols)
    if profit_trend is not None and not profit_trend.empty:
        st.write("**Profit Trend (Monthly)**")
        st.line_chart(profit_trend.set_index("Month"))

    chart_col1, chart_col2 = st.columns(2)

    with chart_col1:
        by_category = get_grouped_totals(dash_df, "category", "revenue", cols)
        if by_category is not None:
            st.write(f"**Revenue by {cols['category']}**")
            st.bar_chart(by_category.set_index(cols["category"]))

        by_region = get_grouped_totals(dash_df, "region", "revenue", cols)
        if by_region is not None:
            st.write(f"**Revenue by {cols['region']}**")
            st.bar_chart(by_region.set_index(cols["region"]))

    with chart_col2:
        top_products = get_grouped_totals(dash_df, "product", "revenue", cols, top_n=10)
        if top_products is not None:
            st.write("**Top Products by Revenue**")
            st.bar_chart(top_products.set_index(cols["product"]))


# ============================================================
# PAGE: 🤖 AI Analyst
# ============================================================

def page_ai_analyst():
    render_header("🤖", "AI Analyst", "Ask your data a question in plain English.")

    ai_df = get_active_data()

    if "conversation_history" not in st.session_state:
        st.session_state["conversation_history"] = []

    if st.session_state["conversation_history"]:
        with st.expander(f"💬 Conversation history ({len(st.session_state['conversation_history'])} turns)"):
            for turn in st.session_state["conversation_history"]:
                st.text(turn)
        if st.button("Clear conversation"):
            st.session_state["conversation_history"] = []
            st.rerun()

    engine_choice = st.radio(
        "Execution engine",
        options=["Pandas", "SQL"],
        horizontal=True,
        help="Both engines validate the AI's plan before running anything — this just lets you compare approaches.",
    )

    question = st.text_input(
        "Ask your data a question",
        placeholder="e.g. What product generated the highest revenue?",
    )
    question = sanitize_question(question)

    if st.button("Ask", type="primary") and question:
        if engine_choice == "Pandas":
            with st.spinner("Interpreting your question..."):
                try:
                    plan = interpret_question(
                        question, ai_df, history=st.session_state["conversation_history"]
                    )
                except Exception as e:
                    st.error(f"Couldn't interpret the question: {e}")
                    plan = None

            if plan:
                with st.expander("🔧 Analysis plan (for transparency)"):
                    st.json(plan)

                with st.spinner("Calculating..."):
                    try:
                        result = execute_plan(ai_df, plan)
                    except ValueError as e:
                        st.error(f"Couldn't execute the analysis: {e}")
                        result = None

                if result is not None:
                    st.session_state["conversation_history"].append(
                        summarize_turn_for_history(question, result)
                    )

                    st.subheader("Answer")
                    if isinstance(result, pd.DataFrame):
                        st.dataframe(result, use_container_width=True)
                        st.download_button(
                            "📥 Download this result (CSV)", data=to_csv_bytes(result),
                            file_name="analysis_result.csv", mime="text/csv",
                            key=f"dl_pandas_{len(st.session_state['conversation_history'])}",
                        )
                    else:
                        st.metric(plan.get("metric", "Result"), f"{result:,.2f}")

                    chart_type = choose_chart_type(plan, result)
                    fig = render_chart(plan, result, chart_type)
                    if fig is not None:
                        st.plotly_chart(fig, use_container_width=True)

                    with st.spinner("Generating insight..."):
                        try:
                            insight = generate_insight(call_llm_raw, question, plan, result)
                            st.subheader("💡 Insight")
                            st.markdown(f"**Finding:** {insight['finding']}")
                            st.markdown(f"**Explanation:** {insight['explanation']}")
                            st.markdown(f"**Business Impact:** {insight['business_impact']}")
                            st.success(f"**Recommendation:** {insight['recommendation']}")
                        except ValueError as e:
                            st.warning(f"Result calculated, but insight generation failed: {e}")

        else:  # SQL engine
            with st.spinner("Generating SQL..."):
                try:
                    sql = interpret_question_sql(
                        question, ai_df, history=st.session_state["conversation_history"]
                    )
                except Exception as e:
                    st.error(f"Couldn't generate SQL: {e}")
                    sql = None

            if sql:
                with st.expander("🔧 Generated SQL (for transparency)"):
                    st.code(sql, language="sql")

                with st.spinner("Executing query..."):
                    try:
                        result = execute_sql(ai_df, sql)
                    except ValueError as e:
                        st.error(f"Couldn't execute the query: {e}")
                        result = None

                if result is not None:
                    st.session_state["conversation_history"].append(
                        summarize_turn_for_history(question, result)
                    )

                    st.subheader("Answer")
                    st.dataframe(result, use_container_width=True)
                    st.download_button(
                        "📥 Download this result (CSV)", data=to_csv_bytes(result),
                        file_name="analysis_result.csv", mime="text/csv",
                        key=f"dl_sql_{len(st.session_state['conversation_history'])}",
                    )

                    if result.shape[1] == 2:
                        synthetic_plan = {"operation": "group_by"}
                        chart_type = choose_chart_type(synthetic_plan, result)
                        fig = render_chart(synthetic_plan, result, chart_type)
                        if fig is not None:
                            st.plotly_chart(fig, use_container_width=True)

                    with st.spinner("Generating insight..."):
                        try:
                            insight = generate_insight(call_llm_raw, question, {"sql": sql}, result)
                            st.subheader("💡 Insight")
                            st.markdown(f"**Finding:** {insight['finding']}")
                            st.markdown(f"**Explanation:** {insight['explanation']}")
                            st.markdown(f"**Business Impact:** {insight['business_impact']}")
                            st.success(f"**Recommendation:** {insight['recommendation']}")
                        except ValueError as e:
                            st.warning(f"Result calculated, but insight generation failed: {e}")


# ============================================================
# PAGE: 📈 Visualization (Automated EDA Report)
# ============================================================

def page_visualization():
    render_header("📈", "Visualization — Automated EDA Report", "One-click exploratory analysis with AI-written findings.")

    eda_df = get_active_data()

    st.caption("Runs profiling, correlation, and outlier analysis across the current view, then asks AI to summarize it.")

    if st.button("Generate AI Data Analysis", type="primary"):
        with st.spinner("Running full exploratory analysis..."):
            try:
                report = generate_eda_report(call_llm_raw, eda_df)
                st.session_state["eda_report"] = report
            except ValueError as e:
                st.error(f"Couldn't generate the EDA report: {e}")

    if "eda_report" not in st.session_state:
        empty_state("Click **Generate AI Data Analysis** to produce a full report.")
        return

    report = st.session_state["eda_report"]
    summary = report["summary"]
    facts = report["facts"]

    st.subheader("Data Quality")
    st.write(summary["data_quality_notes"])

    st.subheader("Notable Correlations")
    st.write(summary["notable_correlations"])
    if facts["correlations"]:
        corr_df = pd.DataFrame(facts["correlations"])
        st.dataframe(corr_df, use_container_width=True)

    st.subheader("Key Findings")
    for item in summary["key_findings"]:
        st.markdown(f"- {item}")

    st.subheader("Business Insights")
    for item in summary["business_insights"]:
        st.markdown(f"- {item}")

    st.subheader("Recommendations")
    for item in summary["recommendations"]:
        st.markdown(f"- {item}")

    if facts["outliers"]:
        st.subheader("Detected Outliers (IQR method)")
        outlier_df = pd.DataFrame(facts["outliers"])
        st.dataframe(outlier_df, use_container_width=True)

    report_markdown = render_report_markdown(report)
    st.download_button(
        "📥 Download Report (Markdown)",
        data=report_markdown,
        file_name="eda_report.md",
        mime="text/markdown",
    )


# ============================================================
# PAGE: 🔮 Forecasting
# ============================================================

def page_forecasting():
    render_header("🔮", "Forecasting", "Project a metric forward using historical trend.")

    forecast_df_source = get_active_data()
    numeric_cols = get_numeric_columns(forecast_df_source)
    date_cols = get_date_columns(forecast_df_source)

    if not numeric_cols or not date_cols:
        empty_state(
            "Forecasting needs at least one numeric column and one properly "
            "converted date column. Make sure date cleaning has been applied in Data Upload."
        )
        return

    fc1, fc2, fc3 = st.columns(3)
    with fc1:
        forecast_metric = st.selectbox("Metric to forecast", options=numeric_cols)
    with fc2:
        forecast_date_col = st.selectbox("Date column", options=date_cols)
    with fc3:
        forecast_horizon = st.selectbox(
            "Forecast period",
            options=[
                ("Next 7 days", 7, "D"),
                ("Next 30 days", 30, "D"),
                ("Next 90 days", 90, "D"),
                ("Next 6 months", 6, "ME"),
            ],
            format_func=lambda x: x[0],
        )

    if st.button("Generate Forecast", type="primary"):
        _, periods, freq = forecast_horizon
        try:
            result = run_forecast(forecast_df_source, forecast_date_col, forecast_metric, periods, freq)
            st.session_state["forecast_result"] = result
        except ValueError as e:
            st.error(str(e))

    if "forecast_result" not in st.session_state:
        empty_state("Choose a metric, date column, and horizon, then click **Generate Forecast**.")
        return

    result = st.session_state["forecast_result"]

    hist = result["historical"].copy()
    fc = result["forecast"].copy()

    hist["type"] = "Historical"
    hist = hist.rename(columns={"value": "amount"})

    fc_display = fc.rename(columns={"forecast": "amount"})
    fc_display["type"] = "Forecast"

    combined = pd.concat([
        hist[["date", "amount", "type"]],
        fc_display[["date", "amount", "type"]],
    ])

    fig = px.line(
        combined, x="date", y="amount", color="type", markers=True,
        title=f"{result['metric_col']} — Historical vs Forecast",
    )
    fig.add_scatter(
        x=list(fc["date"]) + list(fc["date"])[::-1],
        y=list(fc["upper_bound"]) + list(fc["lower_bound"])[::-1],
        fill="toself", fillcolor="rgba(99,110,250,0.15)",
        line=dict(color="rgba(255,255,255,0)"), name="95% confidence range",
        showlegend=True,
    )
    st.plotly_chart(fig, use_container_width=True)

    if result["expected_growth_pct"] is not None:
        direction = "growth" if result["expected_growth_pct"] >= 0 else "decline"
        st.metric(
            f"Expected {direction} vs. historical average",
            f"{abs(result['expected_growth_pct']):.1f}%",
        )

    st.download_button(
        "📥 Download forecast (CSV)", data=to_csv_bytes(fc),
        file_name="forecast.csv", mime="text/csv",
    )

    st.caption(
        "⚠️ This forecast is a simple linear trend projection based on historical "
        "patterns. It does not account for seasonality, external events, or "
        "structural changes in the business, and should be treated as a directional "
        "estimate rather than a guaranteed outcome."
    )


# ============================================================
# PAGE: ⚠️ Anomaly Detection
# ============================================================

def page_anomaly_detection():
    render_header("⚠️", "Anomaly Detection", "Flag unusual values with a plain-language reason.")

    anomaly_df_source = get_active_data()
    numeric_cols_for_anomaly = anomaly_df_source.select_dtypes(include="number").columns.tolist()

    if not numeric_cols_for_anomaly:
        empty_state("No numeric columns available to scan for anomalies.")
        return

    anomaly_summary = get_anomaly_summary(anomaly_df_source, numeric_cols_for_anomaly)

    if anomaly_summary:
        st.caption(
            "Anomalies detected in: "
            + ", ".join(f"{col} ({count})" for col, count in anomaly_summary.items())
        )
    else:
        st.caption("No anomalies detected in any numeric column at current filters.")

    anomaly_metric = st.selectbox(
        "Column to inspect", options=numeric_cols_for_anomaly, key="anomaly_metric_select"
    )

    anomalies = detect_anomalies(anomaly_df_source, anomaly_metric)

    if anomalies.empty:
        st.success(f"No anomalies detected in '{anomaly_metric}'.")
        return

    st.dataframe(anomalies, use_container_width=True)
    st.download_button(
        "📥 Download anomalies (CSV)", data=to_csv_bytes(anomalies),
        file_name="anomalies.csv", mime="text/csv",
    )

    fig_anomaly = px.scatter(
        anomaly_df_source.reset_index(),
        x="index", y=anomaly_metric,
        title=f"{anomaly_metric} — anomalies highlighted",
    )
    anomaly_indices = anomaly_df_source[
        anomaly_df_source[anomaly_metric].isin(anomalies["Value"])
    ].index
    highlight_df = anomaly_df_source.loc[anomaly_indices].reset_index()
    fig_anomaly.add_scatter(
        x=highlight_df["index"], y=highlight_df[anomaly_metric],
        mode="markers", marker=dict(color="red", size=10, symbol="x"),
        name="Anomaly",
    )
    st.plotly_chart(fig_anomaly, use_container_width=True)


# ============================================================
# PAGE: 👥 Customer Segmentation
# ============================================================

def page_segmentation():
    render_header("👥", "Customer Segmentation", "RFM analysis and rule-based or K-Means grouping.")

    seg_df_source = get_active_data()
    seg_cols = detect_available_columns(seg_df_source)

    if not seg_cols["customer_id"] or not seg_cols["date"] or not seg_cols["revenue"]:
        empty_state(
            "Customer segmentation needs a customer ID, a converted date column, "
            "and a revenue column. Make sure date cleaning has been applied in Data Upload."
        )
        return
    if not pd.api.types.is_datetime64_any_dtype(seg_df_source[seg_cols["date"]]):
        empty_state("The date column needs to be converted first — apply date cleaning in Data Upload.")
        return

    method = st.radio("Segmentation method", options=["RFM (rule-based)", "K-Means (ML)"], horizontal=True)

    if st.button("Run Segmentation", type="primary"):
        rfm = compute_rfm(seg_df_source, seg_cols["customer_id"], seg_cols["date"], seg_cols["revenue"])

        if method == "RFM (rule-based)":
            scored = score_rfm(rfm)
            segmented = assign_segments(scored)
            st.session_state["segmentation_result"] = {"method": "rfm", "data": segmented}
        else:
            clustered = run_kmeans_segmentation(rfm)
            st.session_state["segmentation_result"] = {"method": "kmeans", "data": clustered}

    if "segmentation_result" not in st.session_state:
        empty_state("Choose a method and click **Run Segmentation**.")
        return

    seg_result = st.session_state["segmentation_result"]
    data = seg_result["data"]

    if seg_result["method"] == "rfm":
        st.subheader("Segment Sizes")
        segment_counts = data["Segment"].value_counts().reset_index()
        segment_counts.columns = ["Segment", "Count"]
        fig_seg = px.pie(segment_counts, names="Segment", values="Count", title="Customer Segments")
        st.plotly_chart(fig_seg, use_container_width=True)

        summary = get_segment_summary(data)
        st.subheader("Segment Profiles")
        st.dataframe(summary, use_container_width=True)

        with st.expander("View all customers with segment labels"):
            st.dataframe(data, use_container_width=True)

        if st.button("Explain Segments with AI"):
            with st.spinner("Generating segment explanations..."):
                try:
                    user_message = f"Segment summary:\n{summary.to_string(index=False)}"
                    raw = call_llm_raw(SEGMENTATION_SYSTEM_PROMPT, user_message).strip()
                    raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
                    explanations = json.loads(raw)
                    st.session_state["segment_explanations"] = explanations["segments"]
                except Exception as e:
                    st.error(f"Couldn't generate segment explanations: {e}")

        if "segment_explanations" in st.session_state:
            st.subheader("💡 Segment Insights")
            for seg in st.session_state["segment_explanations"]:
                with st.expander(f"📌 {seg['segment']}"):
                    st.write(f"**Description:** {seg['description']}")
                    st.success(f"**Recommended Action:** {seg['recommended_action']}")

    else:  # kmeans
        st.subheader("Cluster Sizes")
        cluster_counts = data["Cluster"].value_counts().sort_index().reset_index()
        cluster_counts.columns = ["Cluster", "Count"]
        st.bar_chart(cluster_counts.set_index("Cluster"))

        st.subheader("Cluster Profiles")
        cluster_summary = data.groupby("Cluster").agg(
            Customer_Count=("Cluster", "count"),
            Avg_Recency_Days=("Recency", "mean"),
            Avg_Frequency=("Frequency", "mean"),
            Avg_Monetary=("Monetary", "mean"),
        ).round(1).reset_index()
        st.dataframe(cluster_summary, use_container_width=True)
        st.caption(
            "K-Means clusters are numeric groupings only — interpreting what "
            "each cluster represents requires reviewing the profile table above, "
            "since cluster IDs carry no inherent business meaning."
        )


# ============================================================
# PAGE: 💡 AI Recommendations
# ============================================================

def page_recommendations():
    render_header("💡", "AI Recommendations", "A prioritized action list synthesized from your analysis.")

    st.caption(
        "Synthesizes recommendations from whatever analysis has already been run "
        "elsewhere in the app — EDA report, forecast, anomaly detection, or segmentation."
    )

    if st.button("Generate Recommendations", type="primary"):
        findings_bundle = gather_available_findings(st.session_state)
        with st.spinner("Synthesizing recommendations..."):
            try:
                recommendations = generate_recommendations(call_llm_raw, findings_bundle)
                st.session_state["recommendations"] = recommendations
            except ValueError as e:
                st.error(str(e))

    if "recommendations" not in st.session_state:
        empty_state(
            "No recommendations yet — run the EDA report (📈 Visualization), a forecast "
            "(🔮 Forecasting), anomaly detection, or segmentation first, then generate here."
        )
        return

    priority_colors = {"High": "🔴", "Medium": "🟡", "Low": "🟢"}
    for rec in st.session_state["recommendations"]:
        with st.container(border=True):
            st.markdown(f"{priority_colors.get(rec['priority'], '⚪')} **Priority: {rec['priority']}**")
            st.write(f"**Finding:** {rec['finding']}")
            st.write(f"**Recommendation:** {rec['recommendation']}")
            st.caption(f"Objective: {rec['expected_business_objective']}")


# ============================================================
# PAGE: 📄 Reports (Export)
# ============================================================

def page_reports():
    render_header("📄", "Reports", "Export everything computed in this session.")

    st.caption(
        "Combines everything computed so far in this session — EDA, forecast, "
        "anomalies, segments, recommendations, and Q&A history — into one file."
    )

    full_report_html = build_full_html_report(st.session_state)
    st.download_button(
        "📥 Download Full Report (HTML)",
        data=full_report_html,
        file_name="ai_data_analyst_report.html",
        mime="text/html",
        type="primary",
    )

    st.caption("Tip: open the downloaded HTML file in a browser and use Ctrl+P → Save as PDF if you need a PDF copy.")


# ============================================================
# MAIN — sidebar navigation + routing
# ============================================================

def main():
    data_loaded = "raw_df" in st.session_state

    with st.sidebar:
        if BRAND_LOGO_URL:
            logo_html = f'<img src="{BRAND_LOGO_URL}" style="width:34px;height:34px;border-radius:9px;object-fit:contain;" />'
        else:
            logo_html = f'<div class="brand-mark">{BRAND_MARK}</div>'

        st.markdown(
            f"""
            <div class="brand-lockup">
                {logo_html}
                <div>
                    <div class="brand-name">{APP_NAME}</div>
                    <div class="brand-tagline">{BRAND_TAGLINE}</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        if not data_loaded:
            st.info("Upload a file to unlock the full menu.")
            page = "Data Upload"
        else:
            # If a "Where to go next" card was clicked on the Dashboard, force
            # the menu to that page once, then clear it so normal manual
            # navigation afterward isn't overridden on every rerun.
            manual_index = None
            pending = st.session_state.pop("pending_nav", None)
            if pending in PAGE_NAMES:
                manual_index = PAGE_NAMES.index(pending)

            page = option_menu(
                menu_title=None,
                options=PAGE_NAMES,
                icons=PAGE_ICONS,
                default_index=0,
                manual_select=manual_index,
                key="main_nav_menu",
                styles={
                    "container": {"padding": "0", "background-color": "transparent"},
                    "icon": {"color": BRAND_PRIMARY_LIGHT, "font-size": "16px"},
                    "nav-link": {
                        "font-size": "14px",
                        "text-align": "left",
                        "margin": "2px 0",
                        "border-radius": "8px",
                        "--hover-color": "rgba(0, 180, 200, 0.15)",
                    },
                    "nav-link-selected": {
                        "background": f"linear-gradient(120deg, {BRAND_PANEL_COLOR}, #0f4a5c)",
                        "font-weight": "600",
                    },
                },
            )

        st.divider()
        if data_loaded:
            st.caption(f"📄 {st.session_state.get('uploaded_filename', '')}")
            rows_in_view = len(get_active_data())
            st.caption(f"🔢 {rows_in_view:,} rows in current view")

        if BRAND_SHOW_POWERED_BY:
            st.markdown(
                f"""
                <div class="powered-by">
                    Powered by <a href="{BRAND_POWERED_BY_URL}" target="_blank">{BRAND_POWERED_BY_NAME}</a>
                </div>
                """,
                unsafe_allow_html=True,
            )

    if page == "Dashboard":
        page_home()
    elif page == "Data Upload":
        page_upload()
    elif not data_loaded:
        empty_state("Upload a file in **Data Upload** first.")
    elif page == "Data Explorer":
        page_explorer()
    elif page == "Analytics":
        page_analytics()
    elif page == "AI Analyst":
        page_ai_analyst()
    elif page == "Visualization":
        page_visualization()
    elif page == "Forecasting":
        page_forecasting()
    elif page == "Anomaly Detection":
        page_anomaly_detection()
    elif page == "Customer Segmentation":
        page_segmentation()
    elif page == "AI Recommendations":
        page_recommendations()
    elif page == "Reports":
        page_reports()


if __name__ == "__main__":
    main()