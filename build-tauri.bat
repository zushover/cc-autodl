@echo off
echo ==========================================
echo   AutoDL Manager — Tauri Build
echo ==========================================
echo.

:: 1. Load VS 2022 build tools
call "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat" >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] VS 2022 Build Tools not found
    echo Install: https://visualstudio.microsoft.com/downloads/
    pause
    exit /b 1
)
echo [OK] MSVC build tools loaded

:: 2. Verify Rust
rustc --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Rust not found
    pause
    exit /b 1
)
echo [OK] Rust:
rustc --version

:: 3. Ensure MSVC target
rustup target list --installed | findstr "x86_64-pc-windows-msvc" >nul
if %ERRORLEVEL% NEQ 0 (
    echo [INFO] Installing MSVC target...
    rustup target add x86_64-pc-windows-msvc
)

:: 4. Copy sidecar to Tauri binaries
echo [INFO] Copying Python sidecar...
if not exist "src-tauri\binaries" mkdir "src-tauri\binaries"
copy /y "dist\python-sidecar.exe" "src-tauri\binaries\python-sidecar-x86_64-pc-windows-msvc.exe" >nul
echo [OK] Sidecar copied

:: 5. Install npm deps
echo [INFO] Installing npm dependencies...
call npm install --silent 2>nul
echo [OK] npm dependencies

:: 6. Build Tauri
echo.
echo ==========================================
echo   Building Tauri application...
echo ==========================================
echo.

call npx tauri build 2>&1

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ==========================================
    echo   BUILD SUCCESSFUL!
    echo   Installer: src-tauri\target\release\bundle\
    echo ==========================================
) else (
    echo.
    echo [ERROR] Build failed. See output above.
)

pause
