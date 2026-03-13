@echo off
echo ============================================
echo   Build Bibile Desktop
echo ============================================
echo.

echo [1/3] Installation des dependances de build...
pip install pyinstaller pywebview flask pandas openpyxl >nul 2>&1

echo [2/3] Nettoyage des anciens builds...
if exist "dist" rmdir /s /q dist
if exist "build" rmdir /s /q build

echo [3/3] Build de l'executable...
pyinstaller bibile.spec --clean --noconfirm

echo.
if exist "dist\Bibile\Bibile.exe" (
    echo ============================================
    echo   Build termine avec succes !
    echo   Executable: dist\Bibile\Bibile.exe
    echo ============================================
) else (
    echo ============================================
    echo   ERREUR: Le build a echoue.
    echo ============================================
)
echo.
pause
