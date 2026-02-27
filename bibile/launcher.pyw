#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Launcher silencieux pour Bibile
Lance le serveur et ouvre automatiquement le navigateur
"""

import subprocess
import webbrowser
import time
import sys
import os
from pathlib import Path

# Change le répertoire de travail vers le dossier du script
script_dir = Path(__file__).parent
os.chdir(script_dir)

def check_dependencies():
    """Vérifie et installe les dépendances si nécessaire"""
    try:
        import flask
        import pandas
        import openpyxl
        return True
    except ImportError:
        # Installe les dépendances
        subprocess.run([sys.executable, '-m', 'pip', 'install', '-r', 'requirements.txt', '--quiet'],
                      stdout=subprocess.DEVNULL,
                      stderr=subprocess.DEVNULL)
        return True

def main():
    """Lance Bibile"""

    # Vérifie les dépendances
    check_dependencies()

    # Lance le serveur Flask en mode silencieux
    # Redirige stdout et stderr vers DEVNULL pour éviter la console
    server_process = subprocess.Popen(
        [sys.executable, 'server.py'],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        cwd=script_dir
    )

    # Attend que le serveur démarre
    time.sleep(3)

    # Ouvre le navigateur
    webbrowser.open('http://localhost:5001')

    # Attend que le serveur se termine (normalement jamais, sauf si tué)
    try:
        server_process.wait()
    except KeyboardInterrupt:
        server_process.terminate()

if __name__ == '__main__':
    main()
