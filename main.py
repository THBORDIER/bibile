#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bibile Desktop - Point d'entree de l'application desktop.

Lance Flask dans un thread interne et ouvre une fenetre native via pywebview.
Compatible avec PyInstaller pour generer un .exe autonome.
"""

import os
import sys
import socket
import threading
import time
from pathlib import Path


def get_data_dir():
    """Retourne le dossier de donnees utilisateur (%APPDATA%/Bibile en mode bundle, sinon bibile/)."""
    if getattr(sys, '_MEIPASS', None):
        # Mode PyInstaller : donnees dans %APPDATA%/Bibile
        data_dir = Path(os.environ.get('APPDATA', '.')) / 'Bibile'
    else:
        # Mode dev : donnees dans bibile/
        data_dir = Path(__file__).parent / 'bibile'
    return data_dir


def find_free_port(start=5001, end=5010):
    """Trouve un port libre entre start et end."""
    for port in range(start, end + 1):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('127.0.0.1', port))
                return port
        except OSError:
            continue
    return start  # fallback


def wait_for_server(port, timeout=10):
    """Attend que le serveur Flask soit pret."""
    start = time.time()
    while time.time() - start < timeout:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect(('127.0.0.1', port))
                return True
        except (ConnectionRefusedError, OSError):
            time.sleep(0.1)
    return False


def import_ancien_historique(db_path):
    """
    Dialogue d'import au premier lancement.
    Propose a l'utilisateur de selectionner son ancien dossier historique
    pour importer les fichiers Excel existants dans la base SQLite.
    """
    import tkinter as tk
    from tkinter import messagebox, filedialog

    root = tk.Tk()
    root.withdraw()  # Cacher la fenetre principale

    reponse = messagebox.askyesno(
        "Bibile - Premier lancement",
        "Bienvenue dans Bibile !\n\n"
        "Voulez-vous importer votre ancien historique ?\n"
        "Sélectionnez le dossier contenant vos fichiers Enlevements_*.xlsx"
    )

    if not reponse:
        root.destroy()
        return

    dossier = filedialog.askdirectory(
        title="Sélectionner le dossier historique"
    )

    if not dossier:
        root.destroy()
        return

    dossier = Path(dossier)
    fichiers_xlsx = sorted(dossier.glob('Enlevements_*.xlsx'))

    if not fichiers_xlsx:
        messagebox.showwarning(
            "Aucun fichier trouvé",
            f"Aucun fichier Enlevements_*.xlsx trouvé dans :\n{dossier}"
        )
        root.destroy()
        return

    # Chercher le dossier de logs (peut être au même niveau ou dans un sous-dossier 'logs')
    logs_dir = dossier / 'logs' if (dossier / 'logs').exists() else dossier.parent / 'logs'

    from bibile.database import import_xlsx_file

    nb_importes = 0
    for xlsx_file in fichiers_xlsx:
        # Chercher le log correspondant
        timestamp_str = xlsx_file.stem.replace('Enlevements_', '')
        log_file = logs_dir / f"log_{timestamp_str}.md" if logs_dir.exists() else None
        if log_file and not log_file.exists():
            log_file = None

        result = import_xlsx_file(db_path, xlsx_file, log_file)
        if result is not None:
            nb_importes += 1

    messagebox.showinfo(
        "Import terminé",
        f"{nb_importes} fichier(s) importé(s) sur {len(fichiers_xlsx)} trouvé(s)."
    )

    root.destroy()


def main():
    # 1. Preparer le dossier de donnees
    data_dir = get_data_dir()
    data_dir.mkdir(exist_ok=True)
    (data_dir / 'historique').mkdir(exist_ok=True)
    (data_dir / 'logs').mkdir(exist_ok=True)
    os.environ['BIBILE_DATA_DIR'] = str(data_dir)

    # 2. Initialiser la base de donnees SQLite
    db_path = data_dir / 'bibile.db'
    from bibile.database import init_db, list_extractions
    init_db(db_path)
    os.environ['BIBILE_DB_PATH'] = str(db_path)

    # 3. Premier lancement ? Proposer l'import de l'ancien historique
    #    On utilise un fichier marqueur pour ne poser la question qu'une seule fois
    first_launch_marker = data_dir / '.import_done'
    if not first_launch_marker.exists():
        import_ancien_historique(db_path)
        first_launch_marker.write_text('ok')

    # 4. Trouver un port libre
    port = find_free_port()
    os.environ['BIBILE_PORT'] = str(port)

    # 5. Importer Flask (apres avoir set les env vars)
    from bibile.server import app, init_sync_manager
    import bibile.server as server_module

    # 5b. Demarrer le SyncManager (synchro BDD externe)
    try:
        init_sync_manager()
    except Exception as e:
        print(f"Note: SyncManager non demarre ({e})")

    # 5c. Verifier les mises a jour en arriere-plan
    def background_update_check():
        try:
            from bibile.updater import check_for_update
            from bibile.version import __version__
            result = check_for_update(__version__)
            if result:
                server_module.update_available = result
                print(f"Mise a jour disponible: v{result['version']}")
        except Exception as e:
            print(f"Note: check update echoue ({e})")

    threading.Thread(target=background_update_check, daemon=True).start()

    # 6. Demarrer Flask dans un thread daemon
    def start_flask():
        app.run(host='127.0.0.1', port=port, debug=False, use_reloader=False)

    flask_thread = threading.Thread(target=start_flask, daemon=True)
    flask_thread.start()

    # 7. Attendre que Flask soit pret
    if not wait_for_server(port):
        print(f"Erreur: le serveur Flask n'a pas demarre sur le port {port}")
        sys.exit(1)

    # 8. Ouvrir la fenetre pywebview (Edge Chromium requis pour le CSS moderne)
    import webview
    window = webview.create_window(
        'Bibile',
        f'http://127.0.0.1:{port}',
        width=1400,
        height=900,
        min_size=(1000, 700),
    )
    try:
        webview.start(gui='edgechromium')
    except Exception:
        # Fallback si edgechromium non disponible
        print("WebView2 (Edge Chromium) non disponible, fallback par defaut.")
        print("Pour un rendu optimal, installez WebView2: https://developer.microsoft.com/en-us/microsoft-edge/webview2/")
        webview.start()


if __name__ == '__main__':
    main()
