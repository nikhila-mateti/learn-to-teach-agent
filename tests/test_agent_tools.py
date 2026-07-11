"""Agent tool loading tests."""

from app.agents.tools import (
    load_approved_knowledge,
    load_learning_path,
    load_topic_notes,
    load_writing_profile,
    select_teaching_example,
    TeachingExampleCandidate,
)


def test_load_learning_path():
    payload = load_learning_path.invoke({})
    assert payload["current_topic"] == "Docker"
    assert "vLLM" in payload["upcoming_topics"]
    assert payload["long_term_goal"]


def test_load_topic_notes_available():
    payload = load_topic_notes.invoke({"topic": "Docker"})
    assert payload["notes_available"] is True
    assert "FastAPI" in payload["notes"]


def test_load_topic_notes_missing():
    payload = load_topic_notes.invoke({"topic": "Missing Topic"})
    assert payload["notes_available"] is False
    assert payload["notes"] == ""


def test_load_approved_knowledge():
    payload = load_approved_knowledge.invoke({"topic": "Docker"})
    assert payload["knowledge_available"] is True
    assert payload["facts"]
    assert payload["commands"]
    assert payload["source_references"]


def test_missing_knowledge_pack():
    payload = load_approved_knowledge.invoke({"topic": "NoSuchTopic"})
    assert payload["knowledge_available"] is False


def test_load_writing_profile():
    payload = load_writing_profile.invoke({})
    assert "prohibitions" in payload
    assert any("first-person" in p.lower() or "personal" in p.lower() for p in payload["prohibitions"])


def test_select_teaching_example_prefers_correctness():
    weak_original = TeachingExampleCandidate(
        title="Lunch box",
        scenario="A lunch box analogy",
        explanation="Generic",
        connection_to_goal="Weak",
        technical_correctness=2,
        beginner_clarity=5,
        path_relevance=2,
        memorability=5,
        originality=5,
        misleading_risk=4,
    )
    strong_technical = TeachingExampleCandidate(
        title="FastAPI inference image",
        scenario="Suppose you package a FastAPI inference API",
        explanation="Dependencies and ports",
        connection_to_goal="Leads to Kubernetes and vLLM",
        technical_correctness=5,
        beginner_clarity=4,
        path_relevance=5,
        memorability=3,
        originality=3,
        misleading_risk=1,
    )
    selected = select_teaching_example([weak_original, strong_technical])
    assert selected.title == "FastAPI inference image"
