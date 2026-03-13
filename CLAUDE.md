# BIBILE - Bible de Tri des Enlevements Hillebrand

## Architecture

Application desktop (pywebview + Flask) pour extraire les donnees d'enlevements depuis du texte PDF Hillebrand et generer des fichiers Excel.

```
main.py                # Entry point desktop (pywebview + Flask en thread + init DB)
bibile/
  server.py            # Backend Flask (logique metier + routes API)
  database.py          # Module SQLite (stockage extractions + enlevements)
  templates/
    base.html          # Template de base (sidebar + layout dark theme)
    index.html         # Page d'accueil (extraction)
    donnees.html       # Visualisation des donnees
    historique.html    # Historique des fichiers
    aide.html          # Aide / documentation
  static/
    css/style.css      # Dark theme (inspire SOCIALIS)
    js/app.js          # JS page accueil
    js/donnees.js      # JS page donnees
    js/historique.js   # JS page historique
bibile.spec            # Config PyInstaller
build.bat              # Script de build .exe
```

## Mode desktop

- `main.py` demarre Flask dans un thread daemon, puis ouvre une fenetre native via pywebview
- En mode PyInstaller bundle : templates/static depuis `sys._MEIPASS`, donnees dans `%APPDATA%/Bibile/`
- En mode dev : donnees dans `bibile/` (comportement original)
- Variable d'environnement `BIBILE_DATA_DIR` controle le dossier de donnees
- Variable d'environnement `BIBILE_DB_PATH` controle le chemin de la base SQLite

## Base de donnees SQLite

- Fichier : `bibile.db` dans le dossier de donnees
- Table `extractions` : metadonnees (nom_fichier, date, nb_lignes, log_contenu)
- Table `enlevements` : donnees des enlevements (liees a une extraction par FK)
- Au premier lancement, dialogue tkinter propose d'importer l'ancien historique (fichiers .xlsx)
- Les fichiers Excel restent generes pour le telechargement, la DB est la source de verite

## Fonctions cles (server.py)

- `nettoyer_texte(texte)` - Pre-traitement : supprime les en-tetes/pieds de page PDF repetes
- `extraire_totaux_livraisons(texte)` - Extrait totaux livraisons + mapping destinataires
- `controler_totaux(...)` - Controle qualite (compare extrait vs attendu)
- `extraire_info_enlevement(lignes, index, mapping)` - Extraction d'un enlevement
- `parser_texte(texte, log_file)` - Orchestrateur principal
- `generer_excel(lignes, nom, log_file)` - Generation Excel avec openpyxl

## Types de palettes

| Type | Comptage Excel | Comptage QC |
|------|---------------|-------------|
| PART PALLET | 0 | Non compte |
| HALF PALLET | 1 | Non compte |
| EURO | Nombre indique | Compte |
| VMF | Nombre indique | Compte |
| LOOSE LOADED | Nombre indique | Compte |

## Commandes

```bash
# Lancer l'app desktop (mode dev)
python main.py

# Lancer Flask seul (mode navigateur, debug)
python bibile/server.py

# Lancer les tests
python test_full_process.py
python test_dynamic_mapping.py
python test_bug_fixes.py

# Builder le .exe
build.bat
# ou: pyinstaller bibile.spec --clean
```

## Donnees de test

- `Date 06fevr.2026 0906.txt` - 38 enlevements, 4 livraisons
- `Date 10fevr.2026.txt` - 36 enlevements, 4 livraisons
