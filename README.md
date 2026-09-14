# DeepStore

A minimalist, locally-encrypted password manager for Windows, styled with Golden Yellow & Slate aesthetics and built with `customtkinter`.

## Highlights & Features

- **End-to-End Local Encryption**:
  - Derived using **scrypt** (`n=65536`, `r=8`, `p=1`) with a 256-bit cryptographically random salt.
  - Authenticated symmetric encryption via **Fernet** (AES-128-CBC + HMAC-SHA256).
  - Backward-compatible derivation for existing vaults.
- **Windows Password & Credential Manager Integration**:
  - Quick unlock using your active **Windows account password** (`advapi32.LogonUserW`).
  - Seamless passkey caching into **Windows Credential Manager** (`keyring.backends.Windows`).
  - In-app **Preferences (⚙️)** modal to toggle Windows Quick Unlock, re-sync passkeys to Windows Credential Manager, or clear cached credentials.
  - Ability to safely **Change Master Passkey** and re-encrypt the entire vault atomically.
- **Modern Windows Design & Typography**:
  - Golden Yellow (`#F5C518`) accent paired with Slate dark/light surfaces.
  - `Segoe UI` typography with `Consolas` monospace font.
  - Responsive hover elevation and interactive feedback.
  - Animated Toast notifications for actions like "Copied to clipboard".
  - **Cell Card Layout**:
    - **Top**: Service Name + Category tag + **Show/Hide password toggle** + `⋯` action menu.
    - **Middle**: Username/Email display + Monospace password display.
    - **Bottom**: Twin **Copy User** and **Copy Pass** buttons placed neatly close together.
- **Security Hardening**:
  - **Atomic File Writes**: Prevents database corruption using temporary file atomic swaps (`os.replace`).
  - **Auto-Clearing Clipboard**: Automatically wipes copied secrets after 30 seconds (configurable).
  - **Inactivity Auto-Lock**: Automatically locks the vault after 1, 5, 15, or 30 minutes of idle time.
  - **Standard Windows Storage**: Encrypted data stored under `%APPDATA%\DeepStore`.

## Running Directly

On Windows (Command Prompt or PowerShell):

```bat
cd DeepStore
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

## Building Standalone Windows Executable (`.exe`)

Run from inside the DeepStore repository on Windows:

```bat
build_windows.bat
```

This will run PyInstaller and generate `dist\DeepStore\DeepStore.exe`.

## File Structure

```
DeepStore/
├── main.py                 Application entry point
├── requirements.txt        Python dependencies
├── build_windows.bat       Windows PyInstaller build script
└── securevault/
    ├── crypto_utils.py     scrypt KDF, Fernet encryption, password strength
    ├── storage.py          %APPDATA% storage, atomic file persistence, key rotation
    ├── win_auth.py         Windows account password verification & Windows Credential Manager
    ├── biometrics.py       Backward compatibility bridge to win_auth
    └── ui.py               Windows Segoe UI theme, cards, animations, toast & settings
```
