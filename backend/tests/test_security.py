from datetime import timedelta

import pytest

from app.core.security import (
    create_access_token,
    decode_access_token,
    generate_refresh_token,
    hash_password,
    hash_token,
    verify_password,
)


def test_hash_and_verify_password():
    plain = "secret123"
    hashed = hash_password(plain)
    assert hashed != plain
    assert verify_password(plain, hashed)


def test_verify_wrong_password_fails():
    hashed = hash_password("correct")
    assert not verify_password("wrong", hashed)


def test_create_and_decode_access_token():
    data = {"sub": "user-123"}
    token = create_access_token(data, expires_delta=timedelta(minutes=5))
    payload = decode_access_token(token)
    assert payload is not None
    assert payload["sub"] == "user-123"


def test_expired_token_returns_none():
    data = {"sub": "user-123"}
    token = create_access_token(data, expires_delta=timedelta(seconds=-1))
    assert decode_access_token(token) is None


def test_invalid_token_returns_none():
    assert decode_access_token("not.a.valid.token") is None


def test_generate_refresh_token_is_unique():
    t1 = generate_refresh_token()
    t2 = generate_refresh_token()
    assert t1 != t2
    assert len(t1) > 32


def test_hash_token_is_deterministic():
    token = "my-refresh-token"
    assert hash_token(token) == hash_token(token)
    assert len(hash_token(token)) == 64  # SHA256 hex 固定 64 字符
