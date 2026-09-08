"""
Applies the white-label theme: custom CSS for the Streamlit chrome, and a
matching Plotly template so every chart in the app (dashboard trends,
forecasts, anomaly scatter, segmentation pie) automatically picks up the
brand palette with zero changes at each chart's call site.

Both read exclusively from config/branding.py, so re-theming the whole
app for a new client is a .env edit — nothing here needs to change.
"""
import plotly.express as px
import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st

from config.branding import (
    BRAND_DARK_COLOR,
    BRAND_DARK_COLOR_2,
    BRAND_PANEL_COLOR,
    BRAND_PRIMARY_COLOR,
    BRAND_PRIMARY_LIGHT,
    BRAND_TEXT_COLOR,
    BRAND_TEXT_MUTED,
)

_PLOTLY_TEMPLATE_NAME = "brand"

# A small, distinct sequence built around the primary accent so
# multi-series charts (grouped bars, segment pies) stay legible without
# drifting into colours outside the brand family.
_CHART_COLOR_SEQUENCE = [
    BRAND_PRIMARY_COLOR,
    "#7be3ee",
    "#1c5f70",
    "#f2b134",
    "#e85d75",
    "#8a7ce8",
    "#4fd1a5",
    "#c6c6c6",
]


def _build_css() -> str:
    return f"""
<style>
    .stApp {{
        background:
            radial-gradient(circle at 15% 10%, rgba(0, 180, 200, 0.16) 0%, transparent 45%),
            radial-gradient(circle at 85% 90%, rgba(61, 214, 232, 0.10) 0%, transparent 45%),
            linear-gradient(160deg, {BRAND_DARK_COLOR_2} 0%, {BRAND_DARK_COLOR} 45%, #0e3341 100%);
        background-attachment: fixed;
    }}

    .block-container {{ padding-top: 1.5rem; padding-bottom: 3rem; max-width: 1200px; }}

    /* Gradient page-header banner used by render_header() on every page */
    .page-header {{
        background: linear-gradient(120deg, {BRAND_PANEL_COLOR} 0%, #0f4a5c 50%, {BRAND_PANEL_COLOR} 100%);
        padding: 22px 28px;
        border-radius: 14px;
        margin-bottom: 22px;
        box-shadow: 0 4px 18px rgba(0, 180, 200, 0.18);
        border: 1px solid rgba(0, 180, 200, 0.28);
    }}
    .page-header h1 {{
        color: white !important;
        font-size: 1.6rem;
        margin: 0;
        display: flex;
        align-items: center;
        gap: 10px;
    }}
    .page-header p {{
        color: rgba(255,255,255,0.82);
        margin: 6px 0 0 0;
        font-size: 0.95rem;
    }}

    /* KPI / metric cards */
    div[data-testid="stMetric"] {{
        background: rgba(255, 255, 255, 0.04);
        backdrop-filter: blur(6px);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-left: 4px solid {BRAND_PRIMARY_COLOR};
        border-radius: 10px;
        padding: 14px 16px;
        transition: transform 0.15s ease, box-shadow 0.15s ease, border-color 0.15s ease;
    }}
    div[data-testid="stMetric"]:hover {{
        transform: translateY(-2px);
        box-shadow: 0 8px 20px rgba(0, 180, 200, 0.22);
        border-left-color: {BRAND_PRIMARY_LIGHT};
    }}

    /* Bordered containers (recommendation cards, segment insights, home
       shortcuts) get the same frosted hover treatment */
    div[data-testid="stVerticalBlockBorderWrapper"] {{
        background: rgba(255, 255, 255, 0.03);
        backdrop-filter: blur(6px);
        border: 1px solid rgba(255, 255, 255, 0.08) !important;
        border-radius: 12px !important;
        transition: transform 0.15s ease, box-shadow 0.15s ease, border-color 0.15s ease;
    }}
    div[data-testid="stVerticalBlockBorderWrapper"]:hover {{
        transform: translateY(-2px);
        box-shadow: 0 10px 24px rgba(0, 180, 200, 0.20);
        border-color: rgba(61, 214, 232, 0.40) !important;
    }}

    button[kind="primary"] {{
        border-radius: 8px;
        font-weight: 600;
        box-shadow: 0 4px 14px rgba(0, 180, 200, 0.32);
    }}
    button[kind="secondary"] {{ border-radius: 8px; }}

    /* Sidebar */
    section[data-testid="stSidebar"] {{
        background: rgba(8, 27, 34, 0.85);
        backdrop-filter: blur(10px);
        border-right: 1px solid rgba(255, 255, 255, 0.06);
    }}
    section[data-testid="stSidebar"] .block-container {{ padding-top: 1rem; }}

    /* Sidebar brand lockup */
    .brand-lockup {{
        display: flex;
        align-items: center;
        gap: 10px;
        padding: 2px 0 14px 0;
    }}
    .brand-mark {{
        width: 34px;
        height: 34px;
        border-radius: 9px;
        background: linear-gradient(135deg, {BRAND_PRIMARY_COLOR}, #0f4a5c);
        display: flex;
        align-items: center;
        justify-content: center;
        color: white;
        font-weight: 700;
        font-size: 15px;
        flex-shrink: 0;
        box-shadow: 0 2px 10px rgba(0, 180, 200, 0.35);
    }}
    .brand-name {{
        color: {BRAND_TEXT_COLOR};
        font-weight: 700;
        font-size: 1.05rem;
        line-height: 1.15;
    }}
    .brand-tagline {{
        color: {BRAND_TEXT_MUTED};
        font-size: 0.72rem;
        line-height: 1.1;
    }}

    /* "Powered by" footer, pinned at the bottom of the sidebar content */
    .powered-by {{
        margin-top: 18px;
        padding-top: 12px;
        border-top: 1px solid rgba(255, 255, 255, 0.08);
        font-size: 0.72rem;
        color: {BRAND_TEXT_MUTED};
    }}
    .powered-by a {{
        color: {BRAND_PRIMARY_LIGHT};
        text-decoration: none;
        font-weight: 600;
    }}
    .powered-by a:hover {{ text-decoration: underline; }}
</style>
"""


def apply_theme() -> None:
    """Injects the brand CSS. Call once, near the top of app.py."""
    st.markdown(_build_css(), unsafe_allow_html=True)


def apply_plotly_theme() -> None:
    """
    Registers a dark, brand-coloured Plotly template and makes it the
    default for every px.* call in the app, plus sets the default
    discrete colour sequence — so no chart call site needs to know
    about colours at all.
    """
    template = go.layout.Template()
    template.layout = go.Layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=BRAND_TEXT_COLOR, family="Inter, -apple-system, Segoe UI, sans-serif"),
        title=dict(font=dict(color=BRAND_TEXT_COLOR, size=16)),
        xaxis=dict(
            gridcolor="rgba(255,255,255,0.08)",
            zerolinecolor="rgba(255,255,255,0.12)",
            linecolor="rgba(255,255,255,0.16)",
        ),
        yaxis=dict(
            gridcolor="rgba(255,255,255,0.08)",
            zerolinecolor="rgba(255,255,255,0.12)",
            linecolor="rgba(255,255,255,0.16)",
        ),
        legend=dict(bgcolor="rgba(0,0,0,0)"),
        colorway=_CHART_COLOR_SEQUENCE,
    )

    pio.templates[_PLOTLY_TEMPLATE_NAME] = template
    pio.templates.default = _PLOTLY_TEMPLATE_NAME
    px.defaults.template = _PLOTLY_TEMPLATE_NAME
    px.defaults.color_discrete_sequence = _CHART_COLOR_SEQUENCE
