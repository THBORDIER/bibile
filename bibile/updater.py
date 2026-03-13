"""
Bibile - Systeme de mise a jour automatique depuis GitHub Releases.
Utilise uniquement urllib (stdlib) pour eviter les dependances externes.
"""

import json
import os
import sys
import subprocess
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import URLError


GITHUB_API_URL = "https://api.github.com/repos/THBORDIER/bibile/releases/latest"


def _parse_version(v):
    """Parse '3.1.0' ou 'v3.1.0' en tuple (3, 1, 0)."""
    return tuple(int(x) for x in v.lstrip('v').split('.'))


def is_newer(remote, local):
    """True si la version remote est plus recente que local."""
    try:
        return _parse_version(remote) > _parse_version(local)
    except (ValueError, AttributeError):
        return False


def check_for_update(current_version):
    """
    Verifie si une nouvelle version est disponible sur GitHub.
    Retourne un dict {version, download_url, changelog} ou None.
    Ne lance jamais d'exception.
    """
    try:
        req = Request(GITHUB_API_URL, headers={'User-Agent': 'Bibile-Updater'})
        with urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode('utf-8'))

        tag = data.get('tag_name', '')
        if not tag or not is_newer(tag, current_version):
            return None

        # Chercher le ZIP dans les assets
        download_url = None
        for asset in data.get('assets', []):
            if asset.get('name', '').lower().endswith('.zip'):
                download_url = asset.get('browser_download_url')
                break

        if not download_url:
            return None

        return {
            'version': tag.lstrip('v'),
            'download_url': download_url,
            'changelog': data.get('body', ''),
        }
    except Exception:
        return None


def download_update(download_url, dest_path):
    """
    Telecharge le ZIP de mise a jour.
    Retourne True si succes, False sinon.
    """
    try:
        dest_path = Path(dest_path)
        dest_path.parent.mkdir(parents=True, exist_ok=True)

        req = Request(download_url, headers={'User-Agent': 'Bibile-Updater'})
        with urlopen(req, timeout=120) as resp:
            with open(dest_path, 'wb') as f:
                while True:
                    chunk = resp.read(8192)
                    if not chunk:
                        break
                    f.write(chunk)
        return True
    except Exception:
        return False


def apply_update(zip_path, app_dir):
    """
    Lance un script batch qui attend la fermeture de l'app,
    extrait le ZIP par-dessus le dossier d'installation, et relance l'app.
    """
    zip_path = Path(zip_path).resolve()
    app_dir = Path(app_dir).resolve()
    parent_dir = app_dir.parent

    # Dossier de donnees utilisateur pour le script batch
    data_dir = Path(os.environ.get('BIBILE_DATA_DIR', app_dir))
    batch_path = data_dir / 'update.bat'

    pid = os.getpid()

    batch_content = f"""@echo off
title Mise a jour Bibile...
echo Mise a jour de Bibile en cours, veuillez patienter...
echo.

:: Attendre que l'application se ferme
:wait_loop
tasklist /FI "PID eq {pid}" 2>NUL | find /I "Bibile.exe" >NUL
if not errorlevel 1 (
    timeout /t 1 /nobreak >NUL
    goto wait_loop
)

:: Petite pause de securite
timeout /t 2 /nobreak >NUL

:: Extraire la mise a jour
echo Extraction de la mise a jour...
powershell -Command "Expand-Archive -Path '{zip_path}' -DestinationPath '{parent_dir}' -Force"

:: Nettoyage
del "{zip_path}"

:: Relancer l'application
echo Redemarrage de Bibile...
start "" "{app_dir / 'Bibile.exe'}"

:: Auto-suppression du script
del "%~f0"
"""

    with open(batch_path, 'w', encoding='utf-8') as f:
        f.write(batch_content)

    # Lancer le batch en processus detache
    subprocess.Popen(
        ['cmd', '/c', str(batch_path)],
        creationflags=subprocess.CREATE_NEW_CONSOLE,
        close_fds=True,
    )

    # Fermer l'application
    sys.exit(0)
