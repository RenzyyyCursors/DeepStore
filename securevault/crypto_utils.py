"""
crypto_utils.py
----------------
All cryptography for DeepStore / SecureVault lives here.

Design:
- Master password -> scrypt (memory-hard KDF, n=2**16, r=8, p=1) -> 256-bit key -> Fernet (AES-128-CBC + HMAC).
- A random salt is generated once and stored next to the vault.
- The master password itself is NEVER stored anywhere.
- Backward compatibility with vaults derived with earlier n parameters.
"""

import os
import json
import base64
import re
from typing import Tuple, Optional
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

SALT_SIZE = 32  # 256-bit salt for maximum entropy


def generate_salt() -> bytes:
    """Generate a cryptographically secure random salt."""
    return os.urandom(SALT_SIZE)


def derive_key(password: str, salt: bytes, cost_n: int = 2 ** 16) -> bytes:
    """Derive a 32-byte key from the master password using scrypt, then
    base64-encode it so it can be used directly as a Fernet key."""
    kdf = Scrypt(salt=salt, length=32, n=cost_n, r=8, p=1)
    raw_key = kdf.derive(password.encode("utf-8"))
    return base64.urlsafe_b64encode(raw_key)


def encrypt_data(data: dict, key: bytes) -> bytes:
    """Encrypt dictionary data to Fernet token."""
    f = Fernet(key)
    plaintext = json.dumps(data, ensure_ascii=False).encode("utf-8")
    return f.encrypt(plaintext)


def decrypt_data(token: bytes, key: bytes) -> dict:
    """Raises cryptography.fernet.InvalidToken if the password/key is wrong
    or the file has been tampered with."""
    f = Fernet(key)
    plaintext = f.decrypt(token)
    return json.loads(plaintext.decode("utf-8"))


class WrongPassword(Exception):
    pass


class CorruptedVault(Exception):
    pass


def try_decrypt(token: bytes, key: bytes) -> dict:
    """Attempt decryption, providing clear error types."""
    try:
        return decrypt_data(token, key)
    except InvalidToken:
        raise WrongPassword("Incorrect master passkey or corrupted vault.")
    except Exception as e:
        raise CorruptedVault(f"Failed to decode vault data: {str(e)}")


def try_derive_and_decrypt(token: bytes, password: str, salt: bytes) -> Tuple[bytes, dict]:
    """Tries primary scrypt parameters (2**16), falling back to legacy (2**14) for backward compatibility."""
    for cost in (2 ** 16, 2 ** 14):
        try:
            key = derive_key(password, salt, cost_n=cost)
            data = decrypt_data(token, key)
            return key, data
        except InvalidToken:
            continue
    raise WrongPassword("Incorrect master passkey or invalid salt.")


def check_password_strength(password: str) -> Tuple[int, str]:
    """Evaluates password strength. Returns score (0-4) and a descriptive text."""
    if not password:
        return 0, "Empty"
    
    score = 0
    if len(password) >= 8:
        score += 1
    if len(password) >= 12:
        score += 1
    if re.search(r"[a-z]", password) and re.search(r"[A-Z]", password):
        score += 1
    if re.search(r"\d", password) and re.search(r"[!@#$%^&*()_\-+=\[\]{}|;:,.<>?/~`]", password):
        score += 1

    labels = {
        0: "Too Weak",
        1: "Weak",
        2: "Fair",
        3: "Good",
        4: "Strong"
    }
    return score, labels.get(score, "Fair")
