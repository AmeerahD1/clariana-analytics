"""
LLM abstraction layer. Handles:
1. Interpreting a natural-language question into a structured Pandas plan.
2. Interpreting a natural-language question into a SQL query.
3. Explaining a computed result in plain language.
4. Providing a generic raw-text call used by insight_generator.py / eda_generator.py / recommendation_engine.py.
5. Compressing a Q&A turn into a one-line summary for conversation history.

Every LLM call site catches provider-level failures (rate limits, auth
errors, timeouts, connection issues) and translates them into plain
messages via utils.helpers.translate_llm_error — the raw exception detail
is logged (utils/logger.py), never shown directly to the user.

The LLM never computes numbers itself — see query_engine.py for that.

Provider selection (OpenAI, Gemini) happens in utils/llm_client.py — this
module only calls chat_completion() and never touches a provider SDK
directly, so switching providers never requires touching this file.
"""
import json

import pandas as pd
import streamlit as st

from prompts.analyst_prompt import (
    PLAN_SYSTEM_PROMPT,
    EXPLANATION_SYSTEM_PROMPT,
    SQL_SYSTEM_PROMPT,
    build_schema_description,
)
from modules.query_engine import get_sql_schema_description
from utils.llm_client import chat_completion
from utils.helpers import translate_llm_error
from utils.logger import log_error


def get_schema_info(df: pd.DataFrame) -> dict:
    """Compact schema summary — column name -> dtype. No actual data sent."""
    return {col: str(dtype) for col, dtype in df.dtypes.items()}


def build_history_context(history: list[str], max_turns: int = 5) -> str:
    """Formats the last few conversation turns as compact context text."""
    if not history:
        return ""
    recent = history[-max_turns:]
    return "Previous conversation (for resolving references like 'it', 'that', 'those'):\n" + "\n".join(recent)


def summarize_turn_for_history(question: str, result) -> str:
    """
    Compresses one Q&A turn into a single short line for conversation
    history — never the full result table, just enough for the LLM to
    resolve follow-up references like 'it' or 'that region'.
    """
    if isinstance(result, pd.DataFrame):
        if result.empty:
            answer_text = "no results"
        else:
            top_row = result.iloc[0]
            answer_text = ", ".join(f"{col}: {top_row[col]}" for col in result.columns)
    else:
        answer_text = str(result)

    return f"Q: {question} -> A: {answer_text}"


@st.cache_data(show_spinner=False)
def interpret_question(question: str, df: pd.DataFrame, history: list[str] | None = None) -> dict:
    """
    Sends the question + schema + recent conversation history to the LLM,
    returns the parsed Pandas plan dict. Raises ValueError with a friendly
    message on any provider failure or malformed response.
    """
    schema_info = get_schema_info(df)
    schema_text = build_schema_description(schema_info)
    history_text = build_history_context(history or [])

    user_message_parts = [f"Dataset schema:\n{schema_text}"]
    if history_text:
        user_message_parts.append(history_text)
    user_message_parts.append(f"Question: {question}")
    user_message = "\n\n".join(user_message_parts)

    try:
        raw_text = chat_completion(PLAN_SYSTEM_PROMPT, user_message, max_tokens=300)
    except Exception as e:
        raise ValueError(translate_llm_error(e, context="interpret_question"))

    raw_text = raw_text.removeprefix("```json").removeprefix("```").removesuffix("```").strip()

    try:
        plan = json.loads(raw_text)
    except json.JSONDecodeError as e:
        log_error("interpret_question - JSON parse", e)
        raise ValueError(
            "The AI's response couldn't be understood. This can happen occasionally — "
            "please try rephrasing your question."
        )

    return plan


@st.cache_data(show_spinner=False)
def interpret_question_sql(question: str, df: pd.DataFrame, history: list[str] | None = None) -> str:
    """
    Sends the question + SQL schema + recent conversation history to the
    LLM, returns a raw SQL string. Does NOT execute it.
    """
    schema_text = get_sql_schema_description(df)
    history_text = build_history_context(history or [])

    user_message_parts = [schema_text]
    if history_text:
        user_message_parts.append(history_text)
    user_message_parts.append(f"Question: {question}")
    user_message = "\n\n".join(user_message_parts)

    try:
        raw_sql = chat_completion(SQL_SYSTEM_PROMPT, user_message, max_tokens=300)
    except Exception as e:
        raise ValueError(translate_llm_error(e, context="interpret_question_sql"))

    raw_sql = raw_sql.removeprefix("```sql").removeprefix("```").removesuffix("```").strip()
    return raw_sql


@st.cache_data(show_spinner=False)
def explain_result(question: str, plan: dict, result) -> str:
    """Asks the LLM to explain the already-computed result in plain language."""
    if isinstance(result, pd.DataFrame):
        result_text = result.to_string(index=False)
    else:
        result_text = str(result)

    user_message = (
        f"Question: {question}\n"
        f"Plan executed: {json.dumps(plan)}\n"
        f"Actual computed result:\n{result_text}"
    )

    try:
        return chat_completion(EXPLANATION_SYSTEM_PROMPT, user_message, max_tokens=300)
    except Exception as e:
        raise ValueError(translate_llm_error(e, context="explain_result"))


@st.cache_data(show_spinner=False)
def call_llm_raw(system_prompt: str, user_message: str) -> str:
    """
    Generic raw-text LLM call, used by insight_generator.py, eda_generator.py,
    and recommendation_engine.py so they don't need their own client setup.
    """
    try:
        # Generous headroom — EDA/recommendation reports need more than a single insight.
        return chat_completion(system_prompt, user_message, max_tokens=1200)
    except Exception as e:
        raise ValueError(translate_llm_error(e, context="call_llm_raw"))
