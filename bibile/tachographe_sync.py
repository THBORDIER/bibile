#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bibile - Service de synchronisation chronotachygraphe

Se connecte a une base de donnees externe pour recuperer :
- Temps de conduite par chauffeur
- Consommation de carburant par vehicule
- Kilometrage

La BDD externe a une retention de 3 mois, donc on archive dans SQLite.
"""

import json
from datetime import datetime, date, timedelta
from pathlib import Path


class TachographeSync:
    """Service de synchronisation avec la BDD chronotachygraphe externe"""

    def __init__(self, db, config_path=None):
        self.db = db
        self.config = {}
        self.connection = None

        if config_path:
            self._load_config(config_path)

    def _load_config(self, config_path):
        """Charge la configuration de connexion depuis un fichier JSON"""
        path = Path(config_path)
        if path.exists():
            with open(path, 'r') as f:
                full_config = json.load(f)
                self.config = full_config.get('tachographe', {})

    def is_configured(self):
        """Verifie si la connexion externe est configuree"""
        return bool(self.config.get('host'))

    def connect(self):
        """
        Etablit la connexion a la BDD externe.

        Supporte : postgresql, mysql, mssql, odbc
        A adapter selon le type de BDD utilisee.
        """
        db_type = self.config.get('type', '')

        if not self.is_configured():
            raise ConnectionError("Connexion chronotachygraphe non configuree. Editez config.json.")

        try:
            if db_type == 'postgresql':
                import psycopg2
                self.connection = psycopg2.connect(
                    host=self.config['host'],
                    port=self.config.get('port', 5432),
                    database=self.config['database'],
                    user=self.config['user'],
                    password=self.config['password']
                )
            elif db_type in ('mysql', 'mariadb'):
                import pymysql
                self.connection = pymysql.connect(
                    host=self.config['host'],
                    port=self.config.get('port', 3306),
                    database=self.config['database'],
                    user=self.config['user'],
                    password=self.config['password']
                )
            elif db_type in ('mssql', 'sqlserver'):
                import pyodbc
                conn_str = (
                    f"DRIVER={{ODBC Driver 17 for SQL Server}};"
                    f"SERVER={self.config['host']},{self.config.get('port', 1433)};"
                    f"DATABASE={self.config['database']};"
                    f"UID={self.config['user']};"
                    f"PWD={self.config['password']}"
                )
                self.connection = pyodbc.connect(conn_str)
            else:
                raise ValueError(f"Type de BDD non supporte: {db_type}")

            return True

        except ImportError as e:
            raise ConnectionError(
                f"Driver non installe pour {db_type}. "
                f"Installez le package Python correspondant. Erreur: {e}"
            )

    def disconnect(self):
        """Ferme la connexion"""
        if self.connection:
            try:
                self.connection.close()
            except Exception:
                pass
            self.connection = None

    def sync(self):
        """
        Synchronise les donnees depuis la BDD externe vers SQLite.

        Retourne (nb_records, message)

        IMPORTANT: Adaptez la requete SQL ci-dessous selon le schema
        de votre base chronotachygraphe.
        """
        from models import TachographeRecord, SyncStatus, Chauffeur, Vehicule

        # Enregistrer le debut de la sync
        sync_status = SyncStatus(
            derniere_sync=datetime.now(),
            statut='running',
            message='Synchronisation en cours...'
        )
        self.db.session.add(sync_status)
        self.db.session.commit()

        try:
            if not self.is_configured():
                sync_status.statut = 'error'
                sync_status.message = 'Connexion non configuree'
                self.db.session.commit()
                return 0, 'Connexion non configuree. Editez config.json.'

            self.connect()

            cursor = self.connection.cursor()

            # ====================================================================
            # ADAPTEZ CETTE REQUETE selon le schema de votre BDD chronotachygraphe
            # ====================================================================
            # Exemple de requete - a modifier selon vos tables/colonnes :
            query = self.config.get('query', """
                SELECT
                    driver_name,
                    vehicle_plate,
                    record_date,
                    driving_time_minutes,
                    distance_km,
                    fuel_consumption_liters
                FROM tachograph_records
                WHERE record_date >= %s
                ORDER BY record_date
            """)

            # Recuperer depuis la derniere sync ou les 3 derniers mois
            last_record = self.db.session.query(
                self.db.func.max(TachographeRecord.date)
            ).scalar()

            if last_record:
                since_date = last_record
            else:
                since_date = date.today() - timedelta(days=90)

            cursor.execute(query, (since_date,))
            rows = cursor.fetchall()

            nb_imported = 0
            for row in rows:
                driver_name, vehicle_plate, record_date, driving_time, distance, fuel = row

                # Trouver ou ignorer le chauffeur/vehicule
                chauffeur = None
                vehicule = None

                if driver_name:
                    parts = driver_name.split(' ', 1)
                    if len(parts) == 2:
                        chauffeur = Chauffeur.query.filter_by(
                            prenom=parts[0], nom=parts[1], actif=True
                        ).first()

                if vehicle_plate:
                    vehicule = Vehicule.query.filter_by(
                        immatriculation=vehicle_plate, actif=True
                    ).first()

                # Eviter les doublons
                existing = TachographeRecord.query.filter_by(
                    date=record_date,
                    chauffeur_id=chauffeur.id if chauffeur else None,
                    vehicule_id=vehicule.id if vehicule else None
                ).first()

                if not existing:
                    record = TachographeRecord(
                        chauffeur_id=chauffeur.id if chauffeur else None,
                        vehicule_id=vehicule.id if vehicule else None,
                        date=record_date,
                        temps_conduite_minutes=driving_time,
                        distance_km=distance,
                        consommation_litres=fuel,
                        source_sync_date=datetime.now()
                    )
                    self.db.session.add(record)
                    nb_imported += 1

            self.db.session.commit()
            self.disconnect()

            sync_status.statut = 'success'
            sync_status.nb_records_sync = nb_imported
            sync_status.message = f'{nb_imported} enregistrement(s) importe(s)'
            self.db.session.commit()

            return nb_imported, f'{nb_imported} enregistrement(s) importe(s)'

        except Exception as e:
            self.disconnect()
            sync_status.statut = 'error'
            sync_status.message = str(e)
            self.db.session.commit()
            return 0, f'Erreur: {str(e)}'
