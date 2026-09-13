"""
storage.py
----------
Handles local vault storage, atomic persistence, strict permissions,
and passkey/metadata lifecycle.

Files in ~/Library/Application Support/SecureVault/ (or fallback ~/.securevault/):
    salt.bin    -> cryptographic salt (protected 0600)
    vault.dat   -> encrypted vault blob (protected 0600)
    meta.json   -> settings such as Touch ID & auto-lock timeout (0600)
"""

import os
import json
import uuid
import tempfile
from pathlib import Path
from typing import Optional, Dict, Any

from . import crypto_utils

# Use macOS standard Application Support path, with fallback
APP_DIR = Path.home() / "Library" / "Application Support" / "DeepStore"
if not (Path.home() / "Library").exists():
    APP_DIR = Path.home() / ".deepstore"

# Legacy path migration check
LEGACY_APP_DIR = Path.home() / "Library" / "Application Support" / "SecureVault"

SALT_FILE = APP_DIR / "salt.bin"
VAULT_FILE = APP_DIR / "vault.dat"
META_FILE = APP_DIR / "meta.json"

DEFAULT_CATEGORIES = ["Personal", "Work", "Finance", "Social", "Uncategorized"]
DEFAULT_META = {
    "touch_id_enabled": False,
    "auto_lock_minutes": 5,        # 0 = never, 1, 5, 15, 30
    "clipboard_clear_seconds": 30, # 15, 30, 60
    "theme": "System",
}


def ensure_app_dir():
    """Ensure app directory exists with strict 0700 permissions."""
    if not APP_DIR.exists():
        # Check if legacy directory exists to migrate seamlessly
        if LEGACY_APP_DIR.exists() and (LEGACY_APP_DIR / "vault.dat").exists():
            import shutil
            APP_DIR.mkdir(parents=True, exist_ok=True)
            try:
                os.chmod(APP_DIR, 0o700)
            except Exception:
                pass
            for item in LEGACY_APP_DIR.iterdir():
                try:
                    shutil.copy2(item, APP_DIR / item.name)
                except Exception:
                    pass
        else:
            APP_DIR.mkdir(parents=True, exist_ok=True)

    try:
        os.chmod(APP_DIR, 0o700)
    except Exception:
        pass


def _atomic_write_bytes(path: Path, data: bytes):
    """Atomically write bytes to disk with 0600 permissions to prevent file corruption."""
    ensure_app_dir()
    temp_file = None
    try:
        # Create temp file in same directory for atomic replace
        with tempfile.NamedTemporaryFile(dir=APP_DIR, delete=False) as tf:
            temp_file = Path(tf.name)
            tf.write(data)
            tf.flush()
            os.fsync(tf.fileno())

        try:
            os.chmod(temp_file, 0o600)
        except Exception:
            pass

        os.replace(temp_file, path)
        try:
            os.chmod(path, 0o600)
        except Exception:
            pass
    except Exception:
        if temp_file and temp_file.exists():
            try:
                temp_file.unlink()
            except Exception:
                pass
        raise


def _atomic_write_text(path: Path, text: str):
    """Atomically write text to disk."""
    _atomic_write_bytes(path, text.encode("utf-8"))


def vault_exists() -> bool:
    ensure_app_dir()
    return VAULT_FILE.exists() and SALT_FILE.exists()


def load_salt() -> bytes:
    return SALT_FILE.read_bytes()


def save_salt(salt: bytes):
    _atomic_write_bytes(SALT_FILE, salt)


def load_meta() -> dict:
    ensure_app_dir()
    if META_FILE.exists():
        try:
            loaded = json.loads(META_FILE.read_text(encoding="utf-8"))
            meta = DEFAULT_META.copy()
            meta.update(loaded)
            return meta
        except Exception:
            return DEFAULT_META.copy()
    return DEFAULT_META.copy()


def save_meta(meta: dict):
    merged = load_meta()
    merged.update(meta)
    _atomic_write_text(META_FILE, json.dumps(merged, indent=2))


def create_vault(master_password: str) -> bytes:
    """First-run setup: generates new salt, key, and empty vault."""
    ensure_app_dir()
    salt = crypto_utils.generate_salt()
    save_salt(salt)
    key = crypto_utils.derive_key(master_password, salt)
    empty_vault = {
        "version": 2,
        "categories": DEFAULT_CATEGORIES.copy(),
        "entries": []
    }
    token = crypto_utils.encrypt_data(empty_vault, key)
    _atomic_write_bytes(VAULT_FILE, token)
    save_meta(DEFAULT_META)
    return key


def unlock_vault(master_password: str) -> bytes:
    """Derive key and verify vault decryption. Returns derived key."""
    if not vault_exists():
        raise FileNotFoundError("Vault file not found.")
    salt = load_salt()
    token = VAULT_FILE.read_bytes()
    key, data = crypto_utils.try_derive_and_decrypt(token, master_password, salt)
    return key


def load_data(key: bytes) -> dict:
    token = VAULT_FILE.read_bytes()
    data = crypto_utils.try_decrypt(token, key)
    if "categories" not in data:
        data["categories"] = DEFAULT_CATEGORIES.copy()
    if "entries" not in data:
        data["entries"] = []
    return data


def save_data(data: dict, key: bytes):
    """Atomically encrypts and writes vault data."""
    token = crypto_utils.encrypt_data(data, key)
    _atomic_write_bytes(VAULT_FILE, token)


def change_master_password(old_key: bytes, new_password: str) -> bytes:
    """Re-encrypt the vault with a newly derived key and fresh random salt.
    Returns the new key."""
    data = load_data(old_key)
    new_salt = crypto_utils.generate_salt()
    new_key = crypto_utils.derive_key(new_password, new_salt)
    save_salt(new_salt)
    save_data(data, new_key)
    return new_key


def reset_entire_vault():
    """Wipes the vault files completely. Caution: irreversible."""
    for p in (VAULT_FILE, SALT_FILE, META_FILE):
        if p.exists():
            try:
                p.unlink()
            except Exception:
                pass


# ---------- Convenience helpers for UI ----------

def new_entry(category: str, service: str, email: str, password: str, notes: str = "") -> dict:
    return {
        "id": uuid.uuid4().hex,
        "category": category or "Uncategorized",
        "service": service.strip(),
        "email": email.strip(),
        "password": password,
        "notes": notes.strip(),
        "created_at": int(__import__("time").time()),
        "updated_at": int(__import__("time").time()),
    }


def add_category(data: dict, name: str) -> bool:
    name = name.strip()
    if not name:
        return False
    # Case-insensitive check
    if any(c.lower() == name.lower() for c in data["categories"]):
        return False
    data["categories"].append(name)
    return True


def delete_category(data: dict, name: str) -> bool:
    if name in data["categories"] and name != "Uncategorized":
        data["categories"].remove(name)
        for e in data["entries"]:
            if e.get("category") == name:
                e["category"] = "Uncategorized"
        if "Uncategorized" not in data["categories"]:
            data["categories"].append("Uncategorized")
        return True
    return False
