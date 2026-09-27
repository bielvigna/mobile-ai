from app.agent import SPOILER_POLICY, normalize_spoiler_level


def test_spoiler_level_normalization_defaults_to_none():
    assert normalize_spoiler_level("high") == "HIGH"
    assert normalize_spoiler_level("unknown") == "NONE"


def test_spoiler_levels_have_distinct_policies():
    assert "Do not reveal" in SPOILER_POLICY["NONE"]
    assert "preserve the main twists" in SPOILER_POLICY["MEDIUM"]
    assert "Answer fully" in SPOILER_POLICY["HIGH"]


def test_chat_request_bounds_history_and_content():
    from pydantic import ValidationError
    from app.schemas import ChatRequest

    assert ChatRequest(message="hello", spoiler_level="LOW").spoiler_level == "LOW"
    try:
        ChatRequest(message="x", history=[{"role": "user", "content": "x"}] * 21)
    except ValidationError:
        return
    raise AssertionError("history longer than 20 messages should be rejected")
