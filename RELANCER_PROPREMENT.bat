@echo off
cls
echo ================================================================================
echo   RELANCEMENT PROPRE DE BIBILE
echo ================================================================================
echo.
echo Etape 1: Arret de tous les serveurs Python...
taskkill /F /IM python.exe >nul 2>&1
taskkill /F /IM pythonw.exe >nul 2>&1
taskkill /F /IM python3.13.exe >nul 2>&1
taskkill /F /IM pythonw3.13.exe >nul 2>&1
echo OK Serveurs arretes
echo.

echo Etape 2: Suppression du cache Python...
cd /d "%~dp0bibile"
python -c "import shutil; shutil.rmtree('__pycache__', ignore_errors=True); print('Cache supprime')"
echo.

echo Etape 3: Lancement du serveur...
start "" pythonw server.py
echo OK Serveur lance en arriere-plan
echo.

echo Etape 4: Attente du demarrage (3 secondes)...
timeout /t 3 /nobreak >nul
echo.

echo Etape 5: Ouverture du navigateur...
start http://localhost:5001
echo.

echo ================================================================================
echo   BIBILE EST LANCE AVEC LE NOUVEAU CODE!
echo ================================================================================
echo.
echo Pour arreter Bibile, lancez ARRETER_BIBILE.bat
echo.
timeout /t 5
