"""Message encryption utilities using Fernet (AES-128-CBC + HMAC).

Fails closed. An absent or malformed ``MESSAGE_ENCRYPTION_KEY`` raises instead
of silently passing plaintext through, because the previous fallback meant a
deployment that simply forgot to set the key would store every buyer/seller
message in cleartext and report success.

Operational note: any message rows written while the key was missing are
plaintext and will not decrypt once a key is configured. Backfill them before
enabling, or accept the loss. See docs/security.md.
"""
import os

from cryptography.fernet import Fernet, InvalidToken

_MISSING_KEY_ERROR = (
    "MESSAGE_ENCRYPTION_KEY is not set. Message encryption is mandatory; "
    "generate one with `python -c \"from cryptography.fernet import Fernet; "
    "print(Fernet.generate_key().decode())\"` and set it in the environment."
)


def _get_cipher() -> Fernet:
    key = os.getenv("MESSAGE_ENCRYPTION_KEY")
    if not key:
        raise RuntimeError(_MISSING_KEY_ERROR)
    try:
        return Fernet(key.encode() if isinstance(key, str) else key)
    except (ValueError, TypeError) as exc:
        raise RuntimeError(
            "MESSAGE_ENCRYPTION_KEY is not a valid Fernet key. "
            "It must be 32 url-safe base64-encoded bytes."
        ) from exc


def encrypt_message(plaintext: str) -> str:
    return _get_cipher().encrypt(plaintext.encode()).decode()


def decrypt_message(ciphertext: str) -> str:
    try:
        return _get_cipher().decrypt(ciphertext.encode()).decode()
    except InvalidToken as exc:
        raise ValueError(
            "Message could not be decrypted. The row is either plaintext from "
            "a deployment with no encryption key, or was written under a "
            "different key."
        ) from exc
