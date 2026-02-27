@echo off
cls
echo ================================================================================
echo   INSTALLATION DE BIBILE
echo ================================================================================
echo.

REM Verifier si Python est installe
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo ERREUR: Python n'est pas installe sur cet ordinateur!
    echo.
    echo Veuillez installer Python depuis:
    echo https://www.python.org/downloads/
    echo.
    echo IMPORTANT: Cochez "Add Python to PATH" pendant l'installation
    echo.
    pause
    exit /b 1
)

echo [OK] Python est installe
python --version
echo.

REM Installer les dependances
echo Installation des dependances Python...
python -m pip install --upgrade pip >nul 2>&1
python -m pip install -r requirements.txt

if %errorlevel% neq 0 (
    echo.
    echo ERREUR lors de l'installation des dependances!
    pause
    exit /b 1
)

echo [OK] Dependances installees
echo.

REM Creer le raccourci sur le bureau
echo Creation du raccourci sur le bureau...
powershell -ExecutionPolicy Bypass -Command "$WshShell = New-Object -ComObject WScript.Shell; $Desktop = [Environment]::GetFolderPath('Desktop'); $Shortcut = $WshShell.CreateShortcut(\"$Desktop\Bibile - Extracteur Hillebrand.lnk\"); $Shortcut.TargetPath = '%~dp0LANCER_BIBILE_SILENCIEUX.bat'; $Shortcut.WorkingDirectory = '%~dp0'; $Shortcut.Save()"

if %errorlevel% equ 0 (
    echo [OK] Raccourci cree sur le bureau
) else (
    echo [ATTENTION] Le raccourci n'a pas pu etre cree automatiquement
    echo Vous pouvez creer un raccourci manuellement vers:
    echo %~dp0LANCER_BIBILE_SILENCIEUX.bat
)

echo.
echo ================================================================================
echo   INSTALLATION TERMINEE!
echo ================================================================================
echo.
echo Pour lancer Bibile:
echo - Double-cliquez sur le raccourci "Bibile - Extracteur Hillebrand" sur votre bureau
echo   OU
echo - Double-cliquez sur LANCER_BIBILE_SILENCIEUX.bat dans ce dossier
echo.
echo Pour arreter Bibile:
echo - Double-cliquez sur ARRETER_BIBILE.bat
echo.
pause
