"""
Centralized configuration. Reads from .env — never hardcode keys here.
"""
import os
from dotenv import load_dotenv

load_dotenv()

_DEFAULT_MODELS = {
    "openai": "gpt-4o-mini",
    "gemini": "gemini-1.5-flash",
}

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai").strip().lower()
if LLM_PROVIDER not in _DEFAULT_MODELS:
    LLM_PROVIDER = "openai"

LLM_API_KEY = os.getenv("LLM_API_KEY")
LLM_MODEL = os.getenv("LLM_MODEL", _DEFAULT_MODELS[LLM_PROVIDER])

_KEY_HELP_URLS = {
    "openai": "https://platform.openai.com/api-keys",
    "gemini": "https://aistudio.google.com/apikey",
}


def get_api_key() -> str:
    if not LLM_API_KEY or LLM_API_KEY == "your_api_key_here":
        help_url = _KEY_HELP_URLS.get(LLM_PROVIDER, "your provider's dashboard")
        raise ValueError(
            f"LLM_API_KEY is not set for provider '{LLM_PROVIDER}'. Add your real "
            f"API key to the .env file at the project root — get one at {help_url}."
        )
    return LLM_API_KEY
