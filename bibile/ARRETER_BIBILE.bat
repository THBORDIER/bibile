@echo off
cls

echo ================================================================================
echo   ARRET DE BIBILE
echo ================================================================================
echo.

REM Tue tous les processus Python
taskkill /F /IM python.exe >nul 2>&1
taskkill /F /IM pythonw.exe >nul 2>&1

REM Trouve et tue tous les processus qui utilisent le port 5001
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":5001.*LISTENING"') do (
    taskkill /F /PID %%a >nul 2>&1
)

echo OK Bibile arrete!
echo.
echo Tous les serveurs sur le port 5001 ont ete arretes.
echo.
echo Vous pouvez maintenant fermer cette fenetre.
echo.
timeout /t 3
