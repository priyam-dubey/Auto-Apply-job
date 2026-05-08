"""
utils/security.py

Secure storage helpers for session cookies / credentials.
Uses Fernet symmetric encryption with a key derived from SECRET_KEY env var.
"""

from __future__ import annotations

import base64
import hashlib
import os


def _get_fernet():
    """Lazily import and build a Fernet cipher from SECRET_KEY."""
    try:
        from cryptography.fernet import Fernet

        secret = os.environ.get("SECRET_KEY", "default-insecure-key-change-me")
        # Derive a 32-byte key from the secret
        key_bytes = hashlib.sha256(secret.encode()).digest()
        fernet_key = base64.urlsafe_b64encode(key_bytes)
        return Fernet(fernet_key)
    except ImportError:
        return None


def encrypt_cookies(raw: str) -> str:
    """
    Encrypt a cookie string.  Returns base64 ciphertext or the raw string
    if the cryptography library isn't installed.
    """
    if not raw:
        return ""
    fernet = _get_fernet()
    if fernet is None:
        return raw  # graceful degradation
    try:
        return fernet.encrypt(raw.encode()).decode()
    except Exception:
        return raw


def decrypt_cookies(encrypted: str) -> str:
    """
    Decrypt a cookie string produced by encrypt_cookies().
    Returns plaintext, or the original string if decryption fails.
    """
    if not encrypted:
        return ""
    fernet = _get_fernet()
    if fernet is None:
        return encrypted
    try:
        return fernet.decrypt(encrypted.encode()).decode()
    except Exception:
        return encrypted  # already plaintext or invalid — pass through


def mask_cookies(cookie_str: str, keep_chars: int = 4) -> str:
    """Return a masked version safe for logging (shows only last N chars)."""
    if not cookie_str:
        return ""
    return "*" * max(0, len(cookie_str) - keep_chars) + cookie_str[-keep_chars:]
