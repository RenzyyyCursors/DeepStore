#!/bin/bash
# Build SecureVault.app on macOS using PyInstaller.
# Run this ON A MAC (not this Linux sandbox), from inside the SecureVault folder:
#
#   chmod +x build_macos.sh
#   ./build_macos.sh
#
set -e

APP_NAME="SecureVault"

echo "==> Installing dependencies..."
pip3 install -r requirements.txt

CTK_PATH=$(python3 -c "import customtkinter, os; print(os.path.dirname(customtkinter.__file__))")

echo "==> Cleaning old builds..."
rm -rf build dist "${APP_NAME}.spec"

echo "==> Running PyInstaller..."
pyinstaller --noconfirm --windowed --name "$APP_NAME" \
    --add-data "${CTK_PATH}:customtkinter/" \
    --hidden-import keyring.backends.macOS \
    main.py

echo "==> Ad-hoc code-signing (required on Apple Silicon, and needed for Touch ID prompts to work)..."
codesign --force --deep --sign - "dist/${APP_NAME}.app"

echo "==> Done. Your app is at dist/${APP_NAME}.app"
echo "    Double-click it, or run: open dist/${APP_NAME}.app"
echo ""
echo "First launch: right-click the app -> Open, since it's not notarized by Apple."
