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
    tournees.html      # Kanban + feuille de route + carte des tournees (source EDI)
    edi.html            # Page comparaison EDI vs PDF
    facturation.html   # Generation fichier facturation Hillebrand (.xlsx)
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
    js/edi.js          # JS page EDI (comparaison auto, recherche libre, historique modifications, tri colonnes)
    js/facturation.js  # JS page facturation (chargement, tableau editable, generation Excel)
    js/tournees.js     # JS Kanban + Feuille de route + sync EDI (SortableJS)
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
- Connexion pyodbc (TrustServerCertificate=yes) avec fallback pymssql (TDS 7.0 obligatoire pour pymssql)
- **pymssql** : ne gere pas les instances nommees (`host\instance`), le code extrait le hostname seul car le port est explicite
- **Prerequis poste client** : pas de driver ODBC requis, pymssql suffit. Si ODBC Driver 17/18 est present, pyodbc est utilise en priorite
- Fix double-encodage UTF-8 : `text.encode('latin-1').decode('utf-8')` pour NTEXT pyodbc
- **`bibile/edi_comparator.py`** : rapprochement EDI vs PDF par scoring multi-criteres (nom fuzzy, ville, poids, reference croisee)
- **IMPORTANT** : le rapprochement se fait TOUJOURS par **reference** (ex: `USRF41070`, `FRBC78660`) et JAMAIS par numero d'enlevement (compteur incremental interne au PDF, sans valeur de rapprochement)
- Config stockee dans table `external_db_config` avec `nom='drakkar'`
- Donnees fetched live (pas de cache local) — chaque requete interroge Drakkar directement
- Historique EDI : `fetch_edi_parsed()` conserve toutes les versions par `shipment_id` (`_edi_history`), affichees dans un modal avec surbrillance des champs modifies
- Deduplication PDF pour la comparaison : prend l'extraction principale (plus d'entrees pour la date), puis ajoute les supplements non couverts — evite les doublons entre PDFs unitaires et PDF principal
- Routes API : `GET/POST /api/drakkar/config`, `POST /api/drakkar/test`, `GET /api/drakkar/edi`, `GET /api/drakkar/stats`, `GET /api/drakkar/compare`, `GET /api/drakkar/compare/export`, `GET /api/enlevements/history`

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
- Table `enlevements_history` : historique des modifications (source 'pdf' ou 'edi', changed_at, anciennes valeurs)
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
- `_parse_single_enlevement(lignes, log_file)` - Fallback pour PDF "Instructions d'enlevement" (format unique)
- `parser_texte(texte, log_file)` - Orchestrateur principal (essaie multi-enlevements, fallback single)
- `generer_excel(lignes, nom, log_file)` - Generation Excel avec openpyxl
- `init_sync_manager()` - Demarre le SyncManager pour la synchro BDD externe
- `inject_version()` - Context processor Jinja injectant `version` dans tous les templates
- `page_gestion()` - Route `/gestion` (page gestion utilisateur)
- `api_tournee_noms()` - Route `GET /api/tournees/noms` (noms distincts pour autocomplete)
- `api_statistiques_export()` - Route `GET /api/statistiques/export` (export Excel des stats, openpyxl)
- `api_sync_edi()` - Route `POST /api/tournees/sync-edi` (fetch EDI Drakkar → enlevements SQLite)

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

## Source EDI pour les tournees (v4.0.0)

- **Depuis v4.0.0**, la page tournees utilise l'EDI Drakkar comme source unique des enlevements (plus le PDF)
- Route `POST /api/tournees/sync-edi` : fetch EDI Drakkar → filtre par `pickup_date` → insere dans table `enlevements`
- Extraction speciale `EDI_YYYY-MM-DD` creee automatiquement dans la table `extractions`
- Mapping `delivery_name` → livraison : TRANSIT, CHEVROLET, BREVET, GREFFAGE, HILLEBRAND
- Les enlevements deja assignes a des tournees sont preserves lors du re-sync
- Le dropdown "Extraction" a ete remplace par un badge "Source EDI" dans la toolbar
- **Ancien code PDF archive** (commente) dans `tournees.js` et `tournees.html` au cas ou
- Matching ville case-insensitive dans `auto_distribuer()` : `.upper()` pour compatibilite EDI (casse mixte)

## Feuille de route

- Vue "Feuille de route" dans la page tournees : un tableau par tournee, format identique au fichier Excel utilisateur
- Header : date, chauffeur, camion, telephone
- Colonnes : N, REF, CLIENT, VILLE, PALS, TYPE, POIDS, COLIS, DESTINATION, OBSERVATION
- Observations editables inline (click-to-edit, sauvegarde via `PUT /api/tournee-enlevements/<id>/observation`)
- Ajout/edition d'enlevements manuels via modal (extraction "Manuel" auto-creee)
- Impression par tournee via `window.print()`

## Page Comparaison EDI (`/edi`)

- Chargement automatique au changement de date (pas de bouton "Comparer")
- Onglets : Enlevements T01 | Autres transports T02+
- Recherche libre en temps reel sur reference, societe PDF, societe EDI
- Stats en haut : nb PDF, nb EDI, correspondances, ecarts, taux %
- Tableau : statut (OK/Ecart/PDF seul/EDI seul), refs, societes, score matching, palettes/poids/colis
- Bouton historique 🕓 sur les refs ayant des modifications EDI reelles (champs differents entre versions)
- Modal historique : toutes versions chronologiques, champs modifies en vert, version actuelle marquee
- Export Excel de la comparaison
- Debug info (nb shipments, dates, sources)

## Page Statistiques

- 5 cartes totaux (extractions, enlevements, palettes, poids, colis)
- 6 graphiques Chart.js : 2 donuts (livraison, palettes), 2 barres (poids, colis), 1 ligne evolution, 1 barre top 10 societes
- **Filtres** : periode (tout/aujourd'hui/semaine/mois/custom), livraison, zone geographique
- **Export PDF** : `window.print()` avec CSS `@media print` (masque sidebar, fond blanc)
- **Export Excel** : route `GET /api/statistiques/export?date_debut=&date_fin=&livraison=&zone=` (openpyxl, 4 feuilles)
- `get_statistiques(db_path, date_debut, date_fin, livraison, zone)` dans `database.py` — supporte filtres livraison et zone (JOIN ville_zone_mapping)
- Chart.js charge depuis `/static/js/chart.min.js` (local, 202 KB)

## Page Facturation

- Generation automatique du fichier de facturation Hillebrand au format .xlsx
- Pre-remplissage depuis les enlevements PDF extraits pour une date donnee
- Mapping livraison → destinataire/tournee/PAQ :
  - BREVET → "BREVET Transports" / "HILLEBRAND CHATENOY" / PAQ=0
  - TRANSIT → "HILLEBRAND TRANSIT CHEVROLLET" / "HILLEBRAND TRANSIT" / PAQ=1
  - CHEVROLET/STORAGE → "HILLEBRAND CHEVROLLET STOCKAGE" / "HILLEBRAND CHEVROLET" / PAQ=1
  - PAQ adapte selon la tournee reelle assignee (CHATENOY=0, TRANSIT/CHEVROLET=1)
- Reference (Ref.cli.2) = reference enlevement sans suffixe /T01
- Champs editables inline : N° recep., Origine, Dpt., CP dest., Localite dest., Dpt.2, PEC, LIV, PAQ, CA Trs.
- Champs pre-remplis non editables : Expediteur, Destinataire, Tournee, U.M., Colis, Poids, Ref.cli.1, Ref.cli.2
- Champs a remplir plus tard : N° recep. (interne Brevet), CA Trs. (tarif transport)
- Routes API : `GET /api/facturation/charger?date=&ref=`, `POST /api/facturation/generer`

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

## Circuit utilisateur et correlation des donnees

Le circuit actuel de l'utilisateur Benjamin est : **PDF → Excel (manuel)**. L'EDI n'est pas utilise directement, il sert de controle/verification.

1. **PDF Hillebrand** : fichier "Instructions de transport" recu quotidiennement, contient tous les enlevements du jour
2. **Excel utilisateur** : fichier `HILLEBRAND RAMASSE LOCALE MATRISSE.xlsx` avec un onglet par vehicule (ex: GL-530-TV, HE-097-ZH), rempli manuellement depuis le PDF
3. **EDI Drakkar** : messages XML recus en continu, mis a jour au fil de l'eau (dizaines de MAJ/jour)

### Formats PDF supportes

- **Multi-enlevements** : "Instructions de transport" avec "Enlèvement 1", "Enlèvement 2"... (format principal)
- **Enlevement unique** : "Instructions d'enlèvement" sans numerotation (format secondaire, fallback via `_parse_single_enlevement()`)
- Import batch de plusieurs PDFs simultanes (timestamp avec microsecondes `_%f` pour eviter collisions UNIQUE)

### Identifiants et rapprochement

- **Reference** (ex: `USRF41070`, `FRBC78660`, `CCG006696`) : identifiant unique d'un shipment, utilise pour TOUT rapprochement (PDF↔Excel, PDF↔EDI)
- **Numero d'enlevement** (ex: #1, #2... #25) : compteur incremental interne au PDF, **AUCUNE valeur** pour le rapprochement — ne JAMAIS utiliser pour matcher
- **transaction_ref EDI** = reference + suffixe `/T01`, `/T02` etc. (T01 = enlevement, T02+ = autres transports)
- **shipment_id EDI** = reference sans suffixe (identique a la reference PDF de base)

### Correlation verifiee (18/03/2026)

| Source → Cible | Taux | Details |
|----------------|------|---------|
| Excel → PDF | 86% (32/37) | 5 ecarts : 1 typo (`CNK0550164`), 2 refs Hillebrand absentes du PDF, 1 ajout manuel, 1 ref non extraite |
| Excel → EDI | 95% (35/37) | 2 absentes : `FRXA83426` (ajout manuel), `FRXA83404` (non trouvee) |
| PDF → EDI | ~91% | Via page comparaison, scoring multi-criteres |

### Structure du fichier Excel utilisateur

- Onglet par vehicule/remorque (ex: `GL-530-TV`, `HE-097-ZH`, `SEMI TRADI`)
- En-tete : date, chauffeur, camion, remorque, telephone
- Colonnes : N°, REF, CLIENT, VILLE, PALS, TYPE, POIDS, COLIS, DESTINATION, OBSERVATION
- Section "DEUXIEME TOUR" en bas de chaque onglet
- Ligne TOTAL avec sommes palettes/poids/colis
- Onglet `FICHE CONDUCTEUR` avec coordonnees chauffeurs

### Noms de societes : differences PDF vs EDI

Le PDF utilise le nom usuel (ex: "MAISON ANDRE GOICHOT"), l'EDI le nom officiel de l'expediteur (ex: "Nos Vins du Sud SAS"). Le rapprochement gere ca via fuzzy matching (SequenceMatcher ratio >= 0.6).

## Donnees de test

- `donnees/Date 06fevr.2026 0906.txt` - 38 enlevements, 4 livraisons
- `donnees/Date 10fevr.2026.txt` - 36 enlevements, 4 livraisons
- `test17032026/HILLEBRAND RAMASSE LOCALE MATRISSE.xlsx` - fichier Excel utilisateur de reference (GL-530-TV + HE-097-ZH, 37 refs, 18/03/2026)

## Problemes connus

- **Windows Server 2022** : pywebview tombe en fallback MSHTML (IE) si WebView2 Runtime n'est pas installe → CSS casse. Solution : installer WebView2 Runtime depuis https://developer.microsoft.com/en-us/microsoft-edge/webview2/
- **Azure SQL firewall** : l'IP du poste doit etre whitelistee dans Azure Portal pour la connexion DBI
