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
    """Retourne une connexion SQLite avec foreign keys activées."""
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys = ON")
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
    """)
    conn.commit()
    conn.close()


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
