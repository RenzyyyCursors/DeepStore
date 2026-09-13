"""
biometrics.py
-------------
Touch ID / Apple Passkey biometric unlock integration via LocalAuthentication
and secure macOS Keychain storage.
"""

import logging
import threading
import time
from typing import Optional, Callable
import keyring

SERVICE_NAME = "DeepStore-App"
ACCOUNT_NAME = "vault-key"
LEGACY_SERVICE_NAME = "SecureVault-App"

try:
    from LocalAuthentication import (
        LAContext,
        LAPolicyDeviceOwnerAuthenticationWithBiometrics,
        LAPolicyDeviceOwnerAuthentication
    )
    _LA_AVAILABLE = True
except Exception:
    _LA_AVAILABLE = False


def touch_id_available() -> bool:
    """Check if Touch ID or device biometric authentication is available on this Mac."""
    if not _LA_AVAILABLE:
        return False
    try:
        ctx = LAContext.alloc().init()
        can_evaluate, error = ctx.canEvaluatePolicy_error_(
            LAPolicyDeviceOwnerAuthenticationWithBiometrics, None
        )
        return bool(can_evaluate)
    except Exception:
        return False


def authenticate_touch_id(reason: str = "Unlock DeepStore Vault", update_pump: Optional[Callable] = None) -> bool:
    """Prompts for Touch ID biometric verification asynchronously without freezing the Tkinter event loop."""
    if not _LA_AVAILABLE:
        return False

    done_event = threading.Event()
    result = [False]

    def _auth_worker():
        try:
            ctx = LAContext.alloc().init()

            def reply_handler(success, error):
                result[0] = bool(success)
                done_event.set()

            ctx.evaluatePolicy_localizedReason_reply_(
                LAPolicyDeviceOwnerAuthenticationWithBiometrics, reason, reply_handler
            )
        except Exception as e:
            logging.error(f"Touch ID auth error: {e}")
            done_event.set()

    thread = threading.Thread(target=_auth_worker, daemon=True)
    thread.start()

    start_time = time.time()
    # Wait up to 30 seconds for biometric prompt response while keeping UI responsive
    while not done_event.is_set() and (time.time() - start_time < 30):
        if update_pump:
            try:
                update_pump()
            except Exception:
                pass
        done_event.wait(timeout=0.04)

    return result[0]


def store_key(key_b64: bytes) -> bool:
    """Store the derived vault key into macOS Keychain."""
    try:
        key_str = key_b64.decode("utf-8") if isinstance(key_b64, bytes) else str(key_b64)
        keyring.set_password(SERVICE_NAME, ACCOUNT_NAME, key_str)
        return True
    except Exception as e:
        logging.error(f"Failed to store passkey in keychain: {e}")
        return False


def retrieve_key() -> Optional[bytes]:
    """Retrieve the cached vault key from macOS Keychain."""
    try:
        value = keyring.get_password(SERVICE_NAME, ACCOUNT_NAME)
        if not value:
            # Check legacy service name
            value = keyring.get_password(LEGACY_SERVICE_NAME, ACCOUNT_NAME)
        return value.encode("utf-8") if value else None
    except Exception as e:
        logging.error(f"Failed to retrieve passkey from keychain: {e}")
        return None


def is_key_stored() -> bool:
    """Check if a passkey is currently saved in Keychain."""
    try:
        val = keyring.get_password(SERVICE_NAME, ACCOUNT_NAME)
        if not val:
            val = keyring.get_password(LEGACY_SERVICE_NAME, ACCOUNT_NAME)
        return bool(val)
    except Exception:
        return False


def clear_key() -> bool:
    """Remove the cached passkey from macOS Keychain."""
    success = True
    for srv in (SERVICE_NAME, LEGACY_SERVICE_NAME):
        try:
            keyring.delete_password(srv, ACCOUNT_NAME)
        except Exception:
            pass
    return success
