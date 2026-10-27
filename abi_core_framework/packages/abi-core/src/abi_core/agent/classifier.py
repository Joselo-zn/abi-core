"""
invoke_classifier — call a decision model (Laya on Ollama) instead of a chat
model when an agent has to classify.

A decision model scores the options of typed questions in one forward pass
and returns calibrated probabilities; it does not generate text. Laya is
served by Ollama (>= 0.40) on its own endpoint, ``/v1/systemone``, not the
chat API, so neither LangChain nor ``invoke``/``invoke_structured`` can call
it: this is a direct HTTP call.

    answers = await invoke_classifier(
        state="User message: make me a snake game in Python",
        questions={
            "artifact": {
                "type": "noul",
                "instructions": "Does the user ask for a deliverable?",
                "criteria": {"true": "A deliverable.", "false": "An answer in the conversation."},
            },
        },
    )
    answers["artifact"]["noul"]       # probability of "true"

Question types and their ``criteria``:
- ``choice``: a dict of 2-26 options (name -> description); returns
  ``choice``, ``probabilities`` and ``confidence``.
- ``noul``: a dict ``{"true": ..., "false": ...}``; returns ``noul``, the
  probability of true.
- ``score``: an ordered rubric, a list of 2-10 levels, lowest first; returns
  ``score`` (the expected level, a float), ``legend``, ``probabilities``
  and ``confidence``. What the
answers mean, and what to do with low confidence, is the caller's decision.

Environment:
  CLASSIFIER_MODEL     the decision model (default: laya)
  CLASSIFIER_BASE_URL  the Ollama that serves it (default: OLLAMA_HOST, then
                       http://localhost:11434)

Spec: .abi/specs/not-implemented/routing-laya-classifier.md
"""

import os
from typing import Any, Dict, Optional

import httpx

QUESTION_TYPES = ("choice", "noul", "score")
MAX_QUESTIONS = 64


class ClassifierError(RuntimeError):
    """The decision model rejected the request or could not be reached."""


def _validate(state: str, questions: Dict[str, Dict[str, Any]]) -> None:
    if not isinstance(state, str) or not state.strip():
        raise ValueError("state must be a non-empty string")
    if not isinstance(questions, dict) or not questions:
        raise ValueError("questions must be a non-empty dict of name -> question")
    if len(questions) > MAX_QUESTIONS:
        raise ValueError(f"at most {MAX_QUESTIONS} questions per call, got {len(questions)}")
    for name, q in questions.items():
        if not isinstance(q, dict) or q.get("type") not in QUESTION_TYPES:
            raise ValueError(f"question {name!r}: type must be one of {QUESTION_TYPES}")
        criteria = q.get("criteria")
        if q["type"] == "score":
            # An ordered rubric: a list of 2-10 levels, lowest first.
            if (not isinstance(criteria, list) or not 2 <= len(criteria) <= 10
                    or not all(isinstance(c, str) and c.strip() for c in criteria)):
                raise ValueError(f"question {name!r}: score criteria must be a list of 2-10 levels (strings), lowest first")
        elif q["type"] == "choice":
            if not isinstance(criteria, dict) or not 2 <= len(criteria) <= 26:
                raise ValueError(f"question {name!r}: choice criteria must be a dict of 2-26 options")
        elif not isinstance(criteria, dict) or not criteria:
            raise ValueError(f"question {name!r}: criteria must be a non-empty dict")


async def invoke_classifier(
    state: str,
    questions: Dict[str, Dict[str, Any]],
    *,
    model: Optional[str] = None,
    base_url: Optional[str] = None,
    timeout: float = 60.0,
) -> Dict[str, Dict[str, Any]]:
    """Ask the decision model ``questions`` about ``state``; returns its
    answers keyed by question name, as the model returns them.

    Raises ValueError for a malformed request (checked before any network
    call) and ClassifierError when the model rejects it or is unreachable."""
    _validate(state, questions)
    model = model or os.getenv("CLASSIFIER_MODEL") or "laya"
    base = (base_url or os.getenv("CLASSIFIER_BASE_URL") or os.getenv("OLLAMA_HOST")
            or "http://localhost:11434").rstrip("/")
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(f"{base}/v1/systemone",
                                     json={"model": model, "state": state, "questions": questions})
    except httpx.HTTPError as e:
        raise ClassifierError(f"classifier at {base} unreachable: {type(e).__name__}: {e}") from e
    try:
        body = resp.json()
    except ValueError:
        raise ClassifierError(f"classifier returned HTTP {resp.status_code} with a non-JSON body")
    if not isinstance(body, dict):
        raise ClassifierError(f"classifier returned HTTP {resp.status_code} with a {type(body).__name__}, not an object")
    if resp.status_code != 200 or "error" in body:
        raise ClassifierError(f"classifier rejected the request (HTTP {resp.status_code}): {body.get('error', body)}")
    answers = body.get("answers")
    if not isinstance(answers, dict) or set(answers) != set(questions):
        raise ClassifierError(f"classifier answered {sorted(answers or {}) if isinstance(answers, dict) else answers!r}, "
                              f"asked {sorted(questions)}")
    for name, q in questions.items():
        _check_answer(name, q["type"], answers[name])
    return answers


def _check_answer(name: str, qtype: str, answer: Any) -> None:
    """An incomplete answer is a failure, not data: the caller treats a
    ClassifierError as confidence 0 (routing-laya-classifier.md)."""
    if not isinstance(answer, dict):
        raise ClassifierError(f"answer {name!r} is a {type(answer).__name__}, not an object")
    if qtype == "noul":
        ok = isinstance(answer.get("noul"), (int, float))
    elif qtype == "choice":
        ok = isinstance(answer.get("choice"), str) and isinstance(answer.get("confidence"), (int, float))
    else:  # score
        ok = isinstance(answer.get("score"), (int, float))
    if not ok:
        raise ClassifierError(f"answer {name!r} to a {qtype} question is incomplete: {answer!r}")
