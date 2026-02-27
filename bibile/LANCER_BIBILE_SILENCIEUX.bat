@echo off
REM Lance Bibile en arriere-plan et ouvre le navigateur automatiquement

REM Verifie si Python est installe
where python >nul 2>&1
if %errorlevel% neq 0 (
    msg * "Python n'est pas installe. Veuillez installer Python depuis https://www.python.org/downloads/"
    exit /b 1
)

REM Installation silencieuse des dependances
pip install -r requirements.txt --quiet --disable-pip-version-check >nul 2>&1

REM Lance le serveur en arriere-plan (sans fenetre)
start "" pythonw server.py

REM Attend 3 secondes que le serveur demarre
timeout /t 3 /nobreak >nul

REM Ouvre le navigateur
start http://localhost:5001

REM Affiche une notification
msg * "Bibile est lance! Le navigateur va s'ouvrir automatiquement. Pour arreter Bibile, lancez ARRETER_BIBILE.bat"
