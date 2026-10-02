"""Licensing: the signature, the plans, and the four gates.

The whole path is exercised with a throwaway key pair, so these tests prove that
issuing, verifying, and gating actually work rather than that they are wired up.
"""

from __future__ import annotations

import binascii
import secrets
import time

import pytest

from edify.errors import TierRequired
from edify.licensing import ed25519, tier
from edify.licensing import token as token_mod
from edify.licensing.token import issue, parse


@pytest.fixture
def keypair(monkeypatch: pytest.MonkeyPatch) -> bytes:
    seed = secrets.token_bytes(32)
    public = ed25519.public_key(seed)
    monkeypatch.setenv("EDIFY_LICENSE_PUBKEY", binascii.hexlify(public).decode())
    return seed


def test_sign_and_verify_round_trip() -> None:
    seed = secrets.token_bytes(32)
    public = ed25519.public_key(seed)
    message = b"the graph is never written by a model"
    signature = ed25519.sign(message, seed)
    assert ed25519.verify(message, signature, public)
    assert not ed25519.verify(message + b"!", signature, public)


def test_a_signature_from_another_key_is_rejected() -> None:
    good, bad = secrets.token_bytes(32), secrets.token_bytes(32)
    message = b"payload"
    assert not ed25519.verify(message, ed25519.sign(message, bad), ed25519.public_key(good))


def test_rfc8032_test_vector() -> None:
    """Vector 1 from RFC 8032 §7.1 — proof this is Ed25519 and not something near it."""
    seed = binascii.unhexlify(
        "9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60"
    )
    expected_public = "d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a"
    assert binascii.hexlify(ed25519.public_key(seed)).decode() == expected_public

    signature = ed25519.sign(b"", seed)
    assert binascii.hexlify(signature).decode() == (
        "e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e065224901555fb8821590a33bacc6"
        "1e39701cf9b46bd25bf5f0595bbe24655141438e7a100b"
    )


def test_a_valid_team_token_carries_its_entitlements(keypair: bytes) -> None:
    token = issue(
        {"sub": "acct_1", "email": "dev@example.com", "plan": "team", "seats": 1,
         "iat": int(time.time()), "exp": int(time.time()) + 86400},
        keypair,
    )
    verdict = parse(token)
    assert verdict.valid
    assert verdict.license.plan == "team"

    tier.save(token)
    ent = tier.current()
    assert ent.plan == "team"
    assert ent.allows("mcp.multi")
    assert ent.mcp_cap is None
    assert ent.node_cap is None


def test_an_expired_token_falls_back_to_free_and_says_why(keypair: bytes) -> None:
    token = issue(
        {"sub": "acct_1", "plan": "team", "iat": 0, "exp": int(time.time()) - 10}, keypair
    )
    tier.save(token)
    ent = tier.current()
    assert ent.plan == "free"
    assert "expired" in ent.problem


def test_a_tampered_token_falls_back_to_free(keypair: bytes) -> None:
    token = issue({"sub": "acct_1", "plan": "team", "iat": 0, "exp": 0}, keypair)
    head, payload, signature = token.split(".")
    forged = f"{head}.{payload[:-2]}AA.{signature}"

    tier.save(forged)
    ent = tier.current()
    assert ent.plan == "free"
    assert ent.problem


def test_no_licence_is_the_free_plan_with_working_limits() -> None:
    ent = tier.current()
    assert ent.plan == "free"
    assert ent.node_cap is None
    assert ent.mcp_cap == tier.FREE_MCP_ENTRIES

    with pytest.raises(TierRequired):
        ent.require("mcp.multi")


def test_the_environment_variable_carries_a_licence_for_ci(
    keypair: bytes, monkeypatch: pytest.MonkeyPatch
) -> None:
    token = issue({"sub": "ci", "plan": "team", "seats": 20, "iat": 0, "exp": 0}, keypair)
    monkeypatch.setenv("EDIFY_LICENSE", token)
    ent = tier.current()
    assert ent.plan == "team"
    assert ent.allows("team")
    assert ent.source == "EDIFY_LICENSE"


def test_an_extra_feature_on_a_token_only_adds(keypair: bytes) -> None:
    token = issue(
        {"sub": "x", "plan": "free", "iat": 0, "exp": 0, "features": ["mcp.multi"]},
        keypair,
    )
    tier.save(token)
    ent = tier.current()
    assert ent.plan == "free"
    assert ent.allows("mcp.multi")
    assert not ent.allows("team")


# -- M1 · the shipped issuing key -------------------------------------------
# 0.1.0 shipped `DEFAULT_PUBLIC_KEY_HEX` as the public key of an all-zeros seed,
# which meant anyone could mint a `pro` token with 32 zero bytes. These two tests
# fail if that key — or any key derivable from a trivially-guessable seed — ever
# comes back, whether by a revert, a bad merge, or a placeholder left in.


def _trivial_seeds() -> list[bytes]:
    """Seeds a person would reach for without thinking: all-zeros, all-ones, a
    single repeated byte, and the low counting integers rendered big-endian."""
    seeds = [bytes([b]) * 32 for b in range(256)]
    seeds += [n.to_bytes(32, "big") for n in range(1, 64)]
    return seeds


def test_the_shipped_key_is_not_derivable_from_a_trivial_seed() -> None:
    shipped = binascii.unhexlify(token_mod.DEFAULT_PUBLIC_KEY_HEX)
    assert len(shipped) == 32
    for seed in _trivial_seeds():
        assert ed25519.public_key(seed) != shipped, (
            "the shipped issuing key is derivable from a guessable seed — anyone can "
            "mint a licence. Run the issuer's keygen and commit only the public half."
        )


def test_the_zero_seed_key_that_shipped_in_0_1_0_is_gone() -> None:
    weak = "3b6a27bcceb6a42d62a3a8d02a6f0d73653215771de243a63ac048a18b59da29"
    assert token_mod.DEFAULT_PUBLIC_KEY_HEX != weak
    assert binascii.hexlify(ed25519.public_key(bytes(32))).decode() == weak


def test_a_token_signed_with_the_zero_seed_no_longer_verifies(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Nothing minted against the old key survives, which is the point of M1."""
    monkeypatch.delenv("EDIFY_LICENSE_PUBKEY", raising=False)
    forged = issue({"sub": "anyone", "plan": "pro", "iat": 0, "exp": 0}, bytes(32))
    verdict = parse(forged)
    assert not verdict.valid
    assert "signature" in verdict.reason
