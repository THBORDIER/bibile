#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bibile - Modeles de base de donnees (SQLAlchemy + SQLite)
"""

from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, date

db = SQLAlchemy()


class Chauffeur(db.Model):
    __tablename__ = 'chauffeurs'

    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(100), nullable=False)
    prenom = db.Column(db.String(100), nullable=False)
    telephone = db.Column(db.String(20))
    permis_numero = db.Column(db.String(50))
    permis_expiration = db.Column(db.Date)
    actif = db.Column(db.Boolean, default=True)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    # Relations
    tachographe_records = db.relationship('TachographeRecord', backref='chauffeur', lazy=True)
    regles = db.relationship('RegleTournee', backref='chauffeur', lazy=True)

    def to_dict(self):
        return {
            'id': self.id,
            'nom': self.nom,
            'prenom': self.prenom,
            'telephone': self.telephone or '',
            'permis_numero': self.permis_numero or '',
            'permis_expiration': self.permis_expiration.isoformat() if self.permis_expiration else '',
            'actif': self.actif,
            'notes': self.notes or '',
            'created_at': self.created_at.isoformat() if self.created_at else '',
            'nom_complet': f"{self.prenom} {self.nom}"
        }


class Vehicule(db.Model):
    __tablename__ = 'vehicules'

    id = db.Column(db.Integer, primary_key=True)
    immatriculation = db.Column(db.String(20), unique=True, nullable=False)
    marque = db.Column(db.String(50))
    modele = db.Column(db.String(50))
    type_vehicule = db.Column(db.String(30))  # Porteur, Semi, VL
    capacite_palettes = db.Column(db.Integer)
    capacite_kg = db.Column(db.Float)
    actif = db.Column(db.Boolean, default=True)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    # Relations
    tachographe_records = db.relationship('TachographeRecord', backref='vehicule', lazy=True)
    regles = db.relationship('RegleTournee', backref='vehicule', lazy=True)

    def to_dict(self):
        return {
            'id': self.id,
            'immatriculation': self.immatriculation,
            'marque': self.marque or '',
            'modele': self.modele or '',
            'type_vehicule': self.type_vehicule or '',
            'capacite_palettes': self.capacite_palettes or 0,
            'capacite_kg': self.capacite_kg or 0,
            'actif': self.actif,
            'notes': self.notes or '',
            'created_at': self.created_at.isoformat() if self.created_at else '',
            'description': f"{self.immatriculation} ({self.marque} {self.modele})".strip()
        }


class TachographeRecord(db.Model):
    __tablename__ = 'tachographe_records'

    id = db.Column(db.Integer, primary_key=True)
    chauffeur_id = db.Column(db.Integer, db.ForeignKey('chauffeurs.id'))
    vehicule_id = db.Column(db.Integer, db.ForeignKey('vehicules.id'))
    date = db.Column(db.Date, nullable=False)
    temps_conduite_minutes = db.Column(db.Integer)
    distance_km = db.Column(db.Float)
    consommation_litres = db.Column(db.Float)
    source_sync_date = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.now)

    def to_dict(self):
        return {
            'id': self.id,
            'chauffeur_id': self.chauffeur_id,
            'vehicule_id': self.vehicule_id,
            'chauffeur_nom': self.chauffeur.to_dict()['nom_complet'] if self.chauffeur else '',
            'vehicule_immat': self.vehicule.immatriculation if self.vehicule else '',
            'date': self.date.isoformat() if self.date else '',
            'temps_conduite_minutes': self.temps_conduite_minutes or 0,
            'temps_conduite_heures': round((self.temps_conduite_minutes or 0) / 60, 1),
            'distance_km': self.distance_km or 0,
            'consommation_litres': self.consommation_litres or 0,
        }


class RegleTournee(db.Model):
    __tablename__ = 'regles_tournees'

    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(100), nullable=False)
    livraison = db.Column(db.String(50))  # BREVET, TRANSIT, etc.
    ville_pattern = db.Column(db.String(100))  # pattern ville (optionnel)
    chauffeur_id = db.Column(db.Integer, db.ForeignKey('chauffeurs.id'), nullable=True)
    vehicule_id = db.Column(db.Integer, db.ForeignKey('vehicules.id'), nullable=True)
    jour_semaine = db.Column(db.Integer, nullable=True)  # 0=lundi, 6=dimanche
    actif = db.Column(db.Boolean, default=True)
    priorite = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.now)

    JOURS = ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi', 'Dimanche']

    def to_dict(self):
        return {
            'id': self.id,
            'nom': self.nom,
            'livraison': self.livraison or '',
            'ville_pattern': self.ville_pattern or '',
            'chauffeur_id': self.chauffeur_id,
            'vehicule_id': self.vehicule_id,
            'chauffeur_nom': self.chauffeur.to_dict()['nom_complet'] if self.chauffeur else '',
            'vehicule_immat': self.vehicule.immatriculation if self.vehicule else '',
            'jour_semaine': self.jour_semaine,
            'jour_semaine_nom': self.JOURS[self.jour_semaine] if self.jour_semaine is not None else '',
            'actif': self.actif,
            'priorite': self.priorite,
        }

    def match(self, livraison, ville, jour_semaine=None):
        """Verifie si cette regle s'applique a un enlevement"""
        if not self.actif:
            return False
        if self.livraison and self.livraison.upper() != (livraison or '').upper():
            return False
        if self.ville_pattern and self.ville_pattern.upper() not in (ville or '').upper():
            return False
        if self.jour_semaine is not None and self.jour_semaine != jour_semaine:
            return False
        return True


class SyncStatus(db.Model):
    __tablename__ = 'sync_status'

    id = db.Column(db.Integer, primary_key=True)
    derniere_sync = db.Column(db.DateTime)
    nb_records_sync = db.Column(db.Integer, default=0)
    statut = db.Column(db.String(20))  # success, error, running
    message = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.now)

    def to_dict(self):
        return {
            'id': self.id,
            'derniere_sync': self.derniere_sync.isoformat() if self.derniere_sync else '',
            'nb_records_sync': self.nb_records_sync,
            'statut': self.statut or '',
            'message': self.message or '',
        }
