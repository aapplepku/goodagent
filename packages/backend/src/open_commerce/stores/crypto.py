"""Authenticated encryption for transient identity and import state."""

import base64
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from open_commerce.config import Settings
from open_commerce.stores.models import StoreError


def encryption_key(settings: Settings) -> bytes:
    if settings.encryption_key is None:
        raise StoreError("Configure the instance encryption key before connecting data.", 503)
    try:
        key = base64.urlsafe_b64decode(settings.encryption_key.get_secret_value())
    except ValueError as exc:
        raise StoreError("The instance encryption key is invalid.", 503) from exc
    if len(key) != 32:
        raise StoreError("The instance encryption key must contain 32 random bytes.", 503)
    return key


def encrypt(settings: Settings, data: bytes, *, context: str) -> bytes:
    nonce = os.urandom(12)
    return nonce + AESGCM(encryption_key(settings)).encrypt(nonce, data, context.encode())


def decrypt(settings: Settings, data: bytes, *, context: str) -> bytes:
    return AESGCM(encryption_key(settings)).decrypt(data[:12], data[12:], context.encode())
