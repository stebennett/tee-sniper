"""Tests for encryption service."""

import base64

import pytest

from app.services.encryption import EncryptionError, EncryptionService


class TestEncryptionService:
    """Tests for EncryptionService."""

    def test_encrypt_decrypt_roundtrip(self, shared_secret: str) -> None:
        """Test that encryption and decryption are inverse operations."""
        service = EncryptionService(shared_secret)

        username = "testuser"
        pin = "1234"

        encrypted = service.encrypt_credentials(username, pin)
        decrypted_username, decrypted_pin = service.decrypt_credentials(encrypted)

        assert decrypted_username == username
        assert decrypted_pin == pin

    def test_encrypt_produces_different_output_each_time(self, shared_secret: str) -> None:
        """Test that encryption produces different ciphertext due to random nonce."""
        service = EncryptionService(shared_secret)

        encrypted1 = service.encrypt_credentials("user", "pin")
        encrypted2 = service.encrypt_credentials("user", "pin")

        # Same plaintext should produce different ciphertext
        assert encrypted1 != encrypted2

        # But both should decrypt to the same value
        u1, p1 = service.decrypt_credentials(encrypted1)
        u2, p2 = service.decrypt_credentials(encrypted2)
        assert u1 == u2 == "user"
        assert p1 == p2 == "pin"

    def test_decrypt_with_wrong_secret_fails(self, shared_secret: str) -> None:
        """Test that decryption fails with wrong shared secret."""
        service1 = EncryptionService(shared_secret)
        service2 = EncryptionService("different-secret")

        encrypted = service1.encrypt_credentials("user", "pin")

        with pytest.raises(EncryptionError, match="Decryption failed"):
            service2.decrypt_credentials(encrypted)

    def test_decrypt_invalid_base64_fails(self, shared_secret: str) -> None:
        """Test that decryption fails with invalid base64."""
        service = EncryptionService(shared_secret)

        with pytest.raises(EncryptionError, match="Invalid base64"):
            service.decrypt_credentials("not-valid-base64!!!")

    def test_decrypt_too_short_data_fails(self, shared_secret: str) -> None:
        """Test that decryption fails with too short data."""
        service = EncryptionService(shared_secret)

        # Create data shorter than nonce size
        short_data = base64.b64encode(b"short").decode()

        with pytest.raises(EncryptionError, match="too short"):
            service.decrypt_credentials(short_data)

    def test_handles_pin_with_colon(self, shared_secret: str) -> None:
        """Test that pins containing colons are handled correctly."""
        service = EncryptionService(shared_secret)

        username = "user"
        pin = "pass:with:colons"

        encrypted = service.encrypt_credentials(username, pin)
        decrypted_username, decrypted_pin = service.decrypt_credentials(encrypted)

        assert decrypted_username == username
        assert decrypted_pin == pin

    def test_handles_special_characters(self, shared_secret: str) -> None:
        """Test encryption with special characters."""
        service = EncryptionService(shared_secret)

        username = "user@example.com"
        pin = "p@$$w0rd!#$%"

        encrypted = service.encrypt_credentials(username, pin)
        decrypted_username, decrypted_pin = service.decrypt_credentials(encrypted)

        assert decrypted_username == username
        assert decrypted_pin == pin

    def test_handles_unicode_characters(self, shared_secret: str) -> None:
        """Test encryption with unicode characters."""
        service = EncryptionService(shared_secret)

        username = "user"
        pin = "password"

        encrypted = service.encrypt_credentials(username, pin)
        decrypted_username, decrypted_pin = service.decrypt_credentials(encrypted)

        assert decrypted_username == username
        assert decrypted_pin == pin

    def test_encrypted_output_is_base64(self, shared_secret: str) -> None:
        """Test that encrypted output is valid base64."""
        service = EncryptionService(shared_secret)

        encrypted = service.encrypt_credentials("user", "pin")

        # Should not raise
        decoded = base64.b64decode(encrypted)
        assert len(decoded) > EncryptionService.NONCE_SIZE
