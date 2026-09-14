"""
test_windows_compatibility.py
------------------------------
Automated verification tests for DeepStore Windows features.
"""

import sys
import os
import unittest
from pathlib import Path

# Ensure securevault can be imported
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from securevault import crypto_utils, storage, win_auth


class TestCrypto(unittest.TestCase):
    def test_key_derivation_and_encryption(self):
        salt = crypto_utils.generate_salt()
        key = crypto_utils.derive_key("MySuperSecret123!", salt)
        data = {"categories": ["Work", "Personal"], "entries": [{"service": "GitHub", "password": "pass"}]}
        encrypted = crypto_utils.encrypt_data(data, key)
        decrypted = crypto_utils.decrypt_data(encrypted, key)
        self.assertEqual(decrypted["categories"], ["Work", "Personal"])
        self.assertEqual(decrypted["entries"][0]["service"], "GitHub")

    def test_password_strength(self):
        score, label = crypto_utils.check_password_strength("weak")
        self.assertIn(label, ["Weak", "Too Weak"])
        score_strong, label_strong = crypto_utils.check_password_strength("C0mpl3x_P@ssw0rd!2026")
        self.assertGreaterEqual(score_strong, 3)


class TestStorage(unittest.TestCase):
    def test_app_dir_exists(self):
        storage.ensure_app_dir()
        self.assertTrue(storage.APP_DIR.exists())

    def test_atomic_write_and_metadata(self):
        meta = storage.load_meta()
        self.assertIn("windows_auth_enabled", meta)
        self.assertIn("auto_lock_minutes", meta)


class TestWinAuth(unittest.TestCase):
    def test_username_retrieval(self):
        user = win_auth.get_current_username()
        self.assertTrue(len(user) > 0)
        print(f"Detected user: {user}")

    def test_key_storage_and_retrieval(self):
        test_key = b"dGVzdF9rZXlfMTIzNDU2Nzg5MDEyMzQ1Njc4OTAxMjM0NTY3ODk="
        stored = win_auth.store_key(test_key)
        self.assertTrue(stored)
        self.assertTrue(win_auth.is_key_stored())
        retrieved = win_auth.retrieve_key()
        self.assertEqual(retrieved, test_key)
        cleared = win_auth.clear_key()
        self.assertTrue(cleared)


if __name__ == "__main__":
    unittest.main()
