# BIBILE - Bible de Tri des Enlevements Hillebrand

## Architecture

Application desktop (pywebview + Flask) pour extraire les donnees d'enlevements depuis du texte PDF Hillebrand, generer des fichiers Excel, et gerer des tournees de livraison.

```
main.py                # Entry point desktop (pywebview + Flask en thread + init DB + SyncManager + update check)
bibile/
  server.py            # Backend Flask (logique metier + routes API + routes update + routes EDI)
  database.py          # Module SQLite (stockage extractions + enlevements + schema tournees)
  database_tournees.py # CRUD tournees, chauffeurs, vehicules, zones, synchro, config Drakkar
  external_sync.py     # SyncManager (thread daemon, connexion BDD externe SQL Server Azure)
  edi_sync.py          # Connexion Drakkar (SQL Express), fetch + parse XML EDI Hillebrand
  edi_comparator.py    # Comparaison EDI vs PDF (rapprochement, ecarts)
  updater.py           # Systeme de mise a jour automatique depuis GitHub Releases
  version.py           # Version unique de l'application (__version__)
  templates/
    base.html          # Template de base (sidebar + layout dark theme + banniere mise a jour)
    index.html         # Page d'accueil (extraction)
    donnees.html       # Visualisation des donnees
    tournees.html      # Kanban + carte des tournees + geolocalisation vehicules
    edi.html            # Page comparaison EDI vs PDF
    gestion.html       # Gestion utilisateur (zones, chauffeurs, vehicules, mapping villes)
    parametres.html    # Parametres systeme (connexion externe DBI, connexion Drakkar EDI)
    statistiques.html  # Page statistiques (filtres periode/livraison/zone, exports PDF/Excel)
    historique.html    # Historique des fichiers
    aide.html          # Aide / documentation
  static/
    css/style.css      # Dark theme (inspire SOCIALIS)
    css/leaflet.css    # Leaflet CSS (local)
    js/app.js          # JS page accueil
    js/donnees.js      # JS page donnees
    js/historique.js   # JS page historique
    js/statistiques.js # JS page statistiques (Chart.js, filtres, exports PDF/Excel)
    js/edi.js          # JS page EDI (comparaison, tri colonnes)
    js/tournees.js     # JS Kanban (SortableJS)
    js/carte.js        # JS carte (Leaflet) + couche vehicules GPS
    js/gestion.js      # JS gestion (zones, chauffeurs, vehicules, mapping, autocomplete tournees)
    js/parametres.js   # JS parametres (config BDD externe + Drakkar)
    js/sortable.min.js # SortableJS (local)
    js/leaflet.min.js  # Leaflet JS (local)
bibile.spec            # Config PyInstaller (inclut pymssql, pymupdf)
build.bat              # Script de build .exe + creation ZIP release
```

## Mode desktop

- `main.py` demarre Flask dans un thread daemon, puis ouvre une fenetre native via pywebview
- **pywebview utilise le backend `edgechromium` (WebView2)** avec fallback automatique — requis pour CSS moderne (variables, flexbox). Sur Windows Server 2022, installer WebView2 Runtime manuellement.
- En mode PyInstaller bundle : templates/static depuis `sys._MEIPASS`, donnees dans `%APPDATA%/Bibile/`
- En mode dev : donnees dans `bibile/` (comportement original)
- Variable d'environnement `BIBILE_DATA_DIR` controle le dossier de donnees
- Variable d'environnement `BIBILE_DB_PATH` controle le chemin de la base SQLite
- Le SyncManager demarre automatiquement au lancement pour la synchro BDD externe
- Un thread background verifie les mises a jour GitHub au demarrage

## Mise a jour automatique (GitHub Releases)

- **`bibile/version.py`** : source unique de verite pour la version (`__version__`)
- **`bibile/updater.py`** : verifie `https://api.github.com/repos/THBORDIER/bibile/releases/latest`
- Au lancement, thread background compare le tag GitHub avec `__version__`
- Si une version plus recente existe : banniere bleue dans `base.html` sur toutes les pages
- Clic "Installer" : telecharge le ZIP, lance `update.bat` (attend fermeture PID, Expand-Archive, relance exe)
- Routes API : `GET /api/update/check`, `POST /api/update/apply`, `GET /api/update/debug`
- Le apply refuse de s'executer en mode dev (`sys._MEIPASS` absent)

### Workflow de release

1. Modifier `bibile/version.py` → nouvelle version
2. `build.bat` → produit `dist/Bibile/Bibile.exe` + `dist/Bibile.zip`
3. `gh release create v3.7.0 dist/Bibile.zip --title "v3.7.0" --notes "Changelog"`

## Connexion Drakkar (EDI SQL Express local)

- **`bibile/edi_sync.py`** : connexion a `sv-drakkar\sqlexpress:49372` (SQL Express local)
- Client cible : JF HILLEBRAND TRANSIT (alias `HILL21BEAU`)
- Tables Drakkar : `[dbo].[ti]` (clients), `[dbo].[edi_atlas400]` (messages EDI)
- Jointure : `edi_atlas400.Code_Indus = ti.N_tiers`
- Champ `SourceCNX` : XML Hillebrand Transport Instructions (namespace `http://JFH.Interfaces2013.Schemas.Schemas.HillebrandTransportInstructionsMessage_2.0`)
- Parse XML : extrait shipments avec expediteur, colis, palettes, poids, dates, destinations
- Deduplication : si un meme `shipment_id` apparait dans plusieurs messages EDI (MAJ en journee), seul le plus recent est conserve
- Connexion pyodbc (TrustServerCertificate=yes) avec fallback pymssql
- Fix double-encodage UTF-8 : `text.encode('latin-1').decode('utf-8')` pour NTEXT pyodbc
- **`bibile/edi_comparator.py`** : rapprochement EDI vs PDF par `num_enlevement`/`RefMessage`
- Config stockee dans table `external_db_config` avec `nom='drakkar'`
- Donnees fetched live (pas de cache local) — chaque requete interroge Drakkar directement
- Routes API : `GET/POST /api/drakkar/config`, `POST /api/drakkar/test`, `GET /api/drakkar/edi`, `GET /api/drakkar/stats`, `GET /api/drakkar/compare`, `GET /api/drakkar/compare/export`

## Connexion BDD externe (DBI SQL Server Azure)

- **`bibile/external_sync.py`** : SyncManager avec pymssql
- Connexion Azure SQL : TDS version 7.3 obligatoire, format utilisateur `user@servername`
- Synchro vehicules depuis DBI : `GET /api/external-db/vehicules`
- Positions GPS live : `GET /api/vehicles/positions` (interroge table DBI)
- Donnees transport (km, conso, duree) : synchro periodique
- Config stockee dans table `external_db_config` (SQLite locale)
- Parametres par defaut : SQL Server, port 1433

## Base de donnees SQLite

- Fichier : `bibile.db` dans le dossier de donnees (WAL mode active)
- Table `extractions` : metadonnees (nom_fichier, date, nb_lignes, log_contenu)
- Table `enlevements` : donnees des enlevements (liees a une extraction par FK)
- Table `chauffeurs` : chauffeurs locaux + synchro externe (externe_id)
- Table `vehicules` : vehicules (immatriculation, type, capacite)
- Table `tournee_modeles` : modeles de tournees permanentes (nom, chauffeur_id, vehicule_id, ordre_tri, actif, couleur)
- Table `tournees` : tournees instanciees par jour (nom, date, chauffeur, vehicule, statut, modele_id FK, couleur)
- Table `tournee_enlevements` : liaison N-N entre tournees et enlevements (avec ordre)
- Table `zones` : zones geographiques (nom, tournee_defaut, couleur)
- Table `ville_zone_mapping` : mapping ville -> zone (+ coordonnees GPS)
- Table `edi_messages` : messages EDI caches (id_ligne, source_cnx, date_sync)
- Table `external_db_config` : configuration connexion BDD externe + Drakkar (nom='drakkar')
- Table `chauffeurs_sync` : selection des chauffeurs a synchroniser
- Table `donnees_transport` : donnees synchro (km, conso, duree par jour) — colonnes ajoutees par migration ALTER TABLE
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
- `inject_version()` - Context processor Jinja injectant `version` dans tous les templates
- `page_gestion()` - Route `/gestion` (page gestion utilisateur)
- `api_tournee_noms()` - Route `GET /api/tournees/noms` (noms distincts pour autocomplete)
- `api_statistiques_export()` - Route `GET /api/statistiques/export` (export Excel des stats, openpyxl)

## Fonctions cles (database_tournees.py)

- `list_tournees(db_path, date)` - Liste tournees + enlevements pour une date
- `auto_distribuer(db_path, date, extraction_id)` - Repartition auto par ville/zone (appelle instancier_tournees)
- `get_unassigned_enlevements(db_path, ...)` - Enlevements non assignes a une tournee
- `get_villes_inconnues(db_path)` - Villes sans mapping zone
- `list_modeles(db_path)` - Liste modeles de tournees actifs
- `save_modele(db_path, data)` - Creer/modifier un modele
- `delete_modele(db_path, modele_id)` - Soft delete (actif=0)
- `instancier_tournees(db_path, date)` - Cree les tournees du jour depuis les modeles actifs

## Pages Gestion vs Parametres

L'interface separe les donnees operationnelles de la configuration systeme :

- **Gestion** (`/gestion`, `gestion.html`, `gestion.js`) : donnees utilisateur modifiees regulierement
  - Onglet "Zones & Villes" : zones geographiques, mapping ville→zone, geocodage, tournee par defaut
  - Onglet "Chauffeurs & Vehicules" : CRUD chauffeurs et vehicules locaux
  - Onglet "Tournees" : modeles de tournees permanentes (nom, chauffeur/vehicule par defaut, couleur)
  - Autocomplete `tournee_defaut` via `GET /api/tournees/noms` (datalist HTML)

- **Parametres** (`/parametres`, `parametres.html`, `parametres.js`) : configuration systeme rarement modifiee
  - Onglet "Connexion externe" : config BDD Azure SQL (DBI), synchro vehicules, intervalle
  - Onglet "Connexion Drakkar" : config SQL Express local (EDI)

Le champ `tournee_defaut` existe a deux niveaux : sur la zone (defaut) et sur le mapping ville (surcharge). Lors de l'auto-distribution, la tournee de la ville prime sur celle de la zone.

## Modeles de tournees (tournees permanentes)

- Table `tournee_modeles` : tournees permanentes avec chauffeur/vehicule par defaut
- Soft delete via `actif=0` (les modeles ne sont jamais supprimes physiquement)
- **Instanciation automatique** : au chargement de la page tournees (`GET /api/tournees?date=`), les modeles actifs sont instancies en tournees du jour si pas deja presentes. Meme chose avant auto-distribution.
- La table `tournees` a une colonne `modele_id` (FK) pour tracer l'origine d'une tournee instanciee
- Les tournees passees sont conservees en historique (navigables via le date picker)
- Routes API : `GET /api/tournee-modeles`, `POST /api/tournee-modeles`, `DELETE /api/tournee-modeles/<id>`

## Page Statistiques

- 5 cartes totaux (extractions, enlevements, palettes, poids, colis)
- 6 graphiques Chart.js : 2 donuts (livraison, palettes), 2 barres (poids, colis), 1 ligne evolution, 1 barre top 10 societes
- **Filtres** : periode (tout/aujourd'hui/semaine/mois/custom), livraison, zone geographique
- **Export PDF** : `window.print()` avec CSS `@media print` (masque sidebar, fond blanc)
- **Export Excel** : route `GET /api/statistiques/export?date_debut=&date_fin=&livraison=&zone=` (openpyxl, 4 feuilles)
- `get_statistiques(db_path, date_debut, date_fin, livraison, zone)` dans `database.py` — supporte filtres livraison et zone (JOIN ville_zone_mapping)
- Chart.js charge depuis `/static/js/chart.min.js` (local, 202 KB)

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

# Builder le .exe + ZIP release
build.bat
# ou: pyinstaller bibile.spec --clean

# Creer une release GitHub
gh release create v3.7.0 dist/Bibile.zip --title "v3.7.0" --notes "Changelog"
```

## Donnees de test

- `Date 06fevr.2026 0906.txt` - 38 enlevements, 4 livraisons
- `Date 10fevr.2026.txt` - 36 enlevements, 4 livraisons

## Problemes connus

- **Windows Server 2022** : pywebview tombe en fallback MSHTML (IE) si WebView2 Runtime n'est pas installe → CSS casse. Solution : installer WebView2 Runtime depuis https://developer.microsoft.com/en-us/microsoft-edge/webview2/
- **Azure SQL firewall** : l'IP du poste doit etre whitelistee dans Azure Portal pour la connexion DBI
