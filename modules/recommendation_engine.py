"""
Synthesizes a prioritized business recommendation list from analysis
ALREADY computed elsewhere in the session (EDA, forecasting, anomaly
detection, segmentation) — this module runs no new analysis of its own,
it only asks the LLM to prioritize and phrase actions grounded in facts
that are already sitting in session_state and already shown on screen.
"""
import json

from prompts.insight_prompt import RECOMMENDATION_SYSTEM_PROMPT

REQUIRED_KEYS = {"finding", "recommendation", "priority", "expected_business_objective"}
VALID_PRIORITIES = {"High", "Medium", "Low"}


def gather_available_findings(session_state) -> dict:
    """
    Pulls whatever's already been computed and cached in session_state
    from earlier phases. Returns only the pieces that actually exist —
    the recommendation prompt is built to work with a partial bundle.
    """
    bundle = {}

    eda_report = session_state.get("eda_report")
    if eda_report:
        bundle["eda_key_findings"] = eda_report["summary"].get("key_findings", [])
        bundle["eda_data_quality"] = eda_report["summary"].get("data_quality_notes")

    forecast_result = session_state.get("forecast_result")
    if forecast_result:
        bundle["forecast"] = {
            "metric": forecast_result["metric_col"],
            "expected_growth_pct": forecast_result["expected_growth_pct"],
            "periods": forecast_result["periods"],
        }

    segmentation_result = session_state.get("segmentation_result")
    if segmentation_result and segmentation_result.get("method") == "rfm":
        data = segmentation_result["data"]
        bundle["segment_sizes"] = data["Segment"].value_counts().to_dict()

    return bundle


def validate_recommendations(payload: dict) -> str | None:
    if not isinstance(payload, dict) or "recommendations" not in payload:
        return "Response is missing the 'recommendations' key."
    recs = payload["recommendations"]
    if not isinstance(recs, list) or not recs:
        return "'recommendations' must be a non-empty list."

    for i, rec in enumerate(recs):
        if not isinstance(rec, dict):
            return f"Recommendation {i} is not a JSON object."
        missing = REQUIRED_KEYS - rec.keys()
        if missing:
            return f"Recommendation {i} is missing fields: {', '.join(missing)}"
        if rec["priority"] not in VALID_PRIORITIES:
            return f"Recommendation {i} has an invalid priority: {rec['priority']}"

    return None


def generate_recommendations(client_call, findings_bundle: dict) -> list[dict]:
    """
    client_call: same (system_prompt, user_message) -> str function reused
    from insight_generator.py / eda_generator.py.

    Returns a validated list of recommendation dicts, or raises ValueError.
    """
    if not findings_bundle:
        raise ValueError(
            "No prior analysis found yet. Run the EDA report, forecasting, "
            "anomaly detection, or segmentation first — recommendations are "
            "built from what those sections compute."
        )

    user_message = f"Computed findings bundle:\n{json.dumps(findings_bundle, default=str)}"

    raw_text = client_call(RECOMMENDATION_SYSTEM_PROMPT, user_message).strip()
    raw_text = raw_text.removeprefix("```json").removeprefix("```").removesuffix("```").strip()

    try:
        payload = json.loads(raw_text)
    except json.JSONDecodeError:
        raise ValueError(f"AI did not return valid JSON for recommendations. Raw response: {raw_text}")

    error = validate_recommendations(payload)
    if error:
        raise ValueError(error)

    priority_order = {"High": 0, "Medium": 1, "Low": 2}
    recs = sorted(payload["recommendations"], key=lambda r: priority_order[r["priority"]])
    return recs