#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bibile - Module de synchronisation avec base de données externe

Gère la connexion à la BDD du prestataire transport (MySQL/PostgreSQL)
et la synchronisation incrémentale des données chauffeurs/transport.
"""

import threading
import logging
from datetime import datetime, timedelta

try:
    from bibile.database_tournees import (
        get_external_config, update_derniere_sync,
        list_chauffeurs_sync, upsert_donnees_transport, save_chauffeur
    )
    from bibile.database import get_db
except ImportError:
    from database_tournees import (
        get_external_config, update_derniere_sync,
        list_chauffeurs_sync, upsert_donnees_transport, save_chauffeur
    )
    from database import get_db

logger = logging.getLogger('bibile.sync')


def _get_connection(config):
    """Crée une connexion à la BDD externe."""
    db_type = config.get('db_type', 'mysql')
    if db_type == 'mysql':
        import mysql.connector
        return mysql.connector.connect(
            host=config['host'],
            port=config.get('port', 3306),
            database=config['database_name'],
            user=config['username'],
            password=config.get('password_encrypted', ''),
            connect_timeout=10,
        )
    elif db_type == 'postgresql':
        import psycopg2
        return psycopg2.connect(
            host=config['host'],
            port=config.get('port', 5432),
            dbname=config['database_name'],
            user=config['username'],
            password=config.get('password_encrypted', ''),
            connect_timeout=10,
        )
    else:
        raise ValueError(f"Type de base non supporte: {db_type}")


def test_connection(config):
    """Teste la connexion à la BDD externe. Retourne (success, message)."""
    try:
        conn = _get_connection(config)
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        cursor.close()
        conn.close()
        return True, "Connexion reussie"
    except Exception as e:
        return False, str(e)


def fetch_external_drivers(config):
    """
    Récupère la liste des chauffeurs depuis la BDD externe.
    NOTE: La requête SQL doit être adaptée au schéma du prestataire.
    """
    try:
        conn = _get_connection(config)
        cursor = conn.cursor()
        # Requête générique - à adapter selon le schéma du prestataire
        cursor.execute("""
            SELECT id, nom, prenom
            FROM chauffeurs
            WHERE actif = 1
            ORDER BY nom
        """)
        drivers = []
        for row in cursor.fetchall():
            drivers.append({
                'externe_id': str(row[0]),
                'nom': f"{row[1]} {row[2]}".strip(),
            })
        cursor.close()
        conn.close()
        return drivers
    except Exception as e:
        logger.error(f"Erreur fetch chauffeurs externes: {e}")
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
        """Démarre le thread de synchronisation."""
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._run_loop, daemon=True, name='bibile-sync')
        self._thread.start()
        logger.info("SyncManager demarré")

    def stop(self):
        """Arrête le thread de synchronisation."""
        self._stop_event.set()
        self._trigger_event.set()  # Débloquer le wait
        if self._thread:
            self._thread.join(timeout=5)

    def trigger_sync(self):
        """Déclenche une synchronisation immédiate."""
        self._trigger_event.set()

    def get_status(self):
        """Retourne le statut courant."""
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
        """Boucle principale du thread de synchronisation."""
        while not self._stop_event.is_set():
            config = get_external_config(self.db_path)
            interval = 300  # 5 min par défaut

            if config and config.get('actif'):
                interval = config.get('sync_interval_minutes', 60) * 60
                try:
                    self._do_sync(config)
                except Exception as e:
                    self._last_error = str(e)
                    logger.error(f"Erreur sync: {e}")

            # Attendre l'intervalle ou un déclenchement manuel
            self._trigger_event.wait(timeout=interval)
            self._trigger_event.clear()

    def _do_sync(self, config):
        """Effectue la synchronisation incrémentale."""
        self._is_syncing = True
        self._last_error = None

        try:
            conn_ext = _get_connection(config)
            cursor = conn_ext.cursor()

            # Récupérer les chauffeurs sélectionnés pour la synchro
            chauffeurs_sync = list_chauffeurs_sync(self.db_path)
            selected = [c for c in chauffeurs_sync if c.get('selectionne')]

            if not selected:
                self._is_syncing = False
                return

            # Déterminer la date de début de synchro
            derniere_sync = config.get('derniere_sync')
            if derniere_sync:
                date_debut = derniere_sync[:10]  # YYYY-MM-DD
            else:
                # Première synchro : récupérer les 3 derniers mois
                date_debut = (datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d')

            # Pour chaque chauffeur sélectionné, récupérer les données
            conn_local = get_db(self.db_path)

            for ch in selected:
                externe_id = ch['externe_id']

                # S'assurer que le chauffeur existe localement
                local = conn_local.execute(
                    "SELECT id FROM chauffeurs WHERE externe_id = ?", (externe_id,)
                ).fetchone()

                if not local:
                    # Créer le chauffeur localement
                    parts = ch['nom'].split(' ', 1)
                    chauffeur_id = save_chauffeur(self.db_path, {
                        'nom': parts[0],
                        'prenom': parts[1] if len(parts) > 1 else '',
                        'externe_id': externe_id,
                    })
                else:
                    chauffeur_id = local['id']

                # Requête sur la BDD externe (à adapter au schéma du prestataire)
                try:
                    cursor.execute("""
                        SELECT date_donnee, kilometres, consommation, duree_minutes
                        FROM donnees_transport
                        WHERE chauffeur_id = %s AND date_donnee >= %s
                        ORDER BY date_donnee
                    """, (externe_id, date_debut))

                    records = []
                    for row in cursor.fetchall():
                        records.append({
                            'chauffeur_id': chauffeur_id,
                            'date_donnee': str(row[0]),
                            'kilometres': float(row[1] or 0),
                            'consommation_carburant': float(row[2] or 0),
                            'duree_travail_minutes': int(row[3] or 0),
                            'source_externe_id': externe_id,
                        })

                    if records:
                        upsert_donnees_transport(self.db_path, records)

                except Exception as e:
                    logger.warning(f"Erreur sync chauffeur {externe_id}: {e}")

            conn_local.close()
            cursor.close()
            conn_ext.close()

            # Mettre à jour la date de dernière synchro
            update_derniere_sync(self.db_path)
            self._last_sync = datetime.now().isoformat()

        except Exception as e:
            self._last_error = str(e)
            raise
        finally:
            self._is_syncing = False
