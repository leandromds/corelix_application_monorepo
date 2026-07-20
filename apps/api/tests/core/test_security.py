"""
Tests for core/security.py — written BEFORE implementation (TDD Red phase).

These tests define the contract for all security utilities.
Run these first — they will all FAIL until security.py is implemented.
"""

from datetime import timedelta

import pytest


class TestPasswordHashing:
    """Tests for password hashing and verification."""

    def test_hash_password_returns_string(self):
        """hash_password should return a non-empty string."""
        from core.security import hash_password
        result = hash_password("my_password")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_hash_is_not_plain_text(self):
        """Hash must never equal the original password."""
        from core.security import hash_password
        password = "super_secret_123"
        assert hash_password(password) != password

    def test_each_hash_is_unique(self):
        """bcrypt uses random salt — same password produces different hashes."""
        from core.security import hash_password
        password = "same_password"
        assert hash_password(password) != hash_password(password)

    def test_verify_correct_password(self):
        """verify_password must return True for matching password/hash."""
        from core.security import hash_password, verify_password
        password = "correct_password"
        hashed = hash_password(password)
        assert verify_password(password, hashed) is True

    def test_verify_wrong_password(self):
        """verify_password must return False — never raise — for wrong password."""
        from core.security import hash_password, verify_password
        hashed = hash_password("correct_password")
        assert verify_password("wrong_password", hashed) is False

    def test_verify_empty_password_is_false(self):
        """Empty string must not match any real password hash."""
        from core.security import hash_password, verify_password
        hashed = hash_password("real_password")
        assert verify_password("", hashed) is False


class TestAccessToken:
    """Tests for JWT access token creation and decoding."""

    def test_create_token_returns_string(self):
        """create_access_token should return a non-empty JWT string."""
        from core.security import create_access_token
        token = create_access_token(subject="some-uuid")
        assert isinstance(token, str)
        assert len(token) > 0

    def test_token_contains_subject(self):
        """Decoded token must contain the subject (professional_id)."""
        from core.security import create_access_token, decode_access_token
        subject = "123e4567-e89b-12d3-a456-426614174000"
        token = create_access_token(subject=subject)
        payload = decode_access_token(token)
        assert payload["sub"] == subject

    def test_token_type_is_access(self):
        """Token type must be access to distinguish from refresh tokens."""
        from core.security import create_access_token, decode_access_token
        token = create_access_token(subject="some-uuid")
        payload = decode_access_token(token)
        assert payload["type"] == "access"

    def test_token_has_expiry(self):
        """Every token must have an expiration claim."""
        from core.security import create_access_token, decode_access_token
        token = create_access_token(subject="some-uuid")
        payload = decode_access_token(token)
        assert "exp" in payload

    def test_custom_expiry_is_respected(self):
        """Custom expiry delta must be used when provided."""
        from core.security import create_access_token, decode_access_token
        token = create_access_token(subject="some-uuid", expires_delta=timedelta(hours=1))
        payload = decode_access_token(token)
        assert payload["sub"] == "some-uuid"

    def test_invalid_token_raises(self):
        """Malformed token must raise JWTError, not return None."""
        from jose import JWTError

        from core.security import decode_access_token
        with pytest.raises(JWTError):
            decode_access_token("not.a.valid.token")

    def test_tampered_token_raises(self):
        """Token with modified payload must fail signature verification."""
        import base64
        import json

        from jose import JWTError

        from core.security import create_access_token, decode_access_token
        token = create_access_token(subject="original-uuid")
        header, payload, signature = token.split(".")
        tampered = base64.urlsafe_b64encode(
            json.dumps({"sub": "attacker-uuid", "type": "access"}).encode()
        ).decode().rstrip("=")
        with pytest.raises(JWTError):
            decode_access_token(f"{header}.{tampered}.{signature}")


class TestRefreshToken:
    """Tests for refresh token hash generation."""

    def test_generate_refresh_token_returns_tuple(self):
        """generate_refresh_token should return (raw_token, hashed_token)."""
        from core.security import generate_refresh_token
        raw, hashed = generate_refresh_token()
        assert isinstance(raw, str)
        assert isinstance(hashed, str)

    def test_raw_and_hash_are_different(self):
        """Raw token must not equal its hash."""
        from core.security import generate_refresh_token
        raw, hashed = generate_refresh_token()
        assert raw != hashed

    def test_each_generated_token_is_unique(self):
        """Each call must produce a different token (uses secrets.token_urlsafe)."""
        from core.security import generate_refresh_token
        raw1, _ = generate_refresh_token()
        raw2, _ = generate_refresh_token()
        assert raw1 != raw2

    def test_hash_refresh_token_is_deterministic(self):
        """Same raw token must always produce the same hash (SHA-256 is deterministic)."""
        from core.security import hash_refresh_token
        raw = "some_raw_token_value"
        assert hash_refresh_token(raw) == hash_refresh_token(raw)
