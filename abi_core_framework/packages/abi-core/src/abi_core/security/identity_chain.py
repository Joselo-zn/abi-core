# abi_core/security/identity_chain.py
"""
Identity chain — HMAC-sealed chain of ids, verified hop by hop.

See .abi/specs/not-implemented/identity-chain-hmac-contract.md for the full
design. Scope of THIS implementation: the chatui <-> orchestrator hop only —
other hops (orchestrator<->planner, orchestrator<->builder, etc.) are not
implemented yet, see that spec's "Alcance de implementación".

Root cause this replaces: session continuity depended on a random opaque
token that had to be minted, cached client-side, and optionally bridged back
to persisted thread metadata — any break in that chain (a missing write, a
second browser tab with its own independent token) produced an orphaned
session with no way to tell where it broke. `derive_session_id` instead
computes the session id as a pure function of (user_id, thread_id) — nothing
to cache, nothing to lose, and two tabs for the same user+thread
deterministically land on the same session.
"""

import hashlib
import hmac as _hmac
from typing import Optional


def _seal(secret: str, previous_checksum: str, id_value: str) -> str:
    """One HMAC-SHA256 link: HMAC(secret, previous_checksum + id_value)."""
    message = (previous_checksum + id_value).encode()
    return _hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()


def build_chain(secret: str, ordered_ids: list[tuple[str, str]]) -> list[dict]:
    """Build a chain of links, each sealed against the previous link's
    checksum.

    `ordered_ids` is a list of (id_type, id_value) pairs, in the order they
    belong in the chain — e.g. [("user_id", ...), ("thread_id", ...)].
    """
    chain = []
    previous_checksum = ""
    for id_type, id_value in ordered_ids:
        checksum = _seal(secret, previous_checksum, id_value)
        chain.append({"id_type": id_type, "id_value": id_value, "checksum": checksum})
        previous_checksum = checksum
    return chain


def verify_chain(secret: str, chain: list[dict]) -> bool:
    """Recompute every link's checksum and compare (constant-time per link).

    Valid for a chain sealed entirely by ONE secret — today's only real case,
    since the chatui->orchestrator hop is the only one implemented and it
    produces the whole chain in one place. A future multi-hop chain, where
    different links are sealed by different hop secrets, needs a caller that
    only re-verifies the links it has the secret for, not a full
    re-verification from the root — see the spec's "Trazabilidad" section.
    """
    if not chain:
        return False
    previous_checksum = ""
    for link in chain:
        id_value = link.get("id_value")
        checksum = link.get("checksum")
        if id_value is None or checksum is None:
            return False
        expected = _seal(secret, previous_checksum, id_value)
        if not _hmac.compare_digest(expected, checksum):
            return False
        previous_checksum = checksum
    return True


def get_id(chain: list[dict], id_type: str) -> Optional[str]:
    """Look up a specific id's value from a chain by its id_type."""
    for link in chain:
        if link.get("id_type") == id_type:
            return link.get("id_value")
    return None


def derive_session_id(*parts: str) -> str:
    """Deterministic, stable session_id from identity parts (e.g. user_id +
    thread_id) — replaces the random context_id minted per token today.

    Not secret-keyed on purpose: this only needs to be deterministic and
    collision-resistant, not tamper-proof — the chain's own HMAC already
    proves the parts themselves are authentic before this ever runs.
    """
    return hashlib.sha256(":".join(parts).encode()).hexdigest()
