"""Encryption service for secure credential handling."""

import base64
import hashlib
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


class EncryptionError(Exception):
    """Raised when encryption or decryption fails."""

    pass


class EncryptionService:
    """Service for encrypting and decrypting credentials using AES-256-GCM."""

    NONCE_SIZE = 12  # 96 bits as recommended for GCM

    def __init__(self, shared_secret: str):
        """Initialize encryption service with a shared secret.

        Args:
            shared_secret: The shared secret used to derive the encryption key.
        """
        # Derive 256-bit key from shared secret using SHA-256
        self.key = hashlib.sha256(shared_secret.encode()).digest()
        self.aesgcm = AESGCM(self.key)

    def encrypt_credentials(self, username: str, pin: str) -> str:
        """Encrypt username and pin into a single encrypted string.

        Args:
            username: The user's username/member ID.
            pin: The user's PIN/password.

        Returns:
            Base64-encoded encrypted string containing nonce + ciphertext.
        """
        plaintext = f"{username}:{pin}".encode()

        # Generate random nonce
        nonce = os.urandom(self.NONCE_SIZE)

        # Encrypt with AES-256-GCM
        ciphertext = self.aesgcm.encrypt(nonce, plaintext, None)

        # Prepend nonce to ciphertext and base64 encode
        return base64.b64encode(nonce + ciphertext).decode()

    def decrypt_credentials(self, encrypted_data: str) -> tuple[str, str]:
        """Decrypt encrypted credentials into username and pin.

        Args:
            encrypted_data: Base64-encoded string containing nonce + ciphertext.

        Returns:
            Tuple of (username, pin).

        Raises:
            EncryptionError: If decryption fails or data format is invalid.
        """
        try:
            # Decode base64
            raw = base64.b64decode(encrypted_data)

            if len(raw) < self.NONCE_SIZE + 1:
                raise EncryptionError("Invalid encrypted data: too short")

            # Extract nonce and ciphertext
            nonce = raw[: self.NONCE_SIZE]
            ciphertext = raw[self.NONCE_SIZE :]

            # Decrypt
            plaintext = self.aesgcm.decrypt(nonce, ciphertext, None)

            # Parse username:pin format
            decoded = plaintext.decode()
            if ":" not in decoded:
                raise EncryptionError("Invalid credential format: missing separator")

            username, pin = decoded.split(":", 1)
            return username, pin

        except base64.binascii.Error as e:
            raise EncryptionError(f"Invalid base64 encoding: {e}") from e
        except Exception as e:
            if isinstance(e, EncryptionError):
                raise
            raise EncryptionError(f"Decryption failed: {e}") from e
