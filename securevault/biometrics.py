"""
biometrics.py
-------------
Backward compatibility wrapper bridging to win_auth.py.
"""

from .win_auth import (
    SERVICE_NAME,
    ACCOUNT_NAME,
    LEGACY_SERVICE_NAME,
    is_windows,
    get_current_username,
    windows_auth_available,
    verify_windows_password,
    store_key,
    retrieve_key,
    is_key_stored,
    clear_key,
)

# Compatibility aliases
def touch_id_available() -> bool:
    return windows_auth_available()

def authenticate_touch_id(reason: str = "", update_pump=None) -> bool:
    return False
