"""Message encryption utilities using Fernet (AES-128-CBC + HMAC)."""
import os
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken


def _get_cipher() -> Optional[Fernet]:
    key = os.getenv("MESSAGE_ENCRYPTION_KEY")
    if not key:
        return None
    return Fernet(key.encode() if isinstance(key, str) else key)


def encrypt_message(plaintext: str) -> str:
    cipher = _get_cipher()
    if not cipher:
        return plaintext
    return cipher.encrypt(plaintext.encode()).decode()


def decrypt_message(ciphertext: str) -> str:
    cipher = _get_cipher()
    if not cipher:
        return ciphertext
    try:
        return cipher.decrypt(ciphertext.encode()).decode()
    except InvalidToken:
        # Stored before MESSAGE_ENCRYPTION_KEY was set, so it's plain text.
        return ciphertext
