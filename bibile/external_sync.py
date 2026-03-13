#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bibile - Module de synchronisation avec BDD DBI (SQL Server Azure)

Gère la connexion à la BDD DBI du prestataire transport et la
synchronisation incrémentale des données véhicules/transport.

BDD: SQL Server Azure (read-only, 90 jours de rétention)
Tables: Vehicle, StartStopEvent, DailyCumulationVehicle, LastPositionVehicle, [User]
Timestamps: epoch millisecondes UTC
"""

import threading
import logging
from datetime import datetime, timedelta

try:
    from bibile.database_tournees import (
        get_external_config, update_derniere_sync,
        list_vehicules_sync, upsert_donnees_transport,
    )
    from bibile.database import get_db
except ImportError:
    from database_tournees import (
        get_external_config, update_derniere_sync,
        list_vehicules_sync, upsert_donnees_transport,
    )
    from database import get_db

logger = logging.getLogger('bibile.sync')


def _get_connection(config):
    """Crée une connexion à la BDD DBI (SQL Server Azure).

    Tente pyodbc (ODBC Driver 17/18) en priorité, fallback pymssql.
    pyodbc est le driver recommandé par Microsoft pour Azure SQL.
    """
    host = config['host']
    port = int(config.get('port', 1433))
    user = config['username']
    password = config.get('password_encrypted', '')
    database = config['database_name']

    # Essayer pyodbc d'abord (meilleur support Azure SQL + TLS)
    try:
        import pyodbc
        # Chercher le meilleur driver ODBC disponible
        drivers = pyodbc.drivers()
        odbc_driver = None
        for preferred in ['ODBC Driver 18 for SQL Server', 'ODBC Driver 17 for SQL Server']:
            if preferred in drivers:
                odbc_driver = preferred
                break

        if odbc_driver:
            conn_str = (
                f"DRIVER={{{odbc_driver}}};"
                f"SERVER={host},{port};"
                f"DATABASE={database};"
                f"UID={user};"
                f"PWD={password};"
                f"Encrypt=yes;"
                f"TrustServerCertificate=no;"
                f"Connection Timeout=15;"
            )
            conn = pyodbc.connect(conn_str)
            conn.timeout = 30
            return conn
    except ImportError:
        pass
    except Exception as e:
        logger.warning(f"pyodbc echoue, fallback pymssql: {e}")

    # Fallback pymssql
    import pymssql

    # Azure SQL exige le format user@servername pour l'authentification
    if '.database.windows.net' in host and '@' not in user:
        server_short = host.split('.')[0]
        user = f"{user}@{server_short}"

    import os
    os.environ.setdefault('TDSVER', '7.3')

    return pymssql.connect(
        server=host,
        port=port,
        user=user,
        password=password,
        database=database,
        login_timeout=15,
        timeout=30,
        as_dict=True,
        tds_version='7.3',
    )


def _row_to_dict(cursor, row):
    """Convertit un row (pyodbc ou pymssql) en dict."""
    if row is None:
        return None
    if isinstance(row, dict):
        return row
    # pyodbc Row: cursor.description contient les noms de colonnes
    columns = [col[0] for col in cursor.description]
    return dict(zip(columns, row))


def _fetchall_dict(cursor):
    """Fetch all rows as list of dicts (compatible pyodbc et pymssql)."""
    rows = cursor.fetchall()
    if not rows:
        return []
    if isinstance(rows[0], dict):
        return rows
    columns = [col[0] for col in cursor.description]
    return [dict(zip(columns, row)) for row in rows]


def test_connection(config):
    """Teste la connexion à la BDD DBI. Retourne (success, message)."""
    try:
        conn = _get_connection(config)
        cursor = conn.cursor()
        cursor.execute("SELECT 1 AS ok")
        cursor.fetchone()
        # Compter les véhicules actifs
        cursor.execute("SELECT COUNT(*) AS cnt FROM Vehicle WHERE active = 1")
        row = _row_to_dict(cursor, cursor.fetchone())
        nb = row['cnt'] if row else 0
        cursor.close()
        conn.close()
        # Indiquer quel driver a été utilisé
        driver = 'pyodbc' if hasattr(conn, 'getinfo') else 'pymssql'
        return True, f"Connexion reussie ({driver}) — {nb} vehicule(s) actif(s)"
    except Exception as e:
        return False, str(e)


def fetch_external_vehicles(config):
    """Récupère la liste des véhicules actifs depuis la BDD DBI."""
    try:
        conn = _get_connection(config)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, licensePlateNumber
            FROM Vehicle
            WHERE active = 1
            ORDER BY licensePlateNumber
        """)
        vehicles = []
        for row in _fetchall_dict(cursor):
            vehicles.append({
                'externe_id': str(row['id']),
                'immatriculation': row['licensePlateNumber'] or '',
            })
        cursor.close()
        conn.close()
        return vehicles
    except Exception as e:
        logger.error(f"Erreur fetch vehicules DBI: {e}")
        return []


def fetch_vehicle_positions(config):
    """Récupère les positions GPS live des véhicules avec chauffeur courant."""
    try:
        conn = _get_connection(config)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT
                v.id AS vehicleId,
                v.licensePlateNumber,
                lpv.latitude,
                lpv.longitude,
                lpv.speed,
                lpv.[timestamp] AS gpsTimestampEpochMs,
                u.firstName,
                u.lastName,
                CASE
                    WHEN DATEDIFF(SECOND,
                        DATEADD(s, lpv.[timestamp] / 1000, '19700101'),
                        GETUTCDATE()
                    ) <= 120 THEN 1
                    ELSE 0
                END AS isFresh
            FROM Vehicle v
            INNER JOIN LastPositionVehicle lpv ON lpv.vehicleId = v.id
            LEFT JOIN [User] u ON u.id = lpv.userId
            WHERE v.active = 1
            ORDER BY v.licensePlateNumber
        """)
        positions = []
        for row in _fetchall_dict(cursor):
            if row['latitude'] is None or row['longitude'] is None:
                continue
            ts_ms = row['gpsTimestampEpochMs'] or 0
            positions.append({
                'vehicleId': row['vehicleId'],
                'immatriculation': row['licensePlateNumber'] or '',
                'lat': float(row['latitude']),
                'lon': float(row['longitude']),
                'speed': float(row['speed'] or 0),
                'timestamp': datetime.utcfromtimestamp(ts_ms / 1000).strftime('%Y-%m-%d %H:%M:%S UTC'),
                'chauffeur': f"{row['firstName'] or ''} {row['lastName'] or ''}".strip() or None,
                'isFresh': bool(row['isFresh']),
            })
        cursor.close()
        conn.close()
        return positions
    except Exception as e:
        logger.error(f"Erreur fetch positions DBI: {e}")
        return []


class SyncManager:
    """Gestionnaire de synchronisation en arrière-plan."""

    def __init__(self, db_path):
        self.db_path = db_path
        self._stop_event = threading.Event()
        self._trigger_event = threading.Event()
        self._thread = None
        self._last_error = None
        self._last_sync = None
        self._is_syncing = False

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._run_loop, daemon=True, name='bibile-sync')
        self._thread.start()
        logger.info("SyncManager demarre")

    def stop(self):
        self._stop_event.set()
        self._trigger_event.set()
        if self._thread:
            self._thread.join(timeout=5)

    def trigger_sync(self):
        self._trigger_event.set()

    def get_status(self):
        config = get_external_config(self.db_path)
        return {
            'configured': config is not None,
            'actif': config.get('actif', 0) if config else False,
            'is_syncing': self._is_syncing,
            'last_sync': config.get('derniere_sync') if config else None,
            'last_error': self._last_error,
            'sync_interval': config.get('sync_interval_minutes', 60) if config else 60,
        }

    def _run_loop(self):
        while not self._stop_event.is_set():
            config = get_external_config(self.db_path)
            interval = 300

            if config and config.get('actif'):
                interval = config.get('sync_interval_minutes', 60) * 60
                try:
                    self._do_sync(config)
                except Exception as e:
                    self._last_error = str(e)
                    logger.error(f"Erreur sync: {e}")

            self._trigger_event.wait(timeout=interval)
            self._trigger_event.clear()

    def _do_sync(self, config):
        """Synchronisation incrémentale depuis la BDD DBI."""
        self._is_syncing = True
        self._last_error = None

        try:
            conn_ext = _get_connection(config)
            cursor = conn_ext.cursor()

            # Véhicules sélectionnés pour la synchro
            vehicules_sync = list_vehicules_sync(self.db_path)
            selected = [v for v in vehicules_sync if v.get('selectionne')]

            if not selected:
                self._is_syncing = False
                cursor.close()
                conn_ext.close()
                return

            # Date de début : dernière sync ou 90 jours
            derniere_sync = config.get('derniere_sync')
            if derniere_sync:
                since_date = datetime.fromisoformat(derniere_sync[:19])
            else:
                since_date = datetime.utcnow() - timedelta(days=90)

            since_epoch_ms = int(since_date.timestamp() * 1000)

            # Synchro véhicules locaux (créer/mettre à jour)
            conn_local = get_db(self.db_path)
            externe_ids = [v['externe_id'] for v in selected]

            for vs in selected:
                ext_id = vs['externe_id']
                immat = vs.get('immatriculation', vs.get('nom', ''))

                local = conn_local.execute(
                    "SELECT id FROM vehicules WHERE externe_id = ?", (ext_id,)
                ).fetchone()

                if not local:
                    conn_local.execute("""
                        INSERT INTO vehicules (immatriculation, externe_id, actif)
                        VALUES (?, ?, 1)
                    """, (immat, ext_id))
                    conn_local.commit()

            # Récupérer les IDs locaux pour le mapping
            local_vehicles = {}
            for vs in selected:
                row = conn_local.execute(
                    "SELECT id FROM vehicules WHERE externe_id = ?", (vs['externe_id'],)
                ).fetchone()
                if row:
                    local_vehicles[vs['externe_id']] = row['id']

            # Synchro DailyCumulationVehicle (km, durées)
            placeholders = ','.join(['%s'] * len(externe_ids))
            int_ids = [int(eid) for eid in externe_ids]

            cursor.execute(f"""
                SELECT
                    vehicleId,
                    CONVERT(DATE, DATEADD(s, [timestamp]/1000, '19700101')) AS date_donnee,
                    totalMileage / 1000.0 AS kilometres,
                    drivingDuration / 60 AS duree_conduite_minutes,
                    workingDuration / 60 AS duree_travail_minutes
                FROM DailyCumulationVehicle
                WHERE vehicleId IN ({placeholders})
                  AND [timestamp] >= %s
            """, (*int_ids, since_epoch_ms))

            daily_data = {}
            for row in _fetchall_dict(cursor):
                key = (str(row['vehicleId']), str(row['date_donnee']))
                daily_data[key] = {
                    'kilometres': float(row['kilometres'] or 0),
                    'duree_conduite_minutes': int(row['duree_conduite_minutes'] or 0),
                    'duree_travail_minutes': int(row['duree_travail_minutes'] or 0),
                }

            # Synchro StartStopEvent (consommation carburant)
            cursor.execute(f"""
                SELECT
                    vehicleId,
                    CONVERT(DATE, DATEADD(s, [timestamp]/1000, '19700101')) AS date_donnee,
                    SUM(fuelConsumption) AS consommation_litres
                FROM StartStopEvent
                WHERE vehicleId IN ({placeholders})
                  AND [timestamp] >= %s
                GROUP BY vehicleId,
                    CONVERT(DATE, DATEADD(s, [timestamp]/1000, '19700101'))
            """, (*int_ids, since_epoch_ms))

            fuel_data = {}
            for row in _fetchall_dict(cursor):
                key = (str(row['vehicleId']), str(row['date_donnee']))
                fuel_data[key] = float(row['consommation_litres'] or 0)

            # Fusionner et upsert dans SQLite
            records = []
            all_keys = set(daily_data.keys()) | set(fuel_data.keys())
            for key in all_keys:
                ext_vid, date_str = key
                local_vid = local_vehicles.get(ext_vid)
                if not local_vid:
                    continue

                daily = daily_data.get(key, {})
                conso = fuel_data.get(key, 0)

                records.append({
                    'vehicule_id': local_vid,
                    'date_donnee': date_str,
                    'kilometres': daily.get('kilometres', 0),
                    'consommation_litres': conso,
                    'duree_conduite_minutes': daily.get('duree_conduite_minutes', 0),
                    'duree_travail_minutes': daily.get('duree_travail_minutes', 0),
                    'source_externe_id': ext_vid,
                })

            if records:
                upsert_donnees_transport(self.db_path, records)

            conn_local.close()
            cursor.close()
            conn_ext.close()

            update_derniere_sync(self.db_path)
            self._last_sync = datetime.now().isoformat()

        except Exception as e:
            self._last_error = str(e)
            raise
        finally:
            self._is_syncing = False
