"""${VAR} in a card's auth: the HMAC secret and key id from the environment.

Signing (agent_auth, ServiceCard) and verifying (SemanticAccessValidator)
both read the card from disk, so both must resolve the same value. A
reference with no value and no default in `auth` raises CardEnvError; in
`url` it stays as written.

Spec: .abi/specs/not-implemented/card-auth-env-expansion.md
"""

import asyncio
import json

import pytest

from abi_core.common.agent_card_loader import CardEnvError, resolve_card_env
from abi_core.common.service_card import ServiceCard
from abi_core.security.agent_auth import build_semantic_context_from_card
from abi_core.semantic.semantic_access_validator import SemanticAccessValidator


def _card(secret, key_id="agent://orders-default", url="http://orders:8000"):
    return {"id": "agent://orders", "name": "orders", "url": url,
            "auth": {"method": "hmac_sha256", "key_id": key_id, "shared_secret": secret}}


# ── resolve_card_env ────────────────────────────────────────────────

def test_secret_from_environment(monkeypatch):
    monkeypatch.setenv("ORDERS_SECRET", "s3cret")
    assert resolve_card_env(_card("${ORDERS_SECRET}"))["auth"]["shared_secret"] == "s3cret"


def test_secret_default_when_unset(monkeypatch):
    monkeypatch.delenv("ORDERS_SECRET", raising=False)
    card = resolve_card_env(_card("${ORDERS_SECRET:-replace-me}"))
    assert card["auth"]["shared_secret"] == "replace-me"


def test_empty_variable_counts_as_unset(monkeypatch):
    monkeypatch.setenv("ORDERS_SECRET", "")
    assert resolve_card_env(_card("${ORDERS_SECRET:-fallback}"))["auth"]["shared_secret"] == "fallback"
    with pytest.raises(CardEnvError):
        resolve_card_env(_card("${ORDERS_SECRET}"))


def test_missing_secret_raises_naming_the_variable(monkeypatch):
    monkeypatch.delenv("ORDERS_SECRET", raising=False)
    with pytest.raises(CardEnvError, match=r"agent://orders: auth.shared_secret .*\$\{ORDERS_SECRET\}"):
        resolve_card_env(_card("${ORDERS_SECRET}"))


def test_key_id_from_environment(monkeypatch):
    monkeypatch.setenv("ORDERS_KEY", "agent://orders-prod")
    card = resolve_card_env(_card("plain", key_id="${ORDERS_KEY}"))
    assert card["auth"]["key_id"] == "agent://orders-prod"
    monkeypatch.delenv("ORDERS_KEY")
    with pytest.raises(CardEnvError, match="auth.key_id"):
        resolve_card_env(_card("plain", key_id="${ORDERS_KEY}"))


def test_url_keeps_lenient_behaviour(monkeypatch):
    monkeypatch.delenv("ORDERS_URL", raising=False)
    card = resolve_card_env(_card("plain", url="${ORDERS_URL}"))
    assert card["url"] == "${ORDERS_URL}"


def test_original_card_is_not_modified(monkeypatch):
    monkeypatch.setenv("ORDERS_SECRET", "s3cret")
    original = _card("${ORDERS_SECRET}")
    resolve_card_env(original)
    assert original["auth"]["shared_secret"] == "${ORDERS_SECRET}"


def test_include_auth_false_resolves_only_the_url(monkeypatch):
    """What the semantic layer indexes into Weaviate: url resolved, the
    secret kept as a reference, and no error for a variable it lacks."""
    monkeypatch.setenv("ORDERS_URL", "http://orders.run.app")
    monkeypatch.delenv("ORDERS_SECRET", raising=False)
    card = resolve_card_env(_card("${ORDERS_SECRET}", url="${ORDERS_URL}"), include_auth=False)
    assert card["url"] == "http://orders.run.app"
    assert card["auth"]["shared_secret"] == "${ORDERS_SECRET}"


def test_literal_secret_untouched():
    assert resolve_card_env(_card("literal"))["auth"]["shared_secret"] == "literal"


# ── sign and verify end to end ──────────────────────────────────────

def _write(path, card):
    path.write_text(json.dumps(card))
    return path


def _validator(cards_dir):
    return SemanticAccessValidator(agent_cards_dir=cards_dir)


def _verify(validator, card_id, ctx):
    card = asyncio.run(validator._load_agent_card(card_id))
    return card is not None and validator._verify_signature(card, ctx)


def test_agent_signs_and_layer_verifies_with_env_secret(tmp_path, monkeypatch):
    monkeypatch.setenv("ORDERS_SECRET", "s3cret")
    cards = tmp_path / "agent_cards"
    cards.mkdir()
    path = _write(cards / "orders.json", _card("${ORDERS_SECRET}"))

    ctx = build_semantic_context_from_card(str(path), "find_agent", "planner")
    assert _verify(_validator(cards), "agent://orders", ctx)


def test_layer_with_a_different_secret_rejects(tmp_path, monkeypatch):
    monkeypatch.setenv("ORDERS_SECRET", "s3cret")
    cards = tmp_path / "agent_cards"
    cards.mkdir()
    path = _write(cards / "orders.json", _card("${ORDERS_SECRET}"))
    ctx = build_semantic_context_from_card(str(path), "find_agent", "planner")

    monkeypatch.setenv("ORDERS_SECRET", "other")
    assert not _verify(_validator(cards), "agent://orders", ctx)


def test_signature_with_the_literal_reference_is_rejected(tmp_path, monkeypatch):
    """Someone who reads the card must not be able to sign with "${...}"."""
    monkeypatch.setenv("ORDERS_SECRET", "s3cret")
    cards = tmp_path / "agent_cards"
    cards.mkdir()
    _write(cards / "orders.json", _card("${ORDERS_SECRET}"))
    forged_path = _write(tmp_path / "forged.json", _card("${ORDERS_SECRET}"))
    monkeypatch.setenv("ORDERS_SECRET", "${ORDERS_SECRET}")  # forger signs with the literal
    ctx = build_semantic_context_from_card(str(forged_path), "find_agent", "planner")

    monkeypatch.setenv("ORDERS_SECRET", "s3cret")
    assert not _verify(_validator(cards), "agent://orders", ctx)


def test_broken_card_of_another_agent_does_not_break_validation(tmp_path, monkeypatch):
    monkeypatch.setenv("ORDERS_SECRET", "s3cret")
    monkeypatch.delenv("BILLING_SECRET", raising=False)
    cards = tmp_path / "agent_cards"
    cards.mkdir()
    billing = _card("${BILLING_SECRET}")
    billing.update(id="agent://billing", name="billing")
    _write(cards / "a_billing.json", billing)
    path = _write(cards / "orders.json", _card("${ORDERS_SECRET}"))

    validator = _validator(cards)
    ctx = build_semantic_context_from_card(str(path), "find_agent", "planner")
    assert _verify(validator, "agent://orders", ctx)
    assert asyncio.run(validator._load_agent_card("agent://billing")) is None


def test_service_card_signs_with_env_secret(tmp_path, monkeypatch):
    monkeypatch.setenv("WEB_SECRET", "w3b")
    cards = tmp_path / "agent_cards"
    cards.mkdir()
    services = tmp_path / "service_cards"
    services.mkdir()
    card = {"service_id": "service://webapp", "name": "webapp",
            "auth": {"method": "hmac_sha256", "key_id": "service://webapp-default",
                     "shared_secret": "${WEB_SECRET}"}}
    path = _write(services / "webapp.json", card)

    service = ServiceCard.from_file(str(path))
    assert service.auth["shared_secret"] == "w3b"
    ctx = service.build_context(tool_name="find_agent", query="planner")
    assert _verify(_validator(cards), "service://webapp", ctx)


def test_agent_fails_at_start_without_its_secret(tmp_path, monkeypatch):
    """The agent loads its card with load_agent_card at start-up."""
    from abi_core.common.agent_card_loader import load_agent_card

    monkeypatch.delenv("ORDERS_SECRET", raising=False)
    path = _write(tmp_path / "orders.json", _card("${ORDERS_SECRET}"))
    with pytest.raises(CardEnvError, match="ORDERS_SECRET"):
        load_agent_card(str(path))
