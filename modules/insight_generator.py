"""
Generates a structured business insight (finding / explanation / impact /
recommendation) from an already-computed result. Never calculates numbers
itself — only interprets and contextualizes what query_engine already
computed, same boundary as ai_analyzer.py's explain_result.
"""
import json
import pandas as pd

from prompts.insight_prompt import INSIGHT_SYSTEM_PROMPT

REQUIRED_KEYS = {"finding", "explanation", "business_impact", "recommendation"}


def _result_to_text(result) -> str:
    if isinstance(result, pd.DataFrame):
        return result.to_string(index=False)
    return str(result)


def validate_insight(insight: dict) -> str | None:
    """Returns an error message if the insight JSON is malformed, else None."""
    if not isinstance(insight, dict):
        return "Insight is not a JSON object."
    missing = REQUIRED_KEYS - insight.keys()
    if missing:
        return f"Insight is missing required fields: {', '.join(missing)}"
    for key in REQUIRED_KEYS:
        if not isinstance(insight[key], str) or not insight[key].strip():
            return f"Field '{key}' must be a non-empty string."
    return None


def generate_insight(client_call, question: str, plan_or_sql: dict, result) -> dict:
    """
    client_call: a function that takes (system_prompt, user_message) and
    returns the raw text response — this lets insight_generator stay
    provider-agnostic, reusing whichever LLM client ai_analyzer.py already
    set up (OpenAI/Gemini), without duplicating client setup here.

    Returns a validated insight dict, or raises ValueError.
    """
    result_text = _result_to_text(result)
    user_message = (
        f"Question: {question}\n"
        f"Analysis performed: {json.dumps(plan_or_sql)}\n"
        f"Actual computed result:\n{result_text}"
    )

    raw_text = client_call(INSIGHT_SYSTEM_PROMPT, user_message).strip()
    raw_text = raw_text.removeprefix("```json").removeprefix("```").removesuffix("```").strip()

    try:
        insight = json.loads(raw_text)
    except json.JSONDecodeError:
        raise ValueError(f"AI did not return valid JSON for insight. Raw response: {raw_text}")

    error = validate_insight(insight)
    if error:
        raise ValueError(error)

    return insight