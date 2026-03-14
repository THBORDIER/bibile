#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bibile - Module base de données pour les tournées

CRUD pour : chauffeurs, véhicules, tournées, zones, ville_zone_mapping,
external_db_config, chauffeurs_sync, donnees_transport.
"""

import re
from datetime import datetime

try:
    from bibile.database import get_db
except ImportError:
    from database import get_db


def normalize_ville(ville):
    """Normalise un nom de ville : uppercase, supprime tirets/espaces en trop, ponctuation finale."""
    if not ville:
        return ''
    v = ville.upper().strip()
    # Supprimer ponctuation en fin de nom (tirets, points, virgules)
    v = re.sub(r'[\s\-\.,;:]+$', '', v)
    # Supprimer ponctuation en début de nom
    v = re.sub(r'^[\s\-\.,;:]+', '', v)
    # Réduire les espaces multiples
    v = re.sub(r'\s+', ' ', v)
    return v


# ===== CHAUFFEURS =====

def list_chauffeurs(db_path, actifs_seulement=True):
    conn = get_db(db_path)
    sql = "SELECT * FROM chauffeurs"
    if actifs_seulement:
        sql += " WHERE actif = 1"
    sql += " ORDER BY nom, prenom"
    rows = conn.execute(sql).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def save_chauffeur(db_path, data):
    conn = get_db(db_path)
    chauffeur_id = data.get('id')
    if chauffeur_id:
        conn.execute("""
            UPDATE chauffeurs SET nom=?, prenom=?, telephone=?, externe_id=?, actif=?
            WHERE id=?
        """, (data['nom'], data.get('prenom', ''), data.get('telephone', ''),
              data.get('externe_id'), data.get('actif', 1), chauffeur_id))
    else:
        cursor = conn.execute("""
            INSERT INTO chauffeurs (nom, prenom, telephone, externe_id, actif)
            VALUES (?, ?, ?, ?, ?)
        """, (data['nom'], data.get('prenom', ''), data.get('telephone', ''),
              data.get('externe_id'), data.get('actif', 1)))
        chauffeur_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return chauffeur_id


def delete_chauffeur(db_path, chauffeur_id):
    conn = get_db(db_path)
    conn.execute("UPDATE chauffeurs SET actif = 0 WHERE id = ?", (chauffeur_id,))
    conn.commit()
    conn.close()


# ===== VEHICULES =====

def list_vehicules(db_path, actifs_seulement=True):
    conn = get_db(db_path)
    sql = "SELECT * FROM vehicules"
    if actifs_seulement:
        sql += " WHERE actif = 1"
    sql += " ORDER BY immatriculation"
    rows = conn.execute(sql).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def save_vehicule(db_path, data):
    conn = get_db(db_path)
    vehicule_id = data.get('id')
    if vehicule_id:
        conn.execute("""
            UPDATE vehicules SET immatriculation=?, type_vehicule=?, capacite_palettes=?, actif=?
            WHERE id=?
        """, (data['immatriculation'], data.get('type_vehicule', ''),
              data.get('capacite_palettes', 0), data.get('actif', 1), vehicule_id))
    else:
        cursor = conn.execute("""
            INSERT INTO vehicules (immatriculation, type_vehicule, capacite_palettes)
            VALUES (?, ?, ?)
        """, (data['immatriculation'], data.get('type_vehicule', ''),
              data.get('capacite_palettes', 0)))
        vehicule_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return vehicule_id


def delete_vehicule(db_path, vehicule_id):
    conn = get_db(db_path)
    conn.execute("UPDATE vehicules SET actif = 0 WHERE id = ?", (vehicule_id,))
    conn.commit()
    conn.close()


# ===== TOURNEES =====

def list_tournees(db_path, date_tournee):
    """Liste les tournées d'une date avec leurs enlèvements assignés."""
    conn = get_db(db_path)
    tournees = conn.execute("""
        SELECT t.*, c.nom as chauffeur_nom, c.prenom as chauffeur_prenom,
               v.immatriculation as vehicule_immat
        FROM tournees t
        LEFT JOIN chauffeurs c ON c.id = t.chauffeur_id
        LEFT JOIN vehicules v ON v.id = t.vehicule_id
        WHERE t.date_tournee = ?
        ORDER BY t.ordre_tri, t.id
    """, (date_tournee,)).fetchall()

    result = []
    for t in tournees:
        tournee = dict(t)
        # Charger les enlèvements de cette tournée
        enlevements = conn.execute("""
            SELECT te.ordre, e.*, vzm.lat, vzm.lon
            FROM tournee_enlevements te
            JOIN enlevements e ON e.id = te.enlevement_id
            LEFT JOIN ville_zone_mapping vzm ON TRIM(UPPER(e.ville), ' -.,') = TRIM(vzm.ville, ' -.,')
            WHERE te.tournee_id = ?
            ORDER BY te.ordre
        """, (tournee['id'],)).fetchall()
        tournee['enlevements'] = [dict(e) for e in enlevements]
        result.append(tournee)

    conn.close()
    return result


def create_tournee(db_path, data):
    conn = get_db(db_path)
    cursor = conn.execute("""
        INSERT INTO tournees (nom, date_tournee, chauffeur_id, vehicule_id, statut, notes)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (data['nom'], data['date_tournee'], data.get('chauffeur_id'),
          data.get('vehicule_id'), data.get('statut', 'brouillon'), data.get('notes', '')))
    tournee_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return tournee_id


def update_tournee(db_path, tournee_id, data):
    conn = get_db(db_path)
    fields = []
    values = []
    for key in ['nom', 'chauffeur_id', 'vehicule_id', 'statut', 'notes', 'ordre_tri']:
        if key in data:
            fields.append(f"{key} = ?")
            values.append(data[key])
    if fields:
        values.append(tournee_id)
        conn.execute(f"UPDATE tournees SET {', '.join(fields)} WHERE id = ?", values)
        conn.commit()
    conn.close()


def delete_tournee(db_path, tournee_id):
    conn = get_db(db_path)
    conn.execute("DELETE FROM tournees WHERE id = ?", (tournee_id,))
    conn.commit()
    conn.close()


# ===== MODELES DE TOURNEES =====

def list_modeles(db_path, actifs_seulement=True):
    """Liste les modeles de tournees avec chauffeur/vehicule joints."""
    conn = get_db(db_path)
    where = "WHERE m.actif = 1" if actifs_seulement else ""
    rows = conn.execute(f"""
        SELECT m.*, c.nom as chauffeur_nom, c.prenom as chauffeur_prenom,
               v.immatriculation as vehicule_immat
        FROM tournee_modeles m
        LEFT JOIN chauffeurs c ON c.id = m.chauffeur_id
        LEFT JOIN vehicules v ON v.id = m.vehicule_id
        {where}
        ORDER BY m.ordre_tri, m.id
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def save_modele(db_path, data):
    """Creer ou modifier un modele de tournee."""
    conn = get_db(db_path)
    if data.get('id'):
        fields = []
        values = []
        for key in ['nom', 'chauffeur_id', 'vehicule_id', 'ordre_tri', 'actif', 'couleur']:
            if key in data:
                fields.append(f"{key} = ?")
                values.append(data[key])
        if fields:
            values.append(data['id'])
            conn.execute(f"UPDATE tournee_modeles SET {', '.join(fields)} WHERE id = ?", values)
        modele_id = data['id']
    else:
        cursor = conn.execute("""
            INSERT INTO tournee_modeles (nom, chauffeur_id, vehicule_id, ordre_tri, couleur)
            VALUES (?, ?, ?, ?, ?)
        """, (data['nom'], data.get('chauffeur_id'), data.get('vehicule_id'),
              data.get('ordre_tri', 0), data.get('couleur', '#4493f8')))
        modele_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return modele_id


def delete_modele(db_path, modele_id):
    """Soft delete : desactive le modele."""
    conn = get_db(db_path)
    conn.execute("UPDATE tournee_modeles SET actif = 0 WHERE id = ?", (modele_id,))
    conn.commit()
    conn.close()


def instancier_tournees(db_path, date_tournee):
    """
    Pour chaque modele actif, cree une tournee du jour si elle n'existe pas deja.
    Retourne le nombre de tournees creees.
    """
    conn = get_db(db_path)
    modeles = conn.execute(
        "SELECT * FROM tournee_modeles WHERE actif = 1 ORDER BY ordre_tri, id"
    ).fetchall()

    created = 0
    for m in modeles:
        existing = conn.execute(
            "SELECT id FROM tournees WHERE modele_id = ? AND date_tournee = ?",
            (m['id'], date_tournee)
        ).fetchone()
        if not existing:
            conn.execute("""
                INSERT INTO tournees (nom, date_tournee, chauffeur_id, vehicule_id, modele_id, ordre_tri, couleur)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (m['nom'], date_tournee, m['chauffeur_id'], m['vehicule_id'], m['id'], m['ordre_tri'], m['couleur']))
            created += 1

    conn.commit()
    conn.close()
    return created


# ===== ASSIGNATION ENLEVEMENTS <-> TOURNEES =====

def assign_enlevements(db_path, tournee_id, enlevement_ids):
    """Assigne des enlèvements à une tournée."""
    conn = get_db(db_path)
    # Récupérer l'ordre max actuel
    row = conn.execute(
        "SELECT COALESCE(MAX(ordre), -1) as max_ordre FROM tournee_enlevements WHERE tournee_id = ?",
        (tournee_id,)
    ).fetchone()
    ordre = row['max_ordre'] + 1

    for eid in enlevement_ids:
        try:
            conn.execute(
                "INSERT INTO tournee_enlevements (tournee_id, enlevement_id, ordre) VALUES (?, ?, ?)",
                (tournee_id, eid, ordre)
            )
            ordre += 1
        except Exception:
            pass  # Doublon ignoré (UNIQUE constraint)
    conn.commit()
    conn.close()


def remove_enlevement(db_path, tournee_id, enlevement_id):
    conn = get_db(db_path)
    conn.execute(
        "DELETE FROM tournee_enlevements WHERE tournee_id = ? AND enlevement_id = ?",
        (tournee_id, enlevement_id)
    )
    conn.commit()
    conn.close()


def reorder_enlevements(db_path, tournee_id, ordered_enlevement_ids):
    """Réordonne les enlèvements d'une tournée."""
    conn = get_db(db_path)
    for i, eid in enumerate(ordered_enlevement_ids):
        conn.execute(
            "UPDATE tournee_enlevements SET ordre = ? WHERE tournee_id = ? AND enlevement_id = ?",
            (i, tournee_id, eid)
        )
    conn.commit()
    conn.close()


def get_unassigned_enlevements(db_path, extraction_id=None, date=None):
    """Retourne les enlèvements non assignés à une tournée (dédoublonnés par num+societe, plus récent)."""
    conn = get_db(db_path)

    if extraction_id:
        rows = conn.execute("""
            SELECT e.*, vzm.lat, vzm.lon FROM enlevements e
            LEFT JOIN ville_zone_mapping vzm ON TRIM(UPPER(e.ville), ' -.,') = TRIM(vzm.ville, ' -.,')
            WHERE e.extraction_id = ?
            AND e.id NOT IN (SELECT enlevement_id FROM tournee_enlevements)
            ORDER BY e.num_enlevement
        """, (extraction_id,)).fetchall()
    elif date:
        # CTE pour ne garder que l'enlèvement le plus récent par (num_enlevement, societe)
        rows = conn.execute("""
            WITH latest AS (
                SELECT MAX(e2.id) as latest_id
                FROM enlevements e2
                JOIN extractions ex2 ON ex2.id = e2.extraction_id
                WHERE DATE(ex2.date_creation) = ?
                GROUP BY e2.num_enlevement, e2.societe
            )
            SELECT e.*, vzm.lat, vzm.lon FROM enlevements e
            LEFT JOIN ville_zone_mapping vzm ON TRIM(UPPER(e.ville), ' -.,') = TRIM(vzm.ville, ' -.,')
            WHERE e.id IN (SELECT latest_id FROM latest)
            AND e.id NOT IN (SELECT enlevement_id FROM tournee_enlevements)
            ORDER BY e.num_enlevement
        """, (date,)).fetchall()
    else:
        rows = conn.execute("""
            WITH latest AS (
                SELECT MAX(e2.id) as latest_id
                FROM enlevements e2
                GROUP BY e2.num_enlevement, e2.societe
            )
            SELECT e.*, vzm.lat, vzm.lon FROM enlevements e
            LEFT JOIN ville_zone_mapping vzm ON TRIM(UPPER(e.ville), ' -.,') = TRIM(vzm.ville, ' -.,')
            WHERE e.id IN (SELECT latest_id FROM latest)
            AND e.id NOT IN (SELECT enlevement_id FROM tournee_enlevements)
            ORDER BY e.num_enlevement
        """).fetchall()

    conn.close()
    return [dict(r) for r in rows]


# ===== ZONES & VILLE-ZONE MAPPING =====

def list_zones(db_path):
    conn = get_db(db_path)
    zones = conn.execute("SELECT * FROM zones ORDER BY priorite DESC, nom").fetchall()
    result = []
    for z in zones:
        zone = dict(z)
        villes = conn.execute(
            "SELECT * FROM ville_zone_mapping WHERE zone_id = ? ORDER BY ville",
            (zone['id'],)
        ).fetchall()
        zone['villes'] = [dict(v) for v in villes]
        result.append(zone)
    conn.close()
    return result


def save_zone(db_path, data):
    conn = get_db(db_path)
    zone_id = data.get('id')
    if zone_id:
        conn.execute("""
            UPDATE zones SET nom=?, tournee_defaut=?, couleur=?, priorite=? WHERE id=?
        """, (data['nom'], data.get('tournee_defaut', ''), data.get('couleur', '#4493f8'),
              data.get('priorite', 0), zone_id))
    else:
        cursor = conn.execute("""
            INSERT INTO zones (nom, tournee_defaut, couleur, priorite) VALUES (?, ?, ?, ?)
        """, (data['nom'], data.get('tournee_defaut', ''), data.get('couleur', '#4493f8'),
              data.get('priorite', 0)))
        zone_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return zone_id


def delete_zone(db_path, zone_id):
    conn = get_db(db_path)
    conn.execute("UPDATE ville_zone_mapping SET zone_id = NULL WHERE zone_id = ?", (zone_id,))
    conn.execute("DELETE FROM zones WHERE id = ?", (zone_id,))
    conn.commit()
    conn.close()


def list_ville_zone_mapping(db_path):
    conn = get_db(db_path)
    rows = conn.execute("""
        SELECT vzm.*, z.nom as zone_nom, z.couleur as zone_couleur
        FROM ville_zone_mapping vzm
        LEFT JOIN zones z ON z.id = vzm.zone_id
        ORDER BY vzm.ville
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def save_ville_zone(db_path, data):
    conn = get_db(db_path)
    ville = normalize_ville(data['ville'])
    existing = conn.execute("SELECT id FROM ville_zone_mapping WHERE ville = ?", (ville,)).fetchone()
    if existing:
        conn.execute("""
            UPDATE ville_zone_mapping SET zone_id=?, tournee_defaut=?, lat=?, lon=? WHERE ville=?
        """, (data.get('zone_id'), data.get('tournee_defaut', ''),
              data.get('lat'), data.get('lon'), ville))
    else:
        conn.execute("""
            INSERT INTO ville_zone_mapping (ville, zone_id, tournee_defaut, lat, lon)
            VALUES (?, ?, ?, ?, ?)
        """, (ville, data.get('zone_id'), data.get('tournee_defaut', ''),
              data.get('lat'), data.get('lon')))
    conn.commit()
    conn.close()


def get_villes_inconnues(db_path):
    """Retourne les villes présentes dans les enlèvements mais pas dans le mapping."""
    conn = get_db(db_path)
    rows = conn.execute("""
        SELECT DISTINCT TRIM(UPPER(e.ville), ' -.,') as ville, COUNT(*) as nb
        FROM enlevements e
        WHERE e.ville IS NOT NULL AND e.ville != ''
        AND TRIM(UPPER(e.ville), ' -.,') NOT IN (SELECT TRIM(ville, ' -.,') FROM ville_zone_mapping)
        GROUP BY TRIM(UPPER(e.ville), ' -.,')
        ORDER BY nb DESC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ===== AUTO-DISTRIBUTION =====

def auto_distribuer(db_path, date_tournee, extraction_id=None):
    """
    Répartit automatiquement les enlèvements non assignés en tournées
    selon le mapping ville->zone->tournée.
    Instancie d'abord les modeles de tournees pour la date.
    Retourne {assigned: N, unknown_cities: [...]}
    """
    # Instancier les modeles avant de distribuer
    instancier_tournees(db_path, date_tournee)

    conn = get_db(db_path)

    # Charger le mapping ville -> tournée
    mappings = conn.execute("""
        SELECT vzm.ville, vzm.tournee_defaut as ville_tournee,
               z.tournee_defaut as zone_tournee, z.nom as zone_nom
        FROM ville_zone_mapping vzm
        LEFT JOIN zones z ON z.id = vzm.zone_id
    """).fetchall()

    ville_to_tournee = {}
    for m in mappings:
        tournee_nom = m['ville_tournee'] or m['zone_tournee']
        if tournee_nom:
            ville_to_tournee[m['ville']] = tournee_nom

    # Récupérer les enlèvements non assignés
    if extraction_id:
        enlevements = conn.execute("""
            SELECT e.* FROM enlevements e
            WHERE e.extraction_id = ?
            AND e.id NOT IN (SELECT enlevement_id FROM tournee_enlevements)
        """, (extraction_id,)).fetchall()
    else:
        enlevements = conn.execute("""
            SELECT e.* FROM enlevements e
            JOIN extractions ex ON ex.id = e.extraction_id
            WHERE DATE(ex.date_creation) = ?
            AND e.id NOT IN (SELECT enlevement_id FROM tournee_enlevements)
        """, (date_tournee,)).fetchall()

    # Regrouper par tournée cible
    distribution = {}  # tournee_nom -> [enlevement_ids]
    unknown_cities = set()
    assigned = 0

    for e in enlevements:
        ville = e['ville'] or ''
        tournee_nom = ville_to_tournee.get(ville)
        if tournee_nom:
            if tournee_nom not in distribution:
                distribution[tournee_nom] = []
            distribution[tournee_nom].append(e['id'])
        else:
            if ville:
                unknown_cities.add(ville)

    # Créer/trouver les tournées et assigner
    for tournee_nom, enl_ids in distribution.items():
        # Chercher une tournée existante avec ce nom pour cette date
        existing = conn.execute(
            "SELECT id FROM tournees WHERE nom = ? AND date_tournee = ?",
            (tournee_nom, date_tournee)
        ).fetchone()

        if existing:
            tournee_id = existing['id']
        else:
            cursor = conn.execute(
                "INSERT INTO tournees (nom, date_tournee) VALUES (?, ?)",
                (tournee_nom, date_tournee)
            )
            tournee_id = cursor.lastrowid

        # Assigner les enlèvements
        row = conn.execute(
            "SELECT COALESCE(MAX(ordre), -1) as max_o FROM tournee_enlevements WHERE tournee_id = ?",
            (tournee_id,)
        ).fetchone()
        ordre = row['max_o'] + 1

        for eid in enl_ids:
            try:
                conn.execute(
                    "INSERT INTO tournee_enlevements (tournee_id, enlevement_id, ordre) VALUES (?, ?, ?)",
                    (tournee_id, eid, ordre)
                )
                ordre += 1
                assigned += 1
            except Exception:
                pass

    conn.commit()
    conn.close()

    return {
        'assigned': assigned,
        'unknown_cities': sorted(unknown_cities),
    }


# ===== EXTERNAL DB CONFIG =====

def get_external_config(db_path):
    conn = get_db(db_path)
    row = conn.execute("SELECT * FROM external_db_config WHERE nom = 'default'").fetchone()
    conn.close()
    return dict(row) if row else None


def save_external_config(db_path, data):
    conn = get_db(db_path)
    existing = conn.execute("SELECT id FROM external_db_config WHERE nom = 'default'").fetchone()
    if existing:
        conn.execute("""
            UPDATE external_db_config SET
                db_type=?, host=?, port=?, database_name=?, username=?,
                password_encrypted=?, sync_interval_minutes=?, actif=?
            WHERE nom='default'
        """, (data.get('db_type', 'sqlserver'), data['host'], data.get('port', 1433),
              data['database_name'], data['username'], data.get('password_encrypted', ''),
              data.get('sync_interval_minutes', 60), data.get('actif', 1)))
    else:
        conn.execute("""
            INSERT INTO external_db_config
                (nom, db_type, host, port, database_name, username, password_encrypted, sync_interval_minutes, actif)
            VALUES ('default', ?, ?, ?, ?, ?, ?, ?, ?)
        """, (data.get('db_type', 'sqlserver'), data['host'], data.get('port', 1433),
              data['database_name'], data['username'], data.get('password_encrypted', ''),
              data.get('sync_interval_minutes', 60), data.get('actif', 1)))
    conn.commit()
    conn.close()


def update_derniere_sync(db_path):
    conn = get_db(db_path)
    conn.execute(
        "UPDATE external_db_config SET derniere_sync = ? WHERE nom = 'default'",
        (datetime.now().isoformat(),)
    )
    conn.commit()
    conn.close()


# ===== DRAKKAR CONFIG =====

def get_drakkar_config(db_path):
    conn = get_db(db_path)
    row = conn.execute("SELECT * FROM external_db_config WHERE nom = 'drakkar'").fetchone()
    conn.close()
    return dict(row) if row else None


def save_drakkar_config(db_path, data):
    conn = get_db(db_path)
    existing = conn.execute("SELECT id FROM external_db_config WHERE nom = 'drakkar'").fetchone()
    if existing:
        conn.execute("""
            UPDATE external_db_config SET
                db_type=?, host=?, port=?, database_name=?, username=?,
                password_encrypted=?, actif=?
            WHERE nom='drakkar'
        """, (data.get('db_type', 'sqlserver'), data['host'], data.get('port', 49372),
              data['database_name'], data['username'], data.get('password_encrypted', ''),
              data.get('actif', 1)))
    else:
        conn.execute("""
            INSERT INTO external_db_config
                (nom, db_type, host, port, database_name, username, password_encrypted, actif)
            VALUES ('drakkar', ?, ?, ?, ?, ?, ?, ?)
        """, (data.get('db_type', 'sqlserver'), data['host'], data.get('port', 49372),
              data['database_name'], data['username'], data.get('password_encrypted', ''),
              data.get('actif', 1)))
    conn.commit()
    conn.close()


# ===== CHAUFFEURS SYNC =====

def list_chauffeurs_sync(db_path):
    conn = get_db(db_path)
    rows = conn.execute("SELECT * FROM chauffeurs_sync ORDER BY nom").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def save_chauffeurs_sync_selection(db_path, selections):
    """selections = [{externe_id, nom, selectionne}, ...]"""
    conn = get_db(db_path)
    for s in selections:
        existing = conn.execute(
            "SELECT id FROM chauffeurs_sync WHERE externe_id = ?", (s['externe_id'],)
        ).fetchone()
        if existing:
            conn.execute(
                "UPDATE chauffeurs_sync SET selectionne = ?, nom = ? WHERE externe_id = ?",
                (s.get('selectionne', 0), s['nom'], s['externe_id'])
            )
        else:
            conn.execute(
                "INSERT INTO chauffeurs_sync (externe_id, nom, selectionne) VALUES (?, ?, ?)",
                (s['externe_id'], s['nom'], s.get('selectionne', 0))
            )
    conn.commit()
    conn.close()


# ===== VEHICULES SYNC (DBI) =====

def list_vehicules_sync(db_path):
    conn = get_db(db_path)
    rows = conn.execute("SELECT * FROM vehicules_sync ORDER BY immatriculation").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def save_vehicules_sync_selection(db_path, selections):
    """selections = [{externe_id, immatriculation, selectionne}, ...]"""
    conn = get_db(db_path)
    for s in selections:
        existing = conn.execute(
            "SELECT id FROM vehicules_sync WHERE externe_id = ?", (s['externe_id'],)
        ).fetchone()
        if existing:
            conn.execute(
                "UPDATE vehicules_sync SET selectionne = ?, immatriculation = ? WHERE externe_id = ?",
                (s.get('selectionne', 0), s['immatriculation'], s['externe_id'])
            )
        else:
            conn.execute(
                "INSERT INTO vehicules_sync (externe_id, immatriculation, selectionne) VALUES (?, ?, ?)",
                (s['externe_id'], s['immatriculation'], s.get('selectionne', 0))
            )
    conn.commit()
    conn.close()


# ===== DONNEES TRANSPORT =====

def get_donnees_transport(db_path, vehicule_id=None, chauffeur_id=None, date_debut=None, date_fin=None):
    conn = get_db(db_path)
    sql = """
        SELECT dt.*, v.immatriculation as vehicule_immat
        FROM donnees_transport dt
        LEFT JOIN vehicules v ON v.id = dt.vehicule_id
        WHERE 1=1
    """
    params = []
    if vehicule_id:
        sql += " AND dt.vehicule_id = ?"
        params.append(vehicule_id)
    if chauffeur_id:
        sql += " AND dt.chauffeur_id = ?"
        params.append(chauffeur_id)
    if date_debut:
        sql += " AND dt.date_donnee >= ?"
        params.append(date_debut)
    if date_fin:
        sql += " AND dt.date_donnee <= ?"
        params.append(date_fin)
    sql += " ORDER BY dt.date_donnee DESC"
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def upsert_donnees_transport(db_path, records):
    """Insère ou met à jour les données transport (liées aux véhicules DBI)."""
    conn = get_db(db_path)
    for r in records:
        conn.execute("""
            INSERT INTO donnees_transport
                (vehicule_id, date_donnee, kilometres, consommation_litres,
                 duree_conduite_minutes, duree_travail_minutes, source_externe_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(vehicule_id, date_donnee) DO UPDATE SET
                kilometres = excluded.kilometres,
                consommation_litres = excluded.consommation_litres,
                duree_conduite_minutes = excluded.duree_conduite_minutes,
                duree_travail_minutes = excluded.duree_travail_minutes,
                synced_at = CURRENT_TIMESTAMP
        """, (r['vehicule_id'], r['date_donnee'], r.get('kilometres', 0),
              r.get('consommation_litres', 0), r.get('duree_conduite_minutes', 0),
              r.get('duree_travail_minutes', 0), r.get('source_externe_id', '')))
    conn.commit()
    conn.close()


# ===== HELPERS =====

def get_extractions_for_date(db_path, date):
    """Retourne les extractions d'une date donnée."""
    conn = get_db(db_path)
    rows = conn.execute("""
        SELECT id, nom_fichier, date_creation, nb_lignes
        FROM extractions
        WHERE DATE(date_creation) = ?
        ORDER BY date_creation DESC
    """, (date,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]
