# SecureVault

A minimalist, locally-encrypted password manager for macOS, built with
`customtkinter`.

## What it does

- One master password unlocks everything. Nothing is stored in plaintext.
- Encryption: your master password is run through **scrypt** (a memory-hard
  key derivation function) to produce a key, which encrypts your vault with
  **Fernet** (AES-128-CBC + HMAC authentication) from the `cryptography`
  library.
- Optional **Touch ID** convenience-unlock (see "About Touch ID / passkeys"
  below — please read it, it explains what this does and doesn't protect
  against).
- Categories you can add/delete, plus an "All" tab.
- 4×4 grid (16 per page) of password cards showing service, email, and a
  masked password, each with independent "Show/Hide" and "Copy" controls.
- Search box to filter by service or email.
- Light / Dark / System appearance toggle.
- All data stays on your Mac at:
  `~/Library/Application Support/SecureVault/`

## Running it directly (no packaging)

```bash
cd SecureVault
python3 -m venv venv
source venv/bin/activate
pip3 install -r requirements.txt
python3 main.py
```

## Building a standalone macOS app (PyInstaller)

This must be run **on a Mac** — PyInstaller builds for the OS it's run on.

```bash
cd SecureVault
chmod +x build_macos.sh
./build_macos.sh
```

This produces `dist/SecureVault.app`, which you can drag into
`/Applications`. The script ad-hoc code-signs the app, which is required on
Apple Silicon Macs for it to launch at all, and helps the Touch ID prompt
behave correctly.

Because the app isn't notarized by Apple, macOS Gatekeeper will block it on
first launch. **Right-click the app → Open → Open** once, and it will run
normally afterward. This is expected for any app you build yourself outside
the App Store / Developer ID program — it's not a bug in the code.

## About Touch ID / "passkeys"

You asked for a passkey option. True FIDO2/WebAuthn passkeys are a
web-authentication standard between a browser and a server — they don't have
a meaningful equivalent for a local desktop app with no server. The closest
real, useful equivalent on macOS is **Touch ID**, which this app supports as
an optional convenience unlock via Apple's LocalAuthentication framework.

Honesty about its security: when you enable Touch ID, the derived vault key
is stored in your macOS login Keychain (via the `keyring` library) and the
Touch ID prompt gates the app's *access* to it. Without a paid Apple
Developer ID, proper app signing, and Keychain access-control entitlements,
this isn't as strong a guarantee as an OS-enforced per-read biometric check —
it relies on your Mac's own login/Keychain security. Your master password
path never stores anything derivable on disk and is the stronger option. Use
Touch ID for convenience; keep the master password as your real secret, and
skip Touch ID entirely if you want the strongest posture.

## A note on "unhackable"

No software is unhackable, and I'd rather tell you that plainly than oversell
it. What this app does give you: strong, standard, well-reviewed
cryptographic primitives (scrypt + Fernet/AES), no plaintext storage, no
password stored anywhere for recovery (which also means if you forget your
master password, **your data is unrecoverable — there is no backdoor**), and
a small, readable codebase you can audit yourself since it's only a few
hundred lines.

## File layout

```
SecureVault/
├── main.py                 entry point
├── requirements.txt
├── build_macos.sh          PyInstaller build script (run on macOS)
└── securevault/
    ├── crypto_utils.py     scrypt key derivation + Fernet encrypt/decrypt
    ├── storage.py          vault file I/O, categories/entries helpers
    ├── biometrics.py       Touch ID via LocalAuthentication (macOS only)
    └── ui.py               customtkinter UI (login + main vault screen)
```
