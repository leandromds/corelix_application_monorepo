"""Tests for Fernet credential encryption/decryption."""

import pytest
from cryptography.fernet import Fernet, InvalidToken

from whatsapp.providers.crypto import decrypt_credentials, encrypt_credentials


class TestCrypto:
    def test_encrypt_returns_bytes(self):
        result = encrypt_credentials("my_secret_token")
        assert isinstance(result, bytes)

    def test_encrypt_does_not_equal_plaintext(self):
        plaintext = "twilio_auth_token_secret"
        cipher = encrypt_credentials(plaintext)
        assert cipher != plaintext.encode()

    def test_encrypt_decrypt_roundtrip(self):
        plaintext = "twilio_auth_token_secret"
        cipher = encrypt_credentials(plaintext)
        recovered = decrypt_credentials(cipher)
        assert recovered == plaintext

    def test_different_encryptions_of_same_text(self):
        """Fernet uses random IV — same plaintext should produce different ciphertexts."""
        cipher1 = encrypt_credentials("secret")
        cipher2 = encrypt_credentials("secret")
        assert cipher1 != cipher2  # different IVs

    def test_decrypt_with_wrong_key_raises(self, monkeypatch):
        """Decrypting with a different key must raise InvalidToken."""
        cipher = encrypt_credentials("secret")
        # Monkeypatch settings to use a different key
        from core.config import settings

        wrong_key = Fernet.generate_key().decode()
        monkeypatch.setattr(settings, "ENCRYPTION_KEY", wrong_key)
        with pytest.raises(InvalidToken):
            decrypt_credentials(cipher)

    def test_decrypt_corrupted_bytes_raises(self):
        with pytest.raises(InvalidToken):
            decrypt_credentials(b"corrupted_bytes_not_valid_fernet")
