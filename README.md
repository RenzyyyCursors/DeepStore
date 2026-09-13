# DeepStore

A minimalist, locally-encrypted password manager for macOS, styled with Apple Yellow & Graphite aesthetics and built with `customtkinter`.

## Highlights & Features

- **End-to-End Local Encryption**:
  - Derived using **scrypt** (`n=65536`, `r=8`, `p=1`) with a 256-bit cryptographically random salt.
  - Authenticated symmetric encryption via **Fernet** (AES-128-CBC + HMAC-SHA256).
  - Backward-compatible derivation for existing vaults.
- **In-App Passkey & Touch ID Management**:
  - Real-time Touch ID status detection.
  - In-app **Settings (⚙️)** modal to toggle Touch ID, re-sync passkeys to Keychain, or clear cached passkeys instantly.
  - Ability to safely **Change Master Passkey** and re-encrypt the entire vault atomically.
- **macOS Design Language & Animations**:
  - Apple Yellow (`#F5C518`) accent paired with Graphite dark/light surfaces.
  - Responsive hover elevation and interactive feedback.
  - Animated macOS Toast notifications for actions like "Copied to clipboard".
  - **Cell Card Layout**:
    - **Top**: Service Name + Category tag + **Show/Hide password toggle** + `⋯` action menu.
    - **Middle**: Username/Email display + Monospace password display.
    - **Bottom**: Twin **Copy User** and **Copy Pass** buttons placed neatly close together.
- **Security Hardening**:
  - **Atomic File Writes**: Prevents database corruption using temporary file atomic swaps (`os.replace`).
  - **Auto-Clearing Clipboard**: Automatically wipes copied secrets after 30 seconds (configurable).
  - **Inactivity Auto-Lock**: Automatically locks the vault after 1, 5, 15, or 30 minutes of idle time.
  - **Strict POSIX Permissions**: Restricts database files and directory to `0600` / `0700`.

## Running Directly

```bash
cd DeepStore
python3 -m venv venv
source venv/bin/activate
pip3 install -r requirements.txt
python3 main.py
```

## Building Standalone macOS App (`.app` / installer)

Run from inside the DeepStore repository on macOS:

```bash
chmod +x build_macos.sh
./build_macos.sh
```

This will produce `dist/DeepStore.app` which can be dragged directly into `/Applications` or packaged into `.dmg` / `.pkg`.

## File Structure

```
DeepStore/
├── main.py                 Application entry point
├── requirements.txt        Python dependencies
├── build_macos.sh          macOS PyInstaller build & code-signing script
└── securevault/
    ├── crypto_utils.py     scrypt KDF, Fernet encryption, password strength
    ├── storage.py          Atomic file persistence, 0600 permissions, key rotation
    ├── biometrics.py       Touch ID / LocalAuthentication + Keychain sync
    └── ui.py               macOS Yellow theme, cards, animations, toast & settings
```
