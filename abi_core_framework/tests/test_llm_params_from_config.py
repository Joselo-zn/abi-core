"""LLM parameters from the config to LangChain: llm_config_from_env,
LLM_EXTRA_PARAMS, and the Builder's EPHEMERAL_LLM_EXTRA_PARAMS / per-task
override for ephemerals.

Spec: .abi/specs/implemented/llm-params-from-config.md
"""

import importlib.util
import json
import sys
import types
from pathlib import Path

import pytest

from abi_core.agent.llm_provider import create_llm, llm_config_from_env, parse_extra_params

_ENV = ("LLM_PROVIDER", "MODEL_NAME", "LLM_TEMPERATURE", "LLM_BASE_URL", "OLLAMA_HOST",
        "LLM_API_KEY", "LLM_EXTRA_PARAMS", "EPHEMERAL_LLM_EXTRA_PARAMS",
        "ROUTING_DECISION_MODEL_NAME")


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for name in _ENV:
        monkeypatch.delenv(name, raising=False)


def test_defaults_on_ollama():
    cfg = llm_config_from_env()
    assert cfg["provider"] == "ollama"
    assert cfg["model"] == "qwen3:latest"
    assert cfg["temperature"] is None
    assert cfg["base_url"] == "http://localhost:11434"
    assert cfg["extra_params"] == {}


def test_hosted_provider_gets_no_ollama_base_url(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    monkeypatch.setenv("OLLAMA_HOST", "http://ollama:11434")
    assert llm_config_from_env()["base_url"] is None
    monkeypatch.setenv("LLM_BASE_URL", "http://gw/v1")
    assert llm_config_from_env()["base_url"] == "http://gw/v1"


def test_empty_vars_count_as_unset(monkeypatch):
    for name in ("LLM_PROVIDER", "LLM_TEMPERATURE", "LLM_BASE_URL", "LLM_EXTRA_PARAMS"):
        monkeypatch.setenv(name, "")
    cfg = llm_config_from_env()
    assert cfg["provider"] == "ollama" and cfg["temperature"] is None
    assert cfg["base_url"] == "http://localhost:11434" and cfg["extra_params"] == {}


def test_extra_params_env_wins_over_ollama_defaults(monkeypatch):
    monkeypatch.setenv("LLM_EXTRA_PARAMS", '{"reasoning": true, "num_ctx": 8192}')
    cfg = llm_config_from_env(ollama_extra_params={"reasoning": False})
    assert cfg["extra_params"] == {"reasoning": True, "num_ctx": 8192}


def test_ollama_defaults_not_sent_to_other_providers(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    monkeypatch.setenv("LLM_EXTRA_PARAMS", '{"thinking": {"type": "adaptive"}}')
    cfg = llm_config_from_env(ollama_extra_params={"reasoning": False})
    assert cfg["extra_params"] == {"thinking": {"type": "adaptive"}}


def test_model_env_and_temperature(monkeypatch):
    monkeypatch.setenv("ROUTING_DECISION_MODEL_NAME", "granite")
    monkeypatch.setenv("LLM_TEMPERATURE", "0.3")
    cfg = llm_config_from_env(model_env="ROUTING_DECISION_MODEL_NAME")
    assert cfg["model"] == "granite" and cfg["temperature"] == 0.3


@pytest.mark.parametrize("raw, message", [
    ("{not json", "is not valid JSON"),
    ("[1, 2]", "must be a JSON object"),
])
def test_bad_extra_params_fail_naming_the_variable(monkeypatch, raw, message):
    monkeypatch.setenv("LLM_EXTRA_PARAMS", raw)
    with pytest.raises(ValueError, match=f"LLM_EXTRA_PARAMS {message}"):
        llm_config_from_env()


def test_extra_params_reach_the_langchain_model(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("MODEL_NAME", "gpt-x")
    monkeypatch.setenv("LLM_API_KEY", "x")
    monkeypatch.setenv("LLM_EXTRA_PARAMS", '{"max_tokens": 1234, "reasoning_effort": "low"}')
    llm = create_llm(llm_config_from_env())
    payload = llm._get_request_payload([("user", "hi")])
    assert 1234 in (payload.get("max_tokens"), payload.get("max_completion_tokens"))
    assert payload["reasoning_effort"] == "low"
    assert "temperature" not in payload


# ── Builder → ephemeral ──────────────────────────────────────────────

def _builder_steps():
    """Load the Builder's steps.py with a stand-in `app` module (its
    decorators register steps on the real agent)."""
    class _Agent:
        def step(self, *a, **k):
            return lambda fn: fn
    sys.modules["app"] = types.SimpleNamespace(agent=_Agent())
    path = Path(__file__).resolve().parents[1] / "packages/abi-agents/src/abi_agents/builder/agent/steps.py"
    spec = importlib.util.spec_from_file_location("builder_steps_under_test", path)
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    finally:
        sys.modules.pop("app", None)
    return module


def test_ephemeral_params_from_ephemeral_var(monkeypatch):
    steps = _builder_steps()
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    monkeypatch.setenv("LLM_EXTRA_PARAMS", '{"num_ctx": 4096}')
    monkeypatch.setenv("EPHEMERAL_LLM_EXTRA_PARAMS", '{"thinking_level": "low"}')
    env = steps._ephemeral_llm_params_env("gemini", {})
    assert json.loads(env["LLM_EXTRA_PARAMS"]) == {"thinking_level": "low"}
    assert "LLM_TEMPERATURE" not in env


def test_builder_params_fall_back_only_on_same_provider(monkeypatch):
    steps = _builder_steps()
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    monkeypatch.setenv("LLM_EXTRA_PARAMS", '{"num_ctx": 4096}')
    assert json.loads(steps._ephemeral_llm_params_env("ollama", {})["LLM_EXTRA_PARAMS"]) == {"num_ctx": 4096}
    assert steps._ephemeral_llm_params_env("gemini", {}) == {}


def test_task_override_wins_and_sets_temperature(monkeypatch):
    steps = _builder_steps()
    monkeypatch.setenv("EPHEMERAL_LLM_EXTRA_PARAMS", '{"thinking_level": "low", "max_tokens": 100}')
    env = steps._ephemeral_llm_params_env(
        "gemini", {"model": "m", "extra_params": {"thinking_level": "high"}, "temperature": 0.2})
    assert json.loads(env["LLM_EXTRA_PARAMS"]) == {"thinking_level": "high", "max_tokens": 100}
    assert env["LLM_TEMPERATURE"] == "0.2"


def test_bad_ephemeral_params_fail(monkeypatch):
    steps = _builder_steps()
    monkeypatch.setenv("EPHEMERAL_LLM_EXTRA_PARAMS", "nope")
    with pytest.raises(ValueError, match="EPHEMERAL_LLM_EXTRA_PARAMS is not valid JSON"):
        steps._ephemeral_llm_params_env("gemini", {})


def test_parse_extra_params_empty():
    assert parse_extra_params(None) == {} and parse_extra_params("  ") == {}
