#!/usr/bin/env python3
"""
DeepStore - a local, encrypted password manager for Windows.
Run with:  python main.py
"""
from securevault.ui import SecureVaultApp

if __name__ == "__main__":
    app = SecureVaultApp()
    app.mainloop()
