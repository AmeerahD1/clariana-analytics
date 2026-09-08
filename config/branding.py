"""
White-label branding configuration. Everything a new client deployment
needs to change lives here — and every value can be overridden with an
environment variable, so re-branding for a new client is a .env edit,
never a code change.

Default values below are Clariana's own brand, used when no .env
overrides are present (e.g. running the template for the first time).

To spin up a new client instance:
    1. Copy .env.example to .env
    2. Set BRAND_CLIENT_NAME, BRAND_PRIMARY_COLOR, BRAND_DARK_COLOR
       (and BRAND_LOGO_URL if the client has a logo image)
    3. Set LLM_PROVIDER + LLM_API_KEY
    4. Run the app — every page, chart, and exported report re-themes
       automatically.
"""
import os
from dotenv import load_dotenv

load_dotenv()

# ------------------------------------------------------------------
# Identity — the name shown in the page title, header, and sidebar
# ------------------------------------------------------------------
BRAND_CLIENT_NAME = os.getenv("BRAND_CLIENT_NAME", "Clariana")
BRAND_PRODUCT_NAME = os.getenv("BRAND_PRODUCT_NAME", "Analytics")
BRAND_TAGLINE = os.getenv(
    "BRAND_TAGLINE", "AI-Powered Business Intelligence"
)
APP_NAME = f"{BRAND_CLIENT_NAME} {BRAND_PRODUCT_NAME}".strip()

# Short mark shown in the sidebar/header when no logo image is set.
# Keep it to 1-2 characters — it renders inside a small badge.
BRAND_MARK = os.getenv("BRAND_MARK", "C")

# Optional client logo (PNG/SVG URL or local path under /static). If
# unset, the app falls back to the BRAND_MARK badge above.
BRAND_LOGO_URL = os.getenv("BRAND_LOGO_URL", "")

# Browser tab icon — any single emoji works well as a lightweight favicon.
BRAND_PAGE_ICON = os.getenv("BRAND_PAGE_ICON", "\U0001F4CA")  # 📊

# ------------------------------------------------------------------
# Colour system — dark teal + cyan by default (Clariana brand)
# ------------------------------------------------------------------
BRAND_DARK_COLOR = os.getenv("BRAND_DARK_COLOR", "#0d2e3a")       # base background
BRAND_DARK_COLOR_2 = os.getenv("BRAND_DARK_COLOR_2", "#0a2530")   # deeper gradient stop
BRAND_PANEL_COLOR = os.getenv("BRAND_PANEL_COLOR", "#123c4a")     # sidebar / cards
BRAND_PRIMARY_COLOR = os.getenv("BRAND_PRIMARY_COLOR", "#00b4c8")  # cyan accent
BRAND_PRIMARY_LIGHT = os.getenv("BRAND_PRIMARY_LIGHT", "#3dd6e8")  # hover / glow
BRAND_TEXT_COLOR = os.getenv("BRAND_TEXT_COLOR", "#E7F6F8")
BRAND_TEXT_MUTED = os.getenv("BRAND_TEXT_MUTED", "rgba(231, 246, 248, 0.68)")

# ------------------------------------------------------------------
# Consultancy attribution — stays constant across every client build.
# Set BRAND_SHOW_POWERED_BY=false for a fully white-labelled hand-off
# where no Clariana attribution should appear.
# ------------------------------------------------------------------
BRAND_POWERED_BY_NAME = os.getenv("BRAND_POWERED_BY_NAME", "Clariana")
BRAND_POWERED_BY_URL = os.getenv("BRAND_POWERED_BY_URL", "https://clariana.co.uk")
BRAND_SHOW_POWERED_BY = os.getenv("BRAND_SHOW_POWERED_BY", "true").strip().lower() == "true"
