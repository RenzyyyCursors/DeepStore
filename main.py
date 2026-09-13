#!/usr/bin/env python3
"""
SecureVault - a local, encrypted password manager for macOS.
Run with:  python3 main.py
"""
from securevault.ui import SecureVaultApp

if __name__ == "__main__":
    app = SecureVaultApp()
    app.mainloop()
