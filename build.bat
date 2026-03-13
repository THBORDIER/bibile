@echo off
echo ============================================
echo   Build Bibile Desktop
echo ============================================
echo.

echo [1/3] Installation des dependances de build...
python -m pip install pyinstaller pywebview flask pandas openpyxl pyodbc pymssql >nul 2>&1

echo [2/3] Nettoyage des anciens builds...
if exist "dist" rmdir /s /q dist
if exist "build" rmdir /s /q build

echo [3/4] Build de l'executable...
python -m PyInstaller bibile.spec --clean --noconfirm

echo.
if exist "dist\Bibile\Bibile.exe" (
    echo [4/4] Creation du ZIP pour release GitHub...
    powershell -Command "Compress-Archive -Path 'dist\Bibile' -DestinationPath 'dist\Bibile.zip' -Force"
    echo.
    echo ============================================
    echo   Build termine avec succes !
    echo   Executable: dist\Bibile\Bibile.exe
    echo   ZIP release: dist\Bibile.zip
    echo ============================================
) else (
    echo ============================================
    echo   ERREUR: Le build a echoue.
    echo ============================================
)
echo.
pause
