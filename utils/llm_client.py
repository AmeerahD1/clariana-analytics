"""
Unified LLM provider client. One function — chat_completion() — is the
entire surface every other module talks to (ai_analyzer.py,
insight_generator.py, eda_generator.py, recommendation_engine.py). None
of them know or care which provider is behind it.

Supported providers, selected via LLM_PROVIDER in .env:
    "openai" (default) — gpt-4o-mini / gpt-4o / any chat-completions model
    "gemini"            — gemini-1.5-flash / gemini-1.5-pro / etc.

Adding a third provider later (e.g. Anthropic) means adding one branch
here — every call site stays unchanged.
"""
from config.settings import LLM_PROVIDER, LLM_MODEL, get_api_key

_client = None
_client_provider = None


def _get_openai_client():
    global _client, _client_provider
    if _client is None or _client_provider != "openai":
        from openai import OpenAI
        _client = OpenAI(api_key=get_api_key())
        _client_provider = "openai"
    return _client


def _get_gemini_client():
    global _client, _client_provider
    if _client is None or _client_provider != "gemini":
        import google.generativeai as genai
        genai.configure(api_key=get_api_key())
        _client = genai
        _client_provider = "gemini"
    return _client


def chat_completion(system_prompt: str, user_message: str, max_tokens: int = 300) -> str:
    """
    Sends a system + user message to whichever provider is configured
    and returns the plain-text response. Raises the raw provider
    exception on failure — callers (ai_analyzer.py) are responsible for
    translating that into a friendly message via utils.helpers.translate_llm_error,
    since only they know the right context label for logging.
    """
    if LLM_PROVIDER == "gemini":
        client = _get_gemini_client()
        model = client.GenerativeModel(model_name=LLM_MODEL, system_instruction=system_prompt)
        response = model.generate_content(
            user_message,
            generation_config={"max_output_tokens": max_tokens, "temperature": 0.2},
        )
        return response.text.strip()

    # Default: OpenAI (and any OpenAI-compatible endpoint via LLM_BASE_URL)
    client = _get_openai_client()
    response = client.chat.completions.create(
        model=LLM_MODEL,
        max_tokens=max_tokens,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
    )
    return response.choices[0].message.content.strip()
