"""
crypto_utils.py
----------------
All cryptography for SecureVault lives here.

Design:
- Master password -> scrypt (memory-hard KDF) -> 256-bit key -> Fernet (AES-128-CBC + HMAC).
- A random salt is generated once and stored UNENCRYPTED next to the vault.
  The salt is not a secret; it just prevents rainbow-table attacks and makes
  every user's key derivation unique even with the same password.
- The master password itself is NEVER stored anywhere. If you forget it,
  the vault cannot be recovered. That is by design (there's no back door).
"""

import os
import json
import base64
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

SALT_SIZE = 16  # bytes


def generate_salt() -> bytes:
    return os.urandom(SALT_SIZE)


def derive_key(password: str, salt: bytes) -> bytes:
    """Derive a 32-byte key from the master password using scrypt, then
    base64-encode it so it can be used directly as a Fernet key."""
    kdf = Scrypt(salt=salt, length=32, n=2 ** 14, r=8, p=1)
    raw_key = kdf.derive(password.encode("utf-8"))
    return base64.urlsafe_b64encode(raw_key)


def encrypt_data(data: dict, key: bytes) -> bytes:
    f = Fernet(key)
    plaintext = json.dumps(data).encode("utf-8")
    return f.encrypt(plaintext)


def decrypt_data(token: bytes, key: bytes) -> dict:
    """Raises cryptography.fernet.InvalidToken if the password/key is wrong
    or the file has been tampered with."""
    f = Fernet(key)
    plaintext = f.decrypt(token)
    return json.loads(plaintext.decode("utf-8"))


class WrongPassword(Exception):
    pass


def try_decrypt(token: bytes, key: bytes) -> dict:
    try:
        return decrypt_data(token, key)
    except InvalidToken:
        raise WrongPassword("Incorrect master password or corrupted vault.")
