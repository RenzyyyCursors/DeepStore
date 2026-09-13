"""
storage.py
----------
Handles where the vault lives on disk and the shape of the data inside it.

Files (in ~/Library/Application Support/SecureVault/):
    salt.bin    -> random salt (not secret)
    vault.dat   -> encrypted blob (Fernet token) containing JSON:
                   {
                     "categories": ["Work", "Personal", ...],
                     "entries": [
                        {"id": "...", "category": "Work",
                         "service": "Gmail", "email": "me@gmail.com",
                         "password": "hunter2"}
                     ]
                   }
    meta.json   -> small non-secret settings, e.g. whether Touch ID
                   convenience-unlock is enabled.
"""

import os
import json
import uuid
from pathlib import Path

from . import crypto_utils

APP_DIR = Path.home() / "Library" / "Application Support" / "SecureVault"
SALT_FILE = APP_DIR / "salt.bin"
VAULT_FILE = APP_DIR / "vault.dat"
META_FILE = APP_DIR / "meta.json"

DEFAULT_CATEGORIES = ["Uncategorized"]


def ensure_app_dir():
    APP_DIR.mkdir(parents=True, exist_ok=True)


def vault_exists() -> bool:
    return VAULT_FILE.exists() and SALT_FILE.exists()


def load_salt() -> bytes:
    return SALT_FILE.read_bytes()


def save_salt(salt: bytes):
    ensure_app_dir()
    SALT_FILE.write_bytes(salt)


def load_meta() -> dict:
    if META_FILE.exists():
        return json.loads(META_FILE.read_text())
    return {"touch_id_enabled": False}


def save_meta(meta: dict):
    ensure_app_dir()
    META_FILE.write_text(json.dumps(meta))


def create_vault(master_password: str) -> bytes:
    """First-run setup. Returns the derived key."""
    ensure_app_dir()
    salt = crypto_utils.generate_salt()
    save_salt(salt)
    key = crypto_utils.derive_key(master_password, salt)
    empty_vault = {"categories": DEFAULT_CATEGORIES.copy(), "entries": []}
    token = crypto_utils.encrypt_data(empty_vault, key)
    VAULT_FILE.write_bytes(token)
    save_meta({"touch_id_enabled": False})
    return key


def unlock_vault(master_password: str) -> bytes:
    """Returns the derived key, raising WrongPassword if it doesn't decrypt."""
    salt = load_salt()
    key = crypto_utils.derive_key(master_password, salt)
    token = VAULT_FILE.read_bytes()
    crypto_utils.try_decrypt(token, key)  # will raise if wrong
    return key


def load_data(key: bytes) -> dict:
    token = VAULT_FILE.read_bytes()
    return crypto_utils.try_decrypt(token, key)


def save_data(data: dict, key: bytes):
    token = crypto_utils.encrypt_data(data, key)
    VAULT_FILE.write_bytes(token)


# ---------- convenience helpers used by the UI ----------

def new_entry(category, service, email, password) -> dict:
    return {
        "id": uuid.uuid4().hex,
        "category": category,
        "service": service,
        "email": email,
        "password": password,
    }


def add_category(data: dict, name: str):
    name = name.strip()
    if name and name not in data["categories"]:
        data["categories"].append(name)


def delete_category(data: dict, name: str):
    if name in data["categories"] and name != "Uncategorized":
        data["categories"].remove(name)
        for e in data["entries"]:
            if e["category"] == name:
                e["category"] = "Uncategorized"
        if "Uncategorized" not in data["categories"]:
            data["categories"].insert(0, "Uncategorized")
