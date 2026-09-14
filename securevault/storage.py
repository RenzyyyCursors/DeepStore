"""
storage.py
----------
Handles local vault storage, atomic persistence, strict permissions,
and passkey/metadata lifecycle on Windows.

Standard Windows location:
    %APPDATA%\\DeepStore\\
        salt.bin    -> cryptographic salt
        vault.dat   -> encrypted vault blob
        meta.json   -> settings such as Windows Auth & auto-lock timeout
"""

import os
import sys
import json
import uuid
import shutil
import tempfile
from pathlib import Path
from typing import Optional, Dict, Any

from . import crypto_utils

# Standard Windows AppData directory with cross-platform fallback
if sys.platform == "win32" or os.name == "nt":
    appdata = os.environ.get("APPDATA")
    if appdata:
        APP_DIR = Path(appdata) / "DeepStore"
    else:
        APP_DIR = Path.home() / "AppData" / "Roaming" / "DeepStore"
    LEGACY_APP_DIRS = [
        Path.home() / "AppData" / "Roaming" / "SecureVault",
        Path.home() / ".deepstore",
        Path.home() / ".securevault",
    ]
elif sys.platform == "darwin":
    APP_DIR = Path.home() / "Library" / "Application Support" / "DeepStore"
    LEGACY_APP_DIRS = [
        Path.home() / "Library" / "Application Support" / "SecureVault",
        Path.home() / ".deepstore",
    ]
else:
    APP_DIR = Path.home() / ".deepstore"
    LEGACY_APP_DIRS = [Path.home() / ".securevault"]

SALT_FILE = APP_DIR / "salt.bin"
VAULT_FILE = APP_DIR / "vault.dat"
META_FILE = APP_DIR / "meta.json"

DEFAULT_CATEGORIES = ["Personal", "Work", "Finance", "Social", "Uncategorized"]
DEFAULT_META = {
    "windows_auth_enabled": False,
    "auto_lock_minutes": 5,        # 0 = never, 1, 5, 15, 30
    "clipboard_clear_seconds": 30, # 15, 30, 60
    "theme": "System",
}


def ensure_app_dir():
    """Ensure app directory exists with appropriate permissions and handles legacy migration."""
    if not APP_DIR.exists():
        migrated = False
        for legacy_dir in LEGACY_APP_DIRS:
            if legacy_dir.exists() and (legacy_dir / "vault.dat").exists():
                APP_DIR.mkdir(parents=True, exist_ok=True)
                for item in legacy_dir.iterdir():
                    try:
                        shutil.copy2(item, APP_DIR / item.name)
                    except Exception:
                        pass
                migrated = True
                break

        if not migrated:
            APP_DIR.mkdir(parents=True, exist_ok=True)

    try:
        os.chmod(APP_DIR, 0o700)
    except Exception:
        pass


def _atomic_write_bytes(path: Path, data: bytes):
    """
    Atomically write bytes to disk.
    Explicitly closes temporary file handles to support Windows NTFS locking semantics.
    """
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

        # Perform atomic replace (file handle is closed outside the 'with' block)
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
            # Seamless migration from touch_id_enabled to windows_auth_enabled
            if "touch_id_enabled" in meta and "windows_auth_enabled" not in loaded:
                meta["windows_auth_enabled"] = meta["touch_id_enabled"]
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
    """
    Re-encrypt the vault with a newly derived key and fresh random salt.
    Returns the new key.
    """
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
