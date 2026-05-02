"""
Encryption utilities — AES-256-GCM for medical record data.
"""

import json
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.config import settings

# 32-byte key derived from hex string in environment
_ENCRYPTION_KEY = bytes.fromhex(settings.encryption_key)


def encrypt_data(data: dict) -> tuple[bytes, bytes]:
    """
    Encrypt a dictionary using AES-256-GCM.

    Args:
        data: Dictionary to encrypt (will be JSON-serialized).

    Returns:
        Tuple of (encrypted_data, iv).
        The encrypted_data includes the 16-byte auth_tag appended by AESGCM.
    """
    aesgcm = AESGCM(_ENCRYPTION_KEY)
    iv = os.urandom(12)  # 96 bits, recommended for GCM
    plaintext = json.dumps(data, ensure_ascii=False).encode("utf-8")
    ciphertext = aesgcm.encrypt(iv, plaintext, None)  # ciphertext + auth_tag
    return ciphertext, iv


def decrypt_data(encrypted_data: bytes, iv: bytes) -> dict:
    """
    Decrypt AES-256-GCM encrypted data.

    Args:
        encrypted_data: Ciphertext with appended auth_tag.
        iv: Initialization vector used during encryption.

    Returns:
        Decrypted dictionary.

    Raises:
        cryptography.exceptions.InvalidTag: If data has been tampered with.
    """
    aesgcm = AESGCM(_ENCRYPTION_KEY)
    plaintext = aesgcm.decrypt(iv, encrypted_data, None)
    return json.loads(plaintext.decode("utf-8"))
