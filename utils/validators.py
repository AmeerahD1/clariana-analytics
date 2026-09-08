"""
Input validation and sanitization helpers.
"""
import re

MAX_QUESTION_LENGTH = 500


def sanitize_question(question: str) -> str:
    """
    Strips control characters and caps length before a user's question
    is sent to the LLM or stored in conversation history. Returns the
    cleaned string — never raises, since a slightly-too-long or messy
    question is still a valid question, just trimmed.
    """
    if not question:
        return ""

    cleaned = "".join(ch for ch in question if ch.isprintable() or ch in "\n\t ")
    cleaned = cleaned.strip()

    if len(cleaned) > MAX_QUESTION_LENGTH:
        cleaned = cleaned[:MAX_QUESTION_LENGTH]

    return cleaned


def redact_secrets(text: str) -> str:
    """
    Scrubs anything shaped like an API key from a string before it's
    logged or displayed. Defense in depth — most providers don't echo
    keys in error messages, but this guarantees one never leaks even if
    a future SDK version does.
    """
    if not text:
        return text

    patterns = [
        r"sk-[a-zA-Z0-9\-_]{10,}",       # OpenAI/Anthropic-style
        r"AIza[a-zA-Z0-9\-_]{10,}",      # Google (legacy) style
        r"AQ\.[a-zA-Z0-9\-_.]{10,}",     # Google (new) style
    ]
    redacted = text
    for pattern in patterns:
        redacted = re.sub(pattern, "[REDACTED_KEY]", redacted)
    return redacted