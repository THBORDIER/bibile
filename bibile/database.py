#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bibile - Module base de données SQLite

Gère le stockage des extractions et enlèvements dans une base SQLite locale.
Remplace le stockage fichier Excel pour l'historique (les Excel restent générés pour le téléchargement).
"""

import sqlite3
from pathlib import Path
from datetime import datetime
import pandas as pd


# Mapping colonnes DB → noms affichés (avec accents, pour compatibilité JS)
COLONNES_DISPLAY = [
    'N° ENLÈVEMENT',
    'NOTRE RÉFÉRENCE',
    'SOCIÉTÉ / DOMAINE',
    'VILLE',
    'NOMBRE DE PALETTES',
    'TYPE DE PALETTES',
    'POIDS TOTAL (KG)',
    'NOMBRE DE COLIS',
    'LIVRAISON ASSOCIÉE',
    'TÉLÉPHONE',
]

COLONNES_DB = [
    'num_enlevement',
    'reference',
    'societe',
    'ville',
    'nb_palettes',
    'type_palettes',
    'poids_total',
    'nb_colis',
    'livraison',
    'telephone',
]


def get_db(db_path):
    """Retourne une connexion SQLite avec foreign keys activées et WAL mode."""
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path):
    """Crée les tables si elles n'existent pas."""
    conn = get_db(db_path)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS extractions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nom_fichier TEXT NOT NULL UNIQUE,
            date_creation TEXT NOT NULL,
            nb_lignes INTEGER NOT NULL DEFAULT 0,
            log_contenu TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS enlevements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            extraction_id INTEGER NOT NULL REFERENCES extractions(id) ON DELETE CASCADE,
            num_enlevement INTEGER,
            reference TEXT,
            societe TEXT,
            ville TEXT,
            nb_palettes REAL DEFAULT 0,
            type_palettes TEXT,
            poids_total REAL DEFAULT 0,
            nb_colis REAL DEFAULT 0,
            livraison TEXT,
            telephone TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_enlevements_extraction ON enlevements(extraction_id);
        CREATE INDEX IF NOT EXISTS idx_enlevements_ville ON enlevements(ville);

        -- Chauffeurs (locaux + synchro externe)
        CREATE TABLE IF NOT EXISTS chauffeurs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nom TEXT NOT NULL,
            prenom TEXT,
            telephone TEXT,
            externe_id TEXT UNIQUE,
            actif INTEGER DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        -- Vehicules
        CREATE TABLE IF NOT EXISTS vehicules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            immatriculation TEXT NOT NULL UNIQUE,
            type_vehicule TEXT,
            capacite_palettes INTEGER DEFAULT 0,
            externe_id TEXT UNIQUE,
            actif INTEGER DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        -- Tournees
        CREATE TABLE IF NOT EXISTS tournees (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nom TEXT NOT NULL,
            date_tournee TEXT NOT NULL,
            chauffeur_id INTEGER REFERENCES chauffeurs(id),
            vehicule_id INTEGER REFERENCES vehicules(id),
            statut TEXT DEFAULT 'brouillon',
            ordre_tri INTEGER DEFAULT 0,
            notes TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_tournees_date ON tournees(date_tournee);

        -- Liaison tournee <-> enlevements
        CREATE TABLE IF NOT EXISTS tournee_enlevements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tournee_id INTEGER NOT NULL REFERENCES tournees(id) ON DELETE CASCADE,
            enlevement_id INTEGER NOT NULL REFERENCES enlevements(id) ON DELETE CASCADE,
            ordre INTEGER DEFAULT 0,
            UNIQUE(tournee_id, enlevement_id)
        );
        CREATE INDEX IF NOT EXISTS idx_te_tournee ON tournee_enlevements(tournee_id);
        CREATE INDEX IF NOT EXISTS idx_te_enlevement ON tournee_enlevements(enlevement_id);

        -- Modeles de tournees (permanents)
        CREATE TABLE IF NOT EXISTS tournee_modeles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nom TEXT NOT NULL,
            chauffeur_id INTEGER REFERENCES chauffeurs(id),
            vehicule_id INTEGER REFERENCES vehicules(id),
            ordre_tri INTEGER DEFAULT 0,
            actif INTEGER DEFAULT 1,
            couleur TEXT DEFAULT '#4493f8',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        -- Zones geographiques
        CREATE TABLE IF NOT EXISTS zones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nom TEXT NOT NULL UNIQUE,
            tournee_defaut TEXT,
            couleur TEXT DEFAULT '#4493f8',
            priorite INTEGER DEFAULT 0
        );

        -- Mapping ville -> zone
        CREATE TABLE IF NOT EXISTS ville_zone_mapping (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ville TEXT NOT NULL UNIQUE,
            zone_id INTEGER REFERENCES zones(id),
            tournee_defaut TEXT,
            lat REAL,
            lon REAL
        );
        CREATE INDEX IF NOT EXISTS idx_vzm_ville ON ville_zone_mapping(ville);

        -- Config connexion BDD externe (DBI SQL Server Azure)
        CREATE TABLE IF NOT EXISTS external_db_config (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nom TEXT DEFAULT 'default',
            db_type TEXT NOT NULL DEFAULT 'sqlserver',
            host TEXT NOT NULL,
            port INTEGER DEFAULT 1433,
            database_name TEXT NOT NULL,
            username TEXT NOT NULL,
            password_encrypted TEXT,
            derniere_sync TEXT,
            sync_interval_minutes INTEGER DEFAULT 60,
            actif INTEGER DEFAULT 1
        );

        -- Selection des chauffeurs a synchroniser (legacy)
        CREATE TABLE IF NOT EXISTS chauffeurs_sync (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            externe_id TEXT NOT NULL UNIQUE,
            nom TEXT NOT NULL,
            selectionne INTEGER DEFAULT 0
        );

        -- Selection des vehicules a synchroniser (DBI)
        CREATE TABLE IF NOT EXISTS vehicules_sync (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            externe_id TEXT NOT NULL UNIQUE,
            immatriculation TEXT NOT NULL,
            selectionne INTEGER DEFAULT 0
        );

        -- Donnees transport synchronisees (DBI)
        CREATE TABLE IF NOT EXISTS donnees_transport (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chauffeur_id INTEGER REFERENCES chauffeurs(id),
            vehicule_id INTEGER REFERENCES vehicules(id),
            date_donnee TEXT NOT NULL,
            kilometres REAL DEFAULT 0,
            consommation_carburant REAL DEFAULT 0,
            consommation_litres REAL DEFAULT 0,
            duree_travail_minutes INTEGER DEFAULT 0,
            duree_conduite_minutes INTEGER DEFAULT 0,
            source_externe_id TEXT,
            synced_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(vehicule_id, date_donnee)
        );
        CREATE INDEX IF NOT EXISTS idx_dt_chauffeur ON donnees_transport(chauffeur_id);
        CREATE INDEX IF NOT EXISTS idx_dt_date ON donnees_transport(date_donnee);

        -- Messages EDI (Drakkar)
        CREATE TABLE IF NOT EXISTS edi_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            id_ligne INTEGER,
            code_indus TEXT,
            sens TEXT,
            date_trans TEXT,
            fich_suiv TEXT,
            ref_message TEXT,
            ident_message TEXT,
            total_colis INTEGER,
            total_poids REAL,
            total_positions INTEGER,
            source_cnx TEXT,
            date_sync TEXT,
            UNIQUE(id_ligne)
        );
        CREATE INDEX IF NOT EXISTS idx_edi_date ON edi_messages(date_trans);
    """)
    conn.commit()

    # Migration: ajouter les colonnes manquantes sur tables existantes
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT vehicule_id FROM donnees_transport LIMIT 1")
    except Exception:
        try:
            cursor.execute("ALTER TABLE donnees_transport ADD COLUMN vehicule_id INTEGER REFERENCES vehicules(id)")
        except Exception:
            pass
    try:
        cursor.execute("SELECT consommation_litres FROM donnees_transport LIMIT 1")
    except Exception:
        try:
            cursor.execute("ALTER TABLE donnees_transport ADD COLUMN consommation_litres REAL DEFAULT 0")
        except Exception:
            pass
    try:
        cursor.execute("SELECT duree_conduite_minutes FROM donnees_transport LIMIT 1")
    except Exception:
        try:
            cursor.execute("ALTER TABLE donnees_transport ADD COLUMN duree_conduite_minutes INTEGER DEFAULT 0")
        except Exception:
            pass
    try:
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_dt_vehicule ON donnees_transport(vehicule_id)")
    except Exception:
        pass
    # Migration: ajouter modele_id sur tournees
    try:
        cursor.execute("SELECT modele_id FROM tournees LIMIT 1")
    except Exception:
        try:
            cursor.execute("ALTER TABLE tournees ADD COLUMN modele_id INTEGER REFERENCES tournee_modeles(id)")
        except Exception:
            pass
    # Migration: ajouter couleur sur tournees
    try:
        cursor.execute("SELECT couleur FROM tournees LIMIT 1")
    except Exception:
        try:
            cursor.execute("ALTER TABLE tournees ADD COLUMN couleur TEXT")
        except Exception:
            pass
    conn.commit()
    conn.close()


def find_duplicates(db_path, lignes_tableau):
    """
    Cherche les enlèvements existants en DB qui matchent par num_enlevement + societe.
    Retourne un dict: {(num, societe): {extraction_date, extraction_nom, enlevement_id}}
    """
    conn = get_db(db_path)
    duplicates = {}

    for ligne in lignes_tableau:
        num = ligne.get('N° ENLÈVEMENT') or ligne.get('num_enlevement')
        societe = ligne.get('SOCIÉTÉ / DOMAINE') or ligne.get('societe', '')

        if num is None or not societe:
            continue

        row = conn.execute("""
            SELECT en.id, en.extraction_id, e.nom_fichier, e.date_creation
            FROM enlevements en
            JOIN extractions e ON e.id = en.extraction_id
            WHERE en.num_enlevement = ? AND en.societe = ?
            ORDER BY e.date_creation DESC LIMIT 1
        """, (num, societe)).fetchone()

        if row:
            key = (num, societe)
            if key not in duplicates:
                duplicates[key] = {
                    'enlevement_id': row['id'],
                    'extraction_id': row['extraction_id'],
                    'extraction_nom': row['nom_fichier'],
                    'extraction_date': row['date_creation'],
                }

    conn.close()
    return duplicates


def update_enlevements(db_path, lignes_tableau, duplicates):
    """
    Met à jour les enlèvements existants avec les nouvelles données.
    Les lignes qui matchent un doublon sont mises à jour in-place.
    Les lignes nouvelles sont ignorées (doivent être sauvées séparément).
    """
    conn = get_db(db_path)
    updated = 0

    for ligne in lignes_tableau:
        num = ligne.get('N° ENLÈVEMENT') or ligne.get('num_enlevement')
        societe = ligne.get('SOCIÉTÉ / DOMAINE') or ligne.get('societe', '')
        key = (num, societe)

        if key not in duplicates:
            continue

        enlevement_id = duplicates[key]['enlevement_id']
        conn.execute("""
            UPDATE enlevements SET
                reference = ?, ville = ?, nb_palettes = ?, type_palettes = ?,
                poids_total = ?, nb_colis = ?, livraison = ?, telephone = ?
            WHERE id = ?
        """, (
            ligne.get('NOTRE RÉFÉRENCE') or ligne.get('reference', ''),
            ligne.get('VILLE') or ligne.get('ville', ''),
            ligne.get('NOMBRE DE PALETTES') or ligne.get('nb_palettes', 0),
            ligne.get('TYPE DE PALETTES') or ligne.get('type_palettes', ''),
            ligne.get('POIDS TOTAL (KG)') or ligne.get('poids_total', 0),
            ligne.get('NOMBRE DE COLIS') or ligne.get('nb_colis', 0),
            ligne.get('LIVRAISON ASSOCIÉE') or ligne.get('livraison', ''),
            ligne.get('TÉLÉPHONE') or ligne.get('telephone', ''),
            enlevement_id,
        ))
        updated += 1

    conn.commit()
    conn.close()
    return updated


def save_extraction(db_path, nom_fichier, date_creation, lignes_tableau, log_contenu=None):
    """
    Insère une extraction et ses enlèvements dans la DB.

    Args:
        db_path: chemin vers la base SQLite
        nom_fichier: nom du fichier Excel (ex: "Enlevements_20260210_163018.xlsx")
        date_creation: datetime ou string ISO 8601
        lignes_tableau: liste de dicts avec les clés display (ex: "N° ENLÈVEMENT")
        log_contenu: contenu du log markdown (optionnel)
    """
    if isinstance(date_creation, datetime):
        date_creation = date_creation.isoformat()

    conn = get_db(db_path)
    try:
        cursor = conn.execute(
            "INSERT INTO extractions (nom_fichier, date_creation, nb_lignes, log_contenu) VALUES (?, ?, ?, ?)",
            (nom_fichier, date_creation, len(lignes_tableau), log_contenu)
        )
        extraction_id = cursor.lastrowid

        for ligne in lignes_tableau:
            conn.execute(
                """INSERT INTO enlevements
                   (extraction_id, num_enlevement, reference, societe, ville,
                    nb_palettes, type_palettes, poids_total, nb_colis, livraison, telephone)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    extraction_id,
                    ligne.get('N° ENLÈVEMENT') or ligne.get('num_enlevement'),
                    ligne.get('NOTRE RÉFÉRENCE') or ligne.get('reference', ''),
                    ligne.get('SOCIÉTÉ / DOMAINE') or ligne.get('societe', ''),
                    ligne.get('VILLE') or ligne.get('ville', ''),
                    ligne.get('NOMBRE DE PALETTES') or ligne.get('nb_palettes', 0),
                    ligne.get('TYPE DE PALETTES') or ligne.get('type_palettes', ''),
                    ligne.get('POIDS TOTAL (KG)') or ligne.get('poids_total', 0),
                    ligne.get('NOMBRE DE COLIS') or ligne.get('nb_colis', 0),
                    ligne.get('LIVRAISON ASSOCIÉE') or ligne.get('livraison', ''),
                    ligne.get('TÉLÉPHONE') or ligne.get('telephone', ''),
                )
            )

        conn.commit()
        return extraction_id
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def list_extractions(db_path):
    """Retourne la liste des extractions pour /api/historique."""
    conn = get_db(db_path)
    rows = conn.execute(
        "SELECT nom_fichier, date_creation, nb_lignes FROM extractions ORDER BY date_creation DESC"
    ).fetchall()
    conn.close()

    result = []
    for row in rows:
        # Déduire le nom du log depuis le nom du fichier
        timestamp_str = row['nom_fichier'].replace('Enlevements_', '').replace('.xlsx', '')
        result.append({
            'fichier': row['nom_fichier'],
            'nom_fichier': row['nom_fichier'],
            'date': row['date_creation'],
            'nb_lignes': row['nb_lignes'],
            'log_fichier': f"log_{timestamp_str}.md",
        })

    return result


def get_extraction_data(db_path, nom_fichier):
    """Retourne les données d'une extraction pour /api/donnees/<filename>."""
    conn = get_db(db_path)

    extraction = conn.execute(
        "SELECT id FROM extractions WHERE nom_fichier = ?", (nom_fichier,)
    ).fetchone()

    if not extraction:
        conn.close()
        return None

    rows = conn.execute(
        "SELECT * FROM enlevements WHERE extraction_id = ? ORDER BY num_enlevement",
        (extraction['id'],)
    ).fetchall()
    conn.close()

    donnees = []
    for row in rows:
        donnees.append({
            'N° ENLÈVEMENT': row['num_enlevement'],
            'NOTRE RÉFÉRENCE': row['reference'] or '',
            'SOCIÉTÉ / DOMAINE': row['societe'] or '',
            'VILLE': row['ville'] or '',
            'NOMBRE DE PALETTES': row['nb_palettes'] or 0,
            'TYPE DE PALETTES': row['type_palettes'] or '',
            'POIDS TOTAL (KG)': row['poids_total'] or 0,
            'NOMBRE DE COLIS': row['nb_colis'] or 0,
            'LIVRAISON ASSOCIÉE': row['livraison'] or '',
            'TÉLÉPHONE': row['telephone'] or '',
        })

    return {
        'fichier': nom_fichier,
        'nb_lignes': len(donnees),
        'colonnes': COLONNES_DISPLAY,
        'donnees': donnees,
    }


def get_extraction_log(db_path, nom_fichier):
    """Retourne le contenu du log d'une extraction."""
    conn = get_db(db_path)
    row = conn.execute(
        "SELECT log_contenu FROM extractions WHERE nom_fichier = ?", (nom_fichier,)
    ).fetchone()
    conn.close()

    if row and row['log_contenu']:
        return row['log_contenu']
    return None


def import_xlsx_file(db_path, xlsx_path, log_path=None):
    """
    Importe un fichier Excel existant dans la DB.

    Args:
        db_path: chemin vers la base SQLite
        xlsx_path: chemin vers le fichier .xlsx
        log_path: chemin vers le fichier log .md correspondant (optionnel)

    Returns:
        extraction_id ou None si erreur
    """
    xlsx_path = Path(xlsx_path)
    nom_fichier = xlsx_path.name

    # Extraire le timestamp du nom de fichier
    timestamp_str = nom_fichier.replace('Enlevements_', '').replace('.xlsx', '')
    try:
        timestamp = datetime.strptime(timestamp_str, '%Y%m%d_%H%M%S')
        date_creation = timestamp.isoformat()
    except ValueError:
        date_creation = datetime.now().isoformat()

    # Lire le contenu du log si disponible
    log_contenu = None
    if log_path and Path(log_path).exists():
        with open(log_path, 'r', encoding='utf-8') as f:
            log_contenu = f.read()

    # Lire le fichier Excel
    try:
        df = pd.read_excel(xlsx_path)
    except Exception:
        return None

    # Filtrer la ligne TOTAL si présente
    if 'N° ENLÈVEMENT' in df.columns:
        df = df[pd.to_numeric(df['N° ENLÈVEMENT'], errors='coerce').notna()]

    lignes_tableau = df.fillna('').to_dict('records')

    try:
        return save_extraction(db_path, nom_fichier, date_creation, lignes_tableau, log_contenu)
    except sqlite3.IntegrityError:
        # Fichier déjà importé (nom_fichier UNIQUE)
        return None


def generate_excel_from_db(db_path, nom_fichier):
    """
    Génère un fichier Excel à partir des données en DB.
    Retourne un DataFrame pandas prêt à être exporté.
    """
    data = get_extraction_data(db_path, nom_fichier)
    if not data:
        return None

    df = pd.DataFrame(data['donnees'])

    # Convertir les types numériques
    for col in ['N° ENLÈVEMENT', 'NOMBRE DE PALETTES', 'POIDS TOTAL (KG)', 'NOMBRE DE COLIS']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')

    df = df.sort_values('N° ENLÈVEMENT')
    return df


def get_statistiques(db_path, date_debut=None, date_fin=None):
    """
    Agrège les statistiques depuis la DB avec filtres de date optionnels.
    Les dates sont au format ISO 8601 (YYYY-MM-DD ou YYYY-MM-DDTHH:MM:SS).
    """
    conn = get_db(db_path)

    # Clause WHERE pour le filtre de date
    where_clauses = []
    params = []
    if date_debut:
        where_clauses.append("e.date_creation >= ?")
        params.append(date_debut)
    if date_fin:
        where_clauses.append("e.date_creation <= ?")
        params.append(date_fin + "T23:59:59" if len(date_fin) == 10 else date_fin)

    where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

    # Totaux globaux
    row = conn.execute(f"""
        SELECT
            COUNT(DISTINCT e.id) as nb_extractions,
            COUNT(en.id) as nb_enlevements,
            COALESCE(SUM(en.poids_total), 0) as poids_total,
            COALESCE(SUM(en.nb_colis), 0) as colis_total,
            COALESCE(SUM(en.nb_palettes), 0) as palettes_total
        FROM extractions e
        JOIN enlevements en ON en.extraction_id = e.id
        WHERE {where_sql}
    """, params).fetchone()

    totaux = {
        'nb_extractions': row['nb_extractions'],
        'nb_enlevements': row['nb_enlevements'],
        'poids_total': row['poids_total'],
        'colis_total': row['colis_total'],
        'palettes_total': row['palettes_total'],
    }

    # Par livraison (palettes)
    rows = conn.execute(f"""
        SELECT en.livraison, COALESCE(SUM(en.nb_palettes), 0) as total
        FROM extractions e
        JOIN enlevements en ON en.extraction_id = e.id
        WHERE {where_sql} AND en.livraison IS NOT NULL AND en.livraison != ''
        GROUP BY en.livraison ORDER BY total DESC
    """, params).fetchall()
    par_livraison = {r['livraison']: r['total'] for r in rows}

    # Poids par livraison
    rows = conn.execute(f"""
        SELECT en.livraison, COALESCE(SUM(en.poids_total), 0) as total
        FROM extractions e
        JOIN enlevements en ON en.extraction_id = e.id
        WHERE {where_sql} AND en.livraison IS NOT NULL AND en.livraison != ''
        GROUP BY en.livraison ORDER BY total DESC
    """, params).fetchall()
    poids_par_livraison = {r['livraison']: r['total'] for r in rows}

    # Colis par livraison
    rows = conn.execute(f"""
        SELECT en.livraison, COALESCE(SUM(en.nb_colis), 0) as total
        FROM extractions e
        JOIN enlevements en ON en.extraction_id = e.id
        WHERE {where_sql} AND en.livraison IS NOT NULL AND en.livraison != ''
        GROUP BY en.livraison ORDER BY total DESC
    """, params).fetchall()
    colis_par_livraison = {r['livraison']: r['total'] for r in rows}

    # Par type de palette
    rows = conn.execute(f"""
        SELECT en.type_palettes, COUNT(*) as total
        FROM extractions e
        JOIN enlevements en ON en.extraction_id = e.id
        WHERE {where_sql} AND en.type_palettes IS NOT NULL AND en.type_palettes != ''
        GROUP BY en.type_palettes ORDER BY total DESC
    """, params).fetchall()
    par_type_palette = {r['type_palettes']: r['total'] for r in rows}

    # Evolution quotidienne
    rows = conn.execute(f"""
        SELECT
            DATE(e.date_creation) as jour,
            COUNT(DISTINCT en.num_enlevement) as nb_enlevements,
            COALESCE(SUM(en.nb_palettes), 0) as nb_palettes
        FROM extractions e
        JOIN enlevements en ON en.extraction_id = e.id
        WHERE {where_sql}
        GROUP BY DATE(e.date_creation)
        ORDER BY jour
    """, params).fetchall()
    evolution_quotidienne = [
        {'date': r['jour'], 'nb_enlevements': r['nb_enlevements'], 'nb_palettes': r['nb_palettes']}
        for r in rows
    ]

    # Top sociétés
    rows = conn.execute(f"""
        SELECT en.societe, COUNT(DISTINCT en.num_enlevement) as nb
        FROM extractions e
        JOIN enlevements en ON en.extraction_id = e.id
        WHERE {where_sql} AND en.societe IS NOT NULL AND en.societe != ''
        GROUP BY en.societe ORDER BY nb DESC LIMIT 10
    """, params).fetchall()
    top_societes = [{'societe': r['societe'], 'nb': r['nb']} for r in rows]

    conn.close()

    return {
        'totaux': totaux,
        'par_livraison': par_livraison,
        'poids_par_livraison': poids_par_livraison,
        'colis_par_livraison': colis_par_livraison,
        'par_type_palette': par_type_palette,
        'evolution_quotidienne': evolution_quotidienne,
        'top_societes': top_societes,
    }
