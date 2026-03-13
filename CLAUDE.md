# BIBILE - Bible de Tri des Enlevements Hillebrand

## Architecture

Application desktop (pywebview + Flask) pour extraire les donnees d'enlevements depuis du texte PDF Hillebrand, generer des fichiers Excel, et gerer des tournees de livraison.

```
main.py                # Entry point desktop (pywebview + Flask en thread + init DB + SyncManager)
bibile/
  server.py            # Backend Flask (logique metier + routes API)
  database.py          # Module SQLite (stockage extractions + enlevements + schema tournees)
  database_tournees.py # CRUD tournees, chauffeurs, vehicules, zones, synchro
  external_sync.py     # SyncManager (thread daemon, connexion BDD externe)
  templates/
    base.html          # Template de base (sidebar + layout dark theme)
    index.html         # Page d'accueil (extraction)
    donnees.html       # Visualisation des donnees
    tournees.html      # Kanban + carte des tournees
    parametres.html    # Parametres (zones, chauffeurs, vehicules, connexion externe)
    statistiques.html  # Page statistiques
    historique.html    # Historique des fichiers
    aide.html          # Aide / documentation
  static/
    css/style.css      # Dark theme (inspire SOCIALIS)
    css/leaflet.css    # Leaflet CSS (local)
    js/app.js          # JS page accueil
    js/donnees.js      # JS page donnees
    js/historique.js   # JS page historique
    js/statistiques.js # JS page statistiques
    js/tournees.js     # JS Kanban (SortableJS)
    js/carte.js        # JS carte (Leaflet)
    js/parametres.js   # JS parametres
    js/sortable.min.js # SortableJS (local)
    js/leaflet.min.js  # Leaflet JS (local)
bibile.spec            # Config PyInstaller
build.bat              # Script de build .exe
```

## Mode desktop

- `main.py` demarre Flask dans un thread daemon, puis ouvre une fenetre native via pywebview
- En mode PyInstaller bundle : templates/static depuis `sys._MEIPASS`, donnees dans `%APPDATA%/Bibile/`
- En mode dev : donnees dans `bibile/` (comportement original)
- Variable d'environnement `BIBILE_DATA_DIR` controle le dossier de donnees
- Variable d'environnement `BIBILE_DB_PATH` controle le chemin de la base SQLite
- Le SyncManager demarre automatiquement au lancement pour la synchro BDD externe

## Base de donnees SQLite

- Fichier : `bibile.db` dans le dossier de donnees (WAL mode active)
- Table `extractions` : metadonnees (nom_fichier, date, nb_lignes, log_contenu)
- Table `enlevements` : donnees des enlevements (liees a une extraction par FK)
- Table `chauffeurs` : chauffeurs locaux + synchro externe (externe_id)
- Table `vehicules` : vehicules (immatriculation, type, capacite)
- Table `tournees` : tournees planifiees (nom, date, chauffeur, vehicule, statut)
- Table `tournee_enlevements` : liaison N-N entre tournees et enlevements (avec ordre)
- Table `zones` : zones geographiques (nom, tournee_defaut, couleur)
- Table `ville_zone_mapping` : mapping ville -> zone (+ coordonnees GPS)
- Table `external_db_config` : configuration connexion BDD externe
- Table `chauffeurs_sync` : selection des chauffeurs a synchroniser
- Table `donnees_transport` : donnees synchro (km, conso, duree par jour)
- Au premier lancement, dialogue tkinter propose d'importer l'ancien historique (fichiers .xlsx)
- Les fichiers Excel restent generes pour le telechargement, la DB est la source de verite

## Fonctions cles (server.py)

- `nettoyer_texte(texte)` - Pre-traitement : supprime les en-tetes/pieds de page PDF repetes
- `extraire_totaux_livraisons(texte)` - Extrait totaux livraisons + mapping destinataires
- `controler_totaux(...)` - Controle qualite (compare extrait vs attendu)
- `extraire_info_enlevement(lignes, index, mapping)` - Extraction d'un enlevement
- `parser_texte(texte, log_file)` - Orchestrateur principal
- `generer_excel(lignes, nom, log_file)` - Generation Excel avec openpyxl
- `init_sync_manager()` - Demarre le SyncManager pour la synchro BDD externe

## Fonctions cles (database_tournees.py)

- `list_tournees(db_path, date)` - Liste tournees + enlevements pour une date
- `auto_distribuer(db_path, date, extraction_id)` - Repartition auto par ville/zone
- `get_unassigned_enlevements(db_path, ...)` - Enlevements non assignes a une tournee
- `get_villes_inconnues(db_path)` - Villes sans mapping zone

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
