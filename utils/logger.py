"""
Centralized logging setup. Technical error details (stack traces, raw
exception text) get written here — never shown directly to the user in
the UI, which should only ever see a plain-language message. Anything
key-shaped is redacted before it touches disk, even in error logs.
"""
import logging
import os

from utils.validators import redact_secrets

LOG_DIR = "logs"
LOG_FILE = os.path.join(LOG_DIR, "app.log")

_logger = None


def get_logger() -> logging.Logger:
    global _logger
    if _logger is not None:
        return _logger

    os.makedirs(LOG_DIR, exist_ok=True)

    logger = logging.getLogger("ai_data_analyst")
    logger.setLevel(logging.INFO)

    if not logger.handlers:
        file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
        file_handler.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
        )
        logger.addHandler(file_handler)

    _logger = logger
    return _logger


def log_error(context: str, exception: Exception) -> None:
    """Logs full exception detail under a short context label, with any
    key-shaped substring redacted first."""
    logger = get_logger()
    safe_message = redact_secrets(f"{context}: {type(exception).__name__}: {exception}")
    logger.error(safe_message)