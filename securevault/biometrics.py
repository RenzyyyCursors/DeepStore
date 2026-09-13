"""
biometrics.py
-------------
Optional Touch ID convenience-unlock, using Apple's LocalAuthentication
framework through pyobjc.

IMPORTANT HONEST NOTE (please read):
This gives you a real Touch ID *prompt* gating access, which is genuinely
useful day-to-day. But the underlying vault key it unlocks is stored in the
macOS login Keychain via the `keyring` package. Without a proper code-signed
app + Keychain access-control entitlements (kSecAccessControlBiometryCurrentSet),
that Keychain item is protected by your macOS login/Keychain security, not by
a per-read biometric check enforced by the OS itself. In practice that's still
solid (an attacker needs your unlocked Mac session), but it is a step down
from the master password alone, which never touches disk in derivable form.
If you want maximum security, stick to the master password and skip Touch ID.
"""

import keyring

SERVICE_NAME = "SecureVault-App"
ACCOUNT_NAME = "vault-key"

try:
    from LocalAuthentication import LAContext, LAPolicyDeviceOwnerAuthenticationWithBiometrics
    _LA_AVAILABLE = True
except Exception:
    _LA_AVAILABLE = False


def touch_id_available() -> bool:
    if not _LA_AVAILABLE:
        return False
    ctx = LAContext.alloc().init()
    can_evaluate, error = ctx.canEvaluatePolicy_error_(
        LAPolicyDeviceOwnerAuthenticationWithBiometrics, None
    )
    return bool(can_evaluate)


def authenticate_touch_id(reason: str = "unlock your password vault") -> bool:
    """Blocks until the user responds to the Touch ID prompt. Returns True/False."""
    if not _LA_AVAILABLE:
        return False

    ctx = LAContext.alloc().init()
    result = {"success": False, "done": False}

    def callback(success, error):
        result["success"] = bool(success)
        result["done"] = True

    ctx.evaluatePolicy_localizedReason_reply_(
        LAPolicyDeviceOwnerAuthenticationWithBiometrics, reason, callback
    )

    # evaluatePolicy is async; pump a tiny run loop until the callback fires.
    from PyObjCTools import AppHelper
    import time
    from Foundation import NSRunLoop, NSDate

    timeout = time.time() + 30
    while not result["done"] and time.time() < timeout:
        NSRunLoop.currentRunLoop().runUntilDate_(NSDate.dateWithTimeIntervalSinceNow_(0.05))

    return result["success"]


def store_key(key_b64: bytes):
    keyring.set_password(SERVICE_NAME, ACCOUNT_NAME, key_b64.decode("utf-8"))


def retrieve_key():
    value = keyring.get_password(SERVICE_NAME, ACCOUNT_NAME)
    return value.encode("utf-8") if value else None


def clear_key():
    try:
        keyring.delete_password(SERVICE_NAME, ACCOUNT_NAME)
    except keyring.errors.PasswordDeleteError:
        pass
