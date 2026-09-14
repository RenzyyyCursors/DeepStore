"""
win_auth.py
-----------
Windows User Password authentication integration via advapi32.LogonUserW
and secure Windows Credential Manager storage via keyring.
"""

import os
import sys
import logging
from typing import Optional
import keyring

SERVICE_NAME = "DeepStore-App"
ACCOUNT_NAME = "vault-key"
LEGACY_SERVICE_NAME = "SecureVault-App"


def is_windows() -> bool:
    """Check if the current runtime environment is Windows."""
    return sys.platform == "win32" or os.name == "nt"


def get_current_username() -> str:
    """Returns the current logged-in Windows username."""
    user = os.environ.get("USERNAME") or os.environ.get("USER")
    if not user:
        try:
            user = os.getlogin()
        except Exception:
            user = "Windows User"
    return user


def windows_auth_available() -> bool:
    """Check if Windows authentication is available on this system."""
    if not is_windows():
        return True  # Fallback enabled for cross-platform/testing
    try:
        import ctypes
        return hasattr(ctypes, "windll") and hasattr(ctypes.windll, "advapi32")
    except Exception:
        return False


def verify_windows_password(password: str, username: Optional[str] = None) -> bool:
    """
    Verify the Windows account password using advapi32.LogonUserW.
    Returns True if the credentials are valid for the active user.
    """
    if not password:
        return False

    if not is_windows():
        # Fallback when running non-Windows development
        return len(password) > 0

    try:
        import ctypes
        from ctypes import wintypes

        if not username:
            username = get_current_username()

        domain = os.environ.get("USERDOMAIN") or "."

        LOGON32_LOGON_INTERACTIVE = 2
        LOGON32_PROVIDER_DEFAULT = 0

        token = wintypes.HANDLE()
        advapi32 = ctypes.windll.advapi32

        advapi32.LogonUserW.argtypes = [
            wintypes.LPCWSTR,
            wintypes.LPCWSTR,
            wintypes.LPCWSTR,
            wintypes.DWORD,
            wintypes.DWORD,
            ctypes.POINTER(wintypes.HANDLE),
        ]
        advapi32.LogonUserW.restype = wintypes.BOOL

        domain_str = "." if (not domain or domain.lower() == username.lower()) else domain

        success = advapi32.LogonUserW(
            username,
            domain_str,
            password,
            LOGON32_LOGON_INTERACTIVE,
            LOGON32_PROVIDER_DEFAULT,
            ctypes.byref(token),
        )

        if success:
            ctypes.windll.kernel32.CloseHandle(token)
            return True

        # Fallback with empty/None domain for Microsoft account / local logins
        success_retry = advapi32.LogonUserW(
            username,
            None,
            password,
            LOGON32_LOGON_INTERACTIVE,
            LOGON32_PROVIDER_DEFAULT,
            ctypes.byref(token),
        )
        if success_retry:
            ctypes.windll.kernel32.CloseHandle(token)
            return True

        return False
    except Exception as e:
        logging.error(f"Windows logon auth error: {e}")
        return False


def store_key(key_b64: bytes) -> bool:
    """Store the derived vault key into Windows Credential Manager."""
    try:
        key_str = key_b64.decode("utf-8") if isinstance(key_b64, bytes) else str(key_b64)
        keyring.set_password(SERVICE_NAME, ACCOUNT_NAME, key_str)
        return True
    except Exception as e:
        logging.error(f"Failed to store key in Windows Credential Manager: {e}")
        return False


def retrieve_key() -> Optional[bytes]:
    """Retrieve the cached vault key from Windows Credential Manager."""
    try:
        value = keyring.get_password(SERVICE_NAME, ACCOUNT_NAME)
        if not value:
            # Check legacy service name
            value = keyring.get_password(LEGACY_SERVICE_NAME, ACCOUNT_NAME)
        return value.encode("utf-8") if value else None
    except Exception as e:
        logging.error(f"Failed to retrieve key from Windows Credential Manager: {e}")
        return None


def is_key_stored() -> bool:
    """Check if a passkey is currently saved in Windows Credential Manager."""
    try:
        val = keyring.get_password(SERVICE_NAME, ACCOUNT_NAME)
        if not val:
            val = keyring.get_password(LEGACY_SERVICE_NAME, ACCOUNT_NAME)
        return bool(val)
    except Exception:
        return False


def clear_key() -> bool:
    """Remove the cached passkey from Windows Credential Manager."""
    success = True
    for srv in (SERVICE_NAME, LEGACY_SERVICE_NAME):
        try:
            keyring.delete_password(srv, ACCOUNT_NAME)
        except Exception:
            pass
    return success
