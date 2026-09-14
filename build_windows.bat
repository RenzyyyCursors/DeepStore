@echo off
REM Build DeepStore.exe on Windows using PyInstaller.
REM Run from inside the DeepStore directory:
REM   build_windows.bat
REM
REM Prerequisites:
REM   pip install pyinstaller customtkinter cryptography keyring
REM   pip install pillow     (needed to convert icon JPG -> ICO)
REM

set APP_NAME=DeepStore
set ICON_JPG=assets\icon.jpg
set ICON_ICO=assets\icon.ico

echo ======================================================
echo    Building DeepStore for Windows
echo ======================================================

echo [1/5] Installing dependencies...
pip install -r requirements.txt

echo [2/5] Converting icon to .ico format...
python -c "from PIL import Image; img = Image.open('%ICON_JPG%').convert('RGBA'); img.save('%ICON_ICO%', format='ICO', sizes=[(16,16),(32,32),(48,48),(64,64),(128,128),(256,256)])"
if errorlevel 1 (
    echo WARNING: Icon conversion failed. Building without custom icon.
    set ICON_ARGS=
) else (
    echo Icon converted successfully: %ICON_ICO%
    set ICON_ARGS=--icon "%ICON_ICO%"
)

echo [3/5] Locating CustomTkinter assets...
for /f "delims=" %%i in ('python -c "import customtkinter, os; print(os.path.dirname(customtkinter.__file__))"') do set CTK_PATH=%%i
echo CustomTkinter Path: %CTK_PATH%

echo [4/5] Cleaning previous builds...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist %APP_NAME%.spec del /q %APP_NAME%.spec

echo [5/5] Running PyInstaller...
pyinstaller --noconfirm --windowed --name "%APP_NAME%" ^
    --add-data "%CTK_PATH%;customtkinter/" ^
    --add-data "assets;assets/" ^
    --hidden-import keyring.backends.Windows ^
    %ICON_ARGS% ^
    main.py

echo.
echo ======================================================
echo Build Complete!
echo Executable:  dist\%APP_NAME%\%APP_NAME%.exe
echo ======================================================
echo.
echo To create a single-file executable instead, rerun with --onefile:
echo   pyinstaller --noconfirm --windowed --onefile --name "%APP_NAME%" %ICON_ARGS% --add-data "%CTK_PATH%;customtkinter/" --hidden-import keyring.backends.Windows main.py
