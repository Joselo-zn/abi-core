"""invoke_classifier: a decision model (Laya) on Ollama's /v1/systemone.

The HTTP side is simulated with httpx.MockTransport, so this runs without
Ollama. Spec: .abi/specs/not-implemented/routing-laya-classifier.md
"""

import asyncio
import json

import httpx
import pytest

import abi_core.agent.classifier as classifier
from abi_core.agent import ClassifierError, invoke_classifier

NOUL = {"type": "noul", "instructions": "Deliverable?", "criteria": {"true": "yes", "false": "no"}}
CHOICE = {"type": "choice", "instructions": "Reply?",
          "criteria": {"approve": "accepts", "reject": "cancels"}}


def _serve(monkeypatch, handler):
    """Route the module's httpx.AsyncClient through `handler`; returns the
    list of requests it received."""
    seen = []
    real = httpx.AsyncClient

    def factory(*a, **k):
        def h(request):
            seen.append(request)
            return handler(request)
        return real(transport=httpx.MockTransport(h), timeout=k.get("timeout"))

    monkeypatch.setattr(classifier.httpx, "AsyncClient", factory)
    return seen


def _ok(answers):
    return lambda request: httpx.Response(200, json={"model": "laya", "answers": answers, "usage": {}})


def test_sends_state_and_questions_to_systemone(monkeypatch):
    monkeypatch.setenv("CLASSIFIER_BASE_URL", "http://laya-host:11434/")
    monkeypatch.setenv("CLASSIFIER_MODEL", "laya:421m-english-bf16")
    seen = _serve(monkeypatch, _ok({"art": {"type": "noul", "noul": 0.9}}))
    answers = asyncio.run(invoke_classifier("User message: make a game", {"art": NOUL}))
    assert answers == {"art": {"type": "noul", "noul": 0.9}}
    (req,) = seen
    assert str(req.url) == "http://laya-host:11434/v1/systemone"
    body = json.loads(req.content)
    assert body == {"model": "laya:421m-english-bf16", "state": "User message: make a game",
                    "questions": {"art": NOUL}}


def test_defaults_to_ollama_host_and_laya(monkeypatch):
    monkeypatch.delenv("CLASSIFIER_BASE_URL", raising=False)
    monkeypatch.delenv("CLASSIFIER_MODEL", raising=False)
    monkeypatch.setenv("OLLAMA_HOST", "http://ollama:11434")
    seen = _serve(monkeypatch, _ok({"q": {"type": "choice", "choice": "approve", "confidence": 0.9}}))
    asyncio.run(invoke_classifier("x", {"q": CHOICE}))
    assert str(seen[0].url) == "http://ollama:11434/v1/systemone"
    assert json.loads(seen[0].content)["model"] == "laya"


def test_arguments_override_environment(monkeypatch):
    monkeypatch.setenv("CLASSIFIER_BASE_URL", "http://env:1")
    seen = _serve(monkeypatch, _ok({"q": {"type": "noul", "noul": 0.1}}))
    asyncio.run(invoke_classifier("x", {"q": NOUL}, model="m", base_url="http://arg:2"))
    assert str(seen[0].url) == "http://arg:2/v1/systemone"
    assert json.loads(seen[0].content)["model"] == "m"


@pytest.mark.parametrize("state, questions", [
    ("", {"q": NOUL}),
    ("   ", {"q": NOUL}),
    ("x", {}),
    ("x", {"q": {"type": "free_text", "criteria": {"a": "b"}}}),
    ("x", {"q": {"type": "noul", "instructions": "?"}}),
    ("x", {f"q{i}": NOUL for i in range(65)}),
])
def test_malformed_requests_fail_before_any_call(monkeypatch, state, questions):
    seen = _serve(monkeypatch, _ok({}))
    with pytest.raises(ValueError):
        asyncio.run(invoke_classifier(state, questions))
    assert seen == []


@pytest.mark.parametrize("response", [
    httpx.Response(404, json={"error": "model 'x' not found"}),
    httpx.Response(200, json={"error": "questions.q: bad"}),
    httpx.Response(500, text="boom"),
    httpx.Response(200, json={"answers": {"other": {}}}),
])
def test_model_errors_raise_classifier_error(monkeypatch, response):
    _serve(monkeypatch, lambda request: response)
    with pytest.raises(ClassifierError):
        asyncio.run(invoke_classifier("x", {"q": NOUL}))


def test_unreachable_raises_classifier_error(monkeypatch):
    def refuse(request):
        raise httpx.ConnectError("refused", request=request)
    _serve(monkeypatch, refuse)
    with pytest.raises(ClassifierError, match="unreachable"):
        asyncio.run(invoke_classifier("x", {"q": NOUL}))


def test_timeout_raises_classifier_error(monkeypatch):
    def slow(request):
        raise httpx.ReadTimeout("timed out", request=request)
    _serve(monkeypatch, slow)
    with pytest.raises(ClassifierError, match="unreachable"):
        asyncio.run(invoke_classifier("x", {"q": NOUL}, timeout=0.1))


SCORE = {"type": "score", "instructions": "How clear?", "criteria": ["unclear", "clear"]}


@pytest.mark.parametrize("body", [
    [1, 2],
    "laya",
    {"answers": ["not", "an", "object"]},
    {"answers": {"q": "yes"}},
])
def test_non_object_responses_raise_classifier_error(monkeypatch, body):
    _serve(monkeypatch, lambda request: httpx.Response(200, json=body))
    with pytest.raises(ClassifierError):
        asyncio.run(invoke_classifier("x", {"q": NOUL}))


@pytest.mark.parametrize("question, answer", [
    (NOUL, {"type": "noul"}),
    (NOUL, {"type": "noul", "noul": "high"}),
    (CHOICE, {"type": "choice", "confidence": 0.9}),
    (CHOICE, {"type": "choice", "choice": "approve"}),
    (SCORE, {}),
])
def test_incomplete_answers_raise_classifier_error(monkeypatch, question, answer):
    # The router treats a ClassifierError as confidence 0 and asks the user
    # again; an incomplete answer must never reach it as data.
    _serve(monkeypatch, _ok({"q": answer}))
    with pytest.raises(ClassifierError, match="incomplete|not an object"):
        asyncio.run(invoke_classifier("x", {"q": question}))


@pytest.mark.parametrize("question, answer", [
    (NOUL, {"type": "noul", "noul": 0}),
    (CHOICE, {"type": "choice", "choice": "reject", "confidence": 0.2, "probabilities": {}}),
    (SCORE, {"type": "score", "score": 3}),
])
def test_complete_answers_are_returned_as_given(monkeypatch, question, answer):
    _serve(monkeypatch, _ok({"q": answer}))
    assert asyncio.run(invoke_classifier("x", {"q": question})) == {"q": answer}



def test_score_takes_a_list_of_levels(monkeypatch):
    seen = _serve(monkeypatch, _ok({"u": {"type": "score", "score": 1.9, "confidence": 0.9}}))
    answers = asyncio.run(invoke_classifier("server down", {"u": SCORE}))
    assert answers["u"]["score"] == 1.9
    assert json.loads(seen[0].content)["questions"]["u"]["criteria"] == ["unclear", "clear"]


@pytest.mark.parametrize("criteria", [{"a": "b"}, ["only one"], ["a", ""], [f"l{i}" for i in range(11)], ["a", 1]])
def test_bad_score_criteria_fail_before_any_call(monkeypatch, criteria):
    seen = _serve(monkeypatch, _ok({}))
    with pytest.raises(ValueError, match="score criteria"):
        asyncio.run(invoke_classifier("x", {"u": {**SCORE, "criteria": criteria}}))
    assert seen == []


def test_choice_needs_two_options(monkeypatch):
    _serve(monkeypatch, _ok({}))
    with pytest.raises(ValueError, match="2-26"):
        asyncio.run(invoke_classifier("x", {"q": {**CHOICE, "criteria": {"approve": "accepts"}}}))


def test_score_answer_without_score_is_incomplete(monkeypatch):
    _serve(monkeypatch, _ok({"u": {"type": "score", "confidence": 0.5}}))
    with pytest.raises(ClassifierError, match="incomplete"):
        asyncio.run(invoke_classifier("x", {"u": SCORE}))
