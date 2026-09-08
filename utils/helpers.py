"""
General-purpose helpers shared across modules.
"""
from utils.logger import log_error


def translate_llm_error(exception: Exception, context: str = "LLM call") -> str:
    """
    Maps common LLM-provider exceptions to plain-language messages, and
    logs the real technical detail via utils/logger.py. Returns the
    friendly message to show in the UI.
    """
    log_error(context, exception)

    error_name = type(exception).__name__
    error_text = str(exception).lower()

    if "ratelimit" in error_name.lower() or "rate limit" in error_text or "429" in error_text:
        return "The AI service is temporarily rate-limited. Please wait a moment and try again."

    if "authentication" in error_name.lower() or "api key" in error_text or "401" in error_text:
        return "The AI service rejected the request — the API key may be missing or invalid. Check your .env file."

    if "connection" in error_name.lower() or "connection" in error_text:
        return "Couldn't reach the AI service — check your internet connection and try again."

    if "timeout" in error_name.lower() or "timeout" in error_text:
        return "The AI service took too long to respond. Please try again."

    if "quota" in error_text or "insufficient" in error_text:
        return "The AI service account has run out of usage quota. Check your provider account."

    # Fallback: still friendly, still logged above with full detail.
    return "Something went wrong while contacting the AI service. Please try again in a moment."