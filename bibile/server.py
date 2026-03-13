#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bibile - Serveur Flask pour l'extracteur d'enlèvements

RÈGLES IMPORTANTES :
--------------------
1. Calcul des palettes dans la colonne Excel "NOMBRE DE PALETTES" :
   - PART PALLET = 0
   - HALF PALLET = 1
   - EURO/VMF = nombre indiqué
   - LOOSE LOADED = nombre indiqué

2. Contrôle qualité avec "Au total:" :
   - Le "Au total:" du fichier source ne compte QUE les palettes pleines (EURO/VMF/LOOSE LOADED)
   - Il ignore les HALF et PART dans leur comptage
   - Donc le contrôle qualité ne vérifie que les EURO/VMF/LOOSE LOADED, pas les HALF/PART

4. Nettoyage du texte PDF :
   - Le texte copié du PDF contient des en-têtes/pieds de page répétés à chaque saut de page
   - La fonction nettoyer_texte() les supprime avant le parsing
   - Le premier en-tête est préservé (métadonnées du document)

3. Mapping des livraisons :
   - Le système extrait AUTOMATIQUEMENT les noms des destinataires depuis les sections "Livraison X"
   - Chaque fichier peut avoir un nombre différent de livraisons
   - Les noms sont extraits dynamiquement (ex: Livraison 1 → BREVET, Livraison 2 → TRANSIT, etc.)
"""

from flask import Flask, render_template, request, jsonify, send_file, send_from_directory
import os
import sys
import re
import pandas as pd
from datetime import datetime
import json
from pathlib import Path
from openpyxl.styles import Font, PatternFill, Alignment

# Flask : adapter les chemins pour le mode PyInstaller
BASE_DIR = Path(__file__).parent
if getattr(sys, '_MEIPASS', None):
    bundle_dir = Path(sys._MEIPASS) / 'bibile'
    app = Flask(__name__,
                template_folder=str(bundle_dir / 'templates'),
                static_folder=str(bundle_dir / 'static'))
else:
    app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max

# Dossiers de donnees (historique + logs)
# En mode desktop, BIBILE_DATA_DIR pointe vers %APPDATA%/Bibile
DATA_DIR = Path(os.environ.get('BIBILE_DATA_DIR', str(BASE_DIR)))
LOGS_DIR = DATA_DIR / 'logs'
HISTORIQUE_DIR = DATA_DIR / 'historique'

# Base de données SQLite
DB_PATH = Path(os.environ.get('BIBILE_DB_PATH', str(DATA_DIR / 'bibile.db')))

# Créer les dossiers s'ils n'existent pas
LOGS_DIR.mkdir(exist_ok=True)
HISTORIQUE_DIR.mkdir(exist_ok=True)

# Initialiser la DB
try:
    from bibile.database import init_db, save_extraction, list_extractions, get_extraction_data, get_extraction_log, generate_excel_from_db, get_statistiques, find_duplicates, update_enlevements
    from bibile.database_tournees import (
        list_chauffeurs, save_chauffeur, delete_chauffeur,
        list_vehicules, save_vehicule, delete_vehicule,
        list_tournees, create_tournee, update_tournee, delete_tournee,
        assign_enlevements, remove_enlevement, reorder_enlevements,
        get_unassigned_enlevements, list_zones, save_zone, delete_zone,
        list_ville_zone_mapping, save_ville_zone, get_villes_inconnues,
        auto_distribuer, get_external_config, save_external_config,
        list_chauffeurs_sync, save_chauffeurs_sync_selection,
        list_vehicules_sync, save_vehicules_sync_selection,
        get_donnees_transport, get_extractions_for_date,
    )
    from bibile.external_sync import SyncManager, test_connection, fetch_external_vehicles, fetch_vehicle_positions
except ImportError:
    from database import init_db, save_extraction, list_extractions, get_extraction_data, get_extraction_log, generate_excel_from_db, get_statistiques, find_duplicates, update_enlevements
    from database_tournees import (
        list_chauffeurs, save_chauffeur, delete_chauffeur,
        list_vehicules, save_vehicule, delete_vehicule,
        list_tournees, create_tournee, update_tournee, delete_tournee,
        assign_enlevements, remove_enlevement, reorder_enlevements,
        get_unassigned_enlevements, list_zones, save_zone, delete_zone,
        list_ville_zone_mapping, save_ville_zone, get_villes_inconnues,
        auto_distribuer, get_external_config, save_external_config,
        list_chauffeurs_sync, save_chauffeurs_sync_selection,
        list_vehicules_sync, save_vehicules_sync_selection,
        get_donnees_transport, get_extractions_for_date,
    )
    from external_sync import SyncManager, test_connection, fetch_external_vehicles, fetch_vehicle_positions
init_db(DB_PATH)

# Gestionnaire de synchro (initialisé au démarrage)
sync_manager = None



def log_to_file(message, log_file):
    """Ajoute un message au fichier de log"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    with open(log_file, 'a', encoding='utf-8') as f:
        f.write(f"[{timestamp}] {message}\n")


def nettoyer_texte(texte):
    """
    Supprime les en-têtes et pieds de page répétés dans le texte extrait du PDF Hillebrand.

    Les blocs en-tête/pied de page suivent ce schéma :
    - [optionnel] Code-barres : FRBG164812 / µFRBG164812JÄ
    - Pied : "Hillebrand Gori France SAS - 11 Rue Louis et Gaston Chevrolet..."
    - Pied : "T +33 380244300 - VAT number ... Page XX/YY"
    - En-tête : "Date: DD/mois/YYYY HH:MM"
    - En-tête : "A: Brevet SA Crissey - ..."
    - En-tête : "Notre Réf: FRBGXXXXXX (Merci de reporter...)"
    - En-tête : "De: Laurie Jolliot - ..."
    - En-tête : "Instructions de transport"

    Le premier en-tête du document (lignes 1-14) est préservé car il ne contient
    pas la ligne de pied de page "Hillebrand Gori France SAS...Chevrolet...Beaune".
    Cette ligne n'apparaît qu'aux sauts de page.
    """
    lignes = texte.split('\n')
    lignes_nettoyees = []

    i = 0
    while i < len(lignes):
        ligne = lignes[i].strip()

        # Détecter le pied de page Hillebrand (signature unique, n'apparaît qu'aux sauts de page)
        if 'Hillebrand Gori France SAS' in ligne and 'Chevrolet' in ligne and 'Beaune' in ligne:
            # Vérifier que la ligne suivante est bien le numéro de page
            if i + 1 < len(lignes) and 'VAT number' in lignes[i + 1] and 'Page' in lignes[i + 1]:
                # Supprimer aussi les lignes de code-barres qui précèdent le pied de page
                # (ex: FRBG164812, µFRBG164812JÄ)
                while lignes_nettoyees and re.match(r'^µ?[A-Z]{3,5}\d{5,7}', lignes_nettoyees[-1].strip()):
                    lignes_nettoyees.pop()

                # Sauter le bloc pied + en-tête (jusqu'à "Instructions de transport")
                j = i
                while j < len(lignes) and j < i + 12:
                    if lignes[j].strip() == 'Instructions de transport':
                        j += 1  # sauter aussi cette ligne
                        break
                    j += 1
                i = j
                continue

        lignes_nettoyees.append(lignes[i])
        i += 1

    return '\n'.join(lignes_nettoyees)


def extraire_totaux_livraisons(texte):
    """Extrait les totaux ET destinataires des sections Livraison pour contrôle qualité"""
    lignes = texte.split('\n')
    totaux_livraisons = {}
    mapping_destinataires = {}  # num_livraison -> nom destinataire

    i = 0
    while i < len(lignes):
        ligne = lignes[i].strip()

        # Chercher "Livraison X" seul sur une ligne (pas "Fera partie de la Livraison")
        match = re.match(r'^Livraison\s+(\d+)$', ligne)
        if match:
            num_livraison = match.group(1)

            # Extraire le destinataire (ligne après "Au total:")
            destinataire = ""
            for k in range(i+1, min(i+10, len(lignes))):
                if 'Au total:' in lignes[k]:
                    # Extraire les totaux
                    match_total = re.search(r'Au total:\s*(\d+)\s*Palettes?\s+([0-9\.]+)\s*kg.*?([0-9\.]+)\s*Colis', lignes[k])
                    if match_total:
                        totaux_livraisons[num_livraison] = {
                            'palettes': int(match_total.group(1)),
                            'poids': int(match_total.group(2).replace('.', '')),
                            'colis': int(match_total.group(3).replace('.', ''))
                        }

                    # Ligne suivante = destinataire (ex: "Brevet Châtenoy-le-Royal")
                    if k + 1 < len(lignes):
                        dest_ligne = lignes[k + 1].strip()
                        if dest_ligne:
                            nom_destinataire = ""

                            # Si c'est une ligne Hillebrand, extraire le mot-clé (Transit, Chevrolet, Storage)
                            if dest_ligne.startswith('Hillebrand'):
                                # Chercher des mots-clés spécifiques
                                mots = dest_ligne.split()
                                for mot in mots:
                                    mot_upper = mot.upper()
                                    # Mots-clés significatifs pour les livraisons internes
                                    if mot_upper in ['TRANSIT', 'CHEVROLET', 'STORAGE', 'GORI']:
                                        if mot_upper == 'CHEVROLET':
                                            nom_destinataire = 'CHEVROLET'
                                            break
                                        elif mot_upper == 'TRANSIT':
                                            nom_destinataire = 'TRANSIT'
                                            break
                                        elif mot_upper == 'STORAGE':
                                            nom_destinataire = 'STORAGE'
                                            break

                                # Si aucun mot-clé trouvé, utiliser "HILLEBRAND"
                                if not nom_destinataire:
                                    nom_destinataire = 'HILLEBRAND'
                            else:
                                # Sinon, prendre le premier mot (ex: "Brevet Châtenoy-le-Royal" → "BREVET")
                                premier_mot = dest_ligne.split()[0].upper() if dest_ligne.split() else ""
                                if premier_mot:
                                    nom_destinataire = premier_mot

                            if nom_destinataire:
                                mapping_destinataires[num_livraison] = nom_destinataire
                                destinataire = nom_destinataire
                    break

        i += 1

    return totaux_livraisons, mapping_destinataires


def controler_totaux(lignes_tableau, totaux_livraisons, mapping_destinataires, log_file):
    """Contrôle qualité : compare les totaux extraits avec les totaux des sections Livraison"""
    log_to_file("", log_file)
    log_to_file(">> Contrôle qualité des totaux par livraison", log_file)

    if not totaux_livraisons:
        log_to_file("   Aucune section Livraison trouvée - contrôle ignoré", log_file)
        return []

    # Calculer les totaux par livraison depuis les données extraites
    calcules = {}
    for ligne in lignes_tableau:
        livraison = ligne.get('LIVRAISON ASSOCIÉE', '')
        if not livraison:
            continue

        if livraison not in calcules:
            calcules[livraison] = {'palettes': 0, 'poids': 0, 'colis': 0}

        # Compter les palettes pour le contrôle qualité
        # RÈGLE: Le "Au total:" du fichier source ne compte QUE les palettes pleines (EURO/VMF/LOOSE LOADED)
        # Il ignore les HALF et PART dans leur total
        # Donc pour le contrôle, on ne compte que si type = EURO, VMF ou LOOSE LOADED
        type_pal = ligne.get('TYPE DE PALETTES', '')
        if type_pal in ['EURO', 'VMF', 'LOOSE LOADED']:
            try:
                nb_pal = int(ligne.get('NOMBRE DE PALETTES', 0) or 0)
                calcules[livraison]['palettes'] += nb_pal
            except:
                pass

        try:
            poids = int(ligne.get('POIDS TOTAL (KG)', 0) or 0)
            calcules[livraison]['poids'] += poids
        except:
            pass

        try:
            colis = int(ligne.get('NOMBRE DE COLIS', 0) or 0)
            calcules[livraison]['colis'] += colis
        except:
            pass

    erreurs_controle = []

    # Utiliser le mapping dynamique pour comparer les totaux
    for num, attendu in totaux_livraisons.items():
        # Trouver le nom de la livraison depuis le mapping dynamique
        livraison_nom = mapping_destinataires.get(num, f"LIVRAISON {num}")

        calcule = calcules.get(livraison_nom, {'palettes': 0, 'poids': 0, 'colis': 0})

        log_to_file(f"   Livraison {num} ({livraison_nom}):", log_file)
        log_to_file(f"     Attendu  : {attendu['palettes']} pal, {attendu['poids']} kg, {attendu['colis']} colis", log_file)
        log_to_file(f"     Calculé  : {calcule['palettes']} pal, {calcule['poids']} kg, {calcule['colis']} colis", log_file)

        # Vérifier les écarts
        ecart_palettes = attendu['palettes'] != calcule['palettes']
        ecart_poids = attendu['poids'] != calcule['poids']
        ecart_colis = attendu['colis'] != calcule['colis']

        if ecart_palettes:
            msg = f"ERREUR Livraison {num}: {calcule['palettes']} palettes au lieu de {attendu['palettes']}"
            log_to_file(f"     [X] {msg}", log_file)

            # Note spéciale si seules les palettes diffèrent (poids/colis OK)
            if not ecart_poids and not ecart_colis:
                log_to_file(f"         NOTE: Poids et colis sont corrects. Ecart probable du a:", log_file)
                log_to_file(f"         - Convention de comptage HALF/PART dans 'Au total:' du fichier source", log_file)
                log_to_file(f"         - Ou erreur dans le total affiche dans le fichier source", log_file)
                log_to_file(f"         L'extraction est correcte (poids/colis valides)", log_file)

            erreurs_controle.append(msg)
        elif ecart_poids:
            msg = f"ATTENTION Livraison {num}: {calcule['poids']} kg au lieu de {attendu['poids']} kg"
            log_to_file(f"     [!] {msg}", log_file)
            erreurs_controle.append(msg)
        elif ecart_colis:
            msg = f"ATTENTION Livraison {num}: {calcule['colis']} colis au lieu de {attendu['colis']}"
            log_to_file(f"     [!] {msg}", log_file)
            erreurs_controle.append(msg)
        else:
            log_to_file(f"     [OK]", log_file)

    return erreurs_controle


def extraire_info_enlevement(lignes, index_debut, mapping_destinataires=None):
    """
    Extrait toutes les informations d'un enlèvement de manière structurée
    Retourne: (index_fin, infos_enlevement, liste_palettes)
    """
    infos = {
        'num_enlevement': '',
        'societe': '',
        'ville': '',
        'telephone': '',
        'poids_total': '',
        'colis_total': '',
        'index_fin': index_debut
    }
    palettes = []

    # Trouver la fin de cet enlèvement (= début du prochain enlèvement)
    index_fin = len(lignes)
    for k in range(index_debut + 1, len(lignes)):
        if re.match(r'^Enlèvement\s+\d+\s+', lignes[k]):
            index_fin = k
            break

    infos['index_fin'] = index_fin

    # ÉTAPE 1: Extraire numéro + société sur la ligne "Enlèvement X ..."
    ligne_enlevement = lignes[index_debut]
    match = re.search(r'Enlèvement\s+(\d+)\s+(.+)', ligne_enlevement)
    if match:
        infos['num_enlevement'] = match.group(1)
        infos['societe'] = match.group(2).strip().upper()

    # ÉTAPE 1b: Chercher "Au total:" pour infos globales
    for k in range(index_debut, min(index_debut + 10, index_fin)):
        if 'Au total:' in lignes[k]:
            match_total = re.search(r'Au total:.*?([0-9\.]+)\s*kg.*?([0-9\.]+)\s*Colis', lignes[k])
            if match_total:
                infos['poids_total'] = match_total.group(1).replace('.', '')
                infos['colis_total'] = match_total.group(2).replace('.', '')
            break

    # ÉTAPE 2: Chercher VILLE (mot-clé: code postal français = 5 chiffres seuls + ville)
    # Ignorer les lignes de pied de page et références
    for k in range(index_debut, index_fin):
        ligne_k = lignes[k]

        # Ignorer les pieds de page et références
        if 'Hillebrand Gori France SAS' in ligne_k or 'VAT number' in ligne_k:
            continue
        if 'Notre Réf:' in ligne_k or 'Notre Ref:' in ligne_k:
            continue

        # Code postal français : exactement 5 chiffres en début de ligne ou après espace
        match = re.match(r'^(\d{5})\s+(.+)', ligne_k)
        if match:
            ville = match.group(2).strip()
            ville = re.sub(r'\s*France\s*$', '', ville, flags=re.IGNORECASE)
            infos['ville'] = ville.upper()
            break

    # ÉTAPE 3: Chercher TÉLÉPHONE (mot-clé: T: +33)
    for k in range(index_debut, index_fin):
        match = re.search(r'T:\s*(\+?33[0-9\s\.]+)', lignes[k])
        if match:
            telephone = match.group(1).strip()
            telephone = re.sub(r'\s+', '.', telephone)
            infos['telephone'] = telephone
            break

    # ÉTAPE 4: Extraire CHAQUE palette dans cet enlèvement
    j = index_debut + 1
    while j < index_fin:
        ligne = lignes[j].strip()

        # Arrêter si on rencontre une section "Livraison X" (résumé des livraisons)
        if re.match(r'^Livraison\s+\d+$', ligne):
            break

        # Détection de palette avec mot-clé exact
        match_palette = None
        type_palette = ""
        nb_palettes = ""

        # Pattern: "Part pallet"
        if re.match(r'^Part\s+pallet', ligne, re.IGNORECASE):
            match_palette = True
            type_palette = "PART PALLET"
            nb_palettes = "0"

        # Pattern: "Half pallet" ou "1 Half pallet"
        elif re.match(r'^(\d+\s+)?Half\s+pallet', ligne, re.IGNORECASE):
            match_palette = True
            type_palette = "HALF PALLET"
            nb_palettes = "1"

        # Pattern: "X Euro pallet" ou "X Euro Pallet"
        elif re.match(r'^(\d+)\s+Euro\s+[Pp]allet', ligne, re.IGNORECASE):
            match = re.match(r'^(\d+)\s+Euro\s+[Pp]allet', ligne, re.IGNORECASE)
            match_palette = True
            type_palette = "EURO"
            nb_palettes = match.group(1)

        # Pattern: "X VMF pallet" ou "X VMF Pallet"
        elif re.match(r'^(\d+)\s+VMF\s+[Pp]allet', ligne, re.IGNORECASE):
            match = re.match(r'^(\d+)\s+VMF\s+[Pp]allet', ligne, re.IGNORECASE)
            match_palette = True
            type_palette = "VMF"
            nb_palettes = match.group(1)

        # Pattern: "X Loose loaded" (avec ou sans "pallet")
        elif re.match(r'^(\d+)\s+Loose\s+loaded', ligne, re.IGNORECASE):
            match = re.match(r'^(\d+)\s+Loose\s+loaded', ligne, re.IGNORECASE)
            match_palette = True
            type_palette = "LOOSE LOADED"
            nb_palettes = match.group(1)

        # Pattern: "X pallet" générique (par défaut EURO)
        elif re.match(r'^(\d+)\s+[Pp]allet', ligne, re.IGNORECASE):
            match = re.match(r'^(\d+)\s+[Pp]allet', ligne, re.IGNORECASE)
            match_palette = True
            type_palette = "EURO"
            nb_palettes = match.group(1)

        if match_palette:
            # ÉTAPE 4a: Extraire POIDS et COLIS sur la ligne de palette
            poids = ""
            colis = ""

            match_poids = re.search(r'([0-9\.]+)\s*kg', ligne, re.IGNORECASE)
            match_colis = re.search(r'(\d+)\s*Colis', ligne, re.IGNORECASE)

            if match_poids:
                poids = match_poids.group(1).replace('.', '')
            if match_colis:
                colis = match_colis.group(1)

            # Si pas de poids/colis sur la ligne, utiliser les totaux de l'enlèvement
            if not poids and infos['poids_total']:
                poids = infos['poids_total']
            if not colis and infos['colis_total']:
                colis = infos['colis_total']

            # ÉTAPE 4b: Chercher NOTRE RÉF (mot-clé: "Notre Réf:" dans les 20 lignes suivantes)
            # IMPORTANT: Ignorer les références globales des en-têtes de page
            # qui contiennent "(Merci de reporter"
            notre_ref = ""
            for k in range(j + 1, min(j + 20, index_fin)):
                if 'Notre Réf:' in lignes[k] or 'Notre Ref:' in lignes[k]:
                    # Ignorer la référence globale de l'en-tête de page
                    if 'Merci de reporter' in lignes[k]:
                        continue
                    match_ref = re.search(r'Notre Ré[fF]:\s*([A-Z0-9/+\-]+)', lignes[k])
                    if match_ref:
                        notre_ref = match_ref.group(1).split('+')[0].strip()
                    break

            # ÉTAPE 4c: Chercher LIVRAISON (mot-clé: "Fera partie de la Livraison X")
            livraison = ""
            for k in range(j + 1, min(j + 20, index_fin)):
                if 'Fera partie de la Livraison' in lignes[k]:
                    match_liv = re.search(r'Livraison\s+(\d+)', lignes[k])
                    if match_liv:
                        num_livraison = match_liv.group(1)

                        # Utiliser le mapping dynamique si disponible
                        if mapping_destinataires and num_livraison in mapping_destinataires:
                            livraison = mapping_destinataires[num_livraison]
                        else:
                            # Fallback : garder le numéro si pas de mapping
                            livraison = f"LIVRAISON {num_livraison}"
                    break

            # Ajouter cette palette à la liste
            palettes.append({
                'type': type_palette,
                'nombre': nb_palettes,
                'poids': poids,
                'colis': colis,
                'notre_ref': notre_ref,
                'livraison': livraison
            })

        j += 1

    return infos, palettes


def parser_texte(texte, log_file):
    """Parse le texte et extrait les informations de manière structurée"""
    log_to_file(">> Début de l'analyse du texte", log_file)

    # Nettoyer les en-têtes/pieds de page répétés du PDF
    texte_brut_lignes = len(texte.split('\n'))
    texte = nettoyer_texte(texte)

    lignes = texte.split('\n')
    log_to_file(f"OK Texte analysé: {len(lignes)} lignes ({texte_brut_lignes} avant nettoyage)", log_file)

    # ÉTAPE 1: Extraire les totaux ET mapping des destinataires des sections Livraison
    totaux_livraisons, mapping_destinataires = extraire_totaux_livraisons(texte)
    if totaux_livraisons:
        log_to_file(f"OK {len(totaux_livraisons)} sections Livraison trouvées pour contrôle", log_file)
        for num, dest in mapping_destinataires.items():
            log_to_file(f"   Livraison {num} -> {dest}", log_file)

    lignes_tableau = []
    log_to_file(">> Recherche des enlèvements...", log_file)

    i = 0
    while i < len(lignes):
        # Chercher le mot-clé "Enlèvement X"
        if re.match(r'^Enlèvement\s+\d+', lignes[i]):
            # Extraire toutes les infos de cet enlèvement
            infos, palettes = extraire_info_enlevement(lignes, i, mapping_destinataires)

            log_to_file(f"  -> Enlèvement {infos['num_enlevement']}: {infos['societe']}", log_file)
            log_to_file(f"     Ville: {infos['ville']}", log_file)
            log_to_file(f"     {len(palettes)} palette(s) trouvée(s)", log_file)

            # Créer une ligne dans le tableau pour CHAQUE palette
            for palette in palettes:
                ligne_data = {
                    'N° ENLÈVEMENT': infos['num_enlevement'],
                    'NOTRE RÉFÉRENCE': palette['notre_ref'],
                    'SOCIÉTÉ / DOMAINE': infos['societe'],
                    'VILLE': infos['ville'],
                    'NOMBRE DE PALETTES': palette['nombre'],
                    'TYPE DE PALETTES': palette['type'],
                    'POIDS TOTAL (KG)': palette['poids'],
                    'NOMBRE DE COLIS': palette['colis'],
                    'LIVRAISON ASSOCIÉE': palette['livraison'],
                    'TÉLÉPHONE': infos['telephone']
                }

                lignes_tableau.append(ligne_data)
                log_to_file(f"       • {palette['nombre']} {palette['type']} - {palette['poids']} kg - Réf: {palette['notre_ref']}", log_file)

            # Passer à la fin de cet enlèvement
            i = infos['index_fin']
        else:
            i += 1

    log_to_file(f"OK {len(lignes_tableau)} lignes de palettes extraites", log_file)

    # ÉTAPE 2: Contrôle qualité avec les totaux
    erreurs_controle = controler_totaux(lignes_tableau, totaux_livraisons, mapping_destinataires, log_file)

    return lignes_tableau, erreurs_controle


def generer_excel(lignes_tableau, nom_fichier, log_file):
    """Génère le fichier Excel"""
    log_to_file(f">> Génération du fichier Excel: {nom_fichier}", log_file)

    df = pd.DataFrame(lignes_tableau)

    # Trier par numéro d'enlèvement
    df['N° ENLÈVEMENT'] = pd.to_numeric(df['N° ENLÈVEMENT'], errors='coerce')
    df = df.sort_values('N° ENLÈVEMENT')

    df['NOMBRE DE PALETTES'] = pd.to_numeric(df['NOMBRE DE PALETTES'], errors='coerce')
    df['POIDS TOTAL (KG)'] = pd.to_numeric(df['POIDS TOTAL (KG)'], errors='coerce')
    df['NOMBRE DE COLIS'] = pd.to_numeric(df['NOMBRE DE COLIS'], errors='coerce')

    with pd.ExcelWriter(nom_fichier, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Enlèvements')

        workbook = writer.book
        worksheet = writer.sheets['Enlèvements']

        # Ajuster les largeurs de colonnes
        colonnes_largeur = {
            'A': 15, 'B': 18, 'C': 35, 'D': 25, 'E': 10,
            'F': 15, 'G': 12, 'H': 12, 'I': 18, 'J': 18,
        }

        for col, width in colonnes_largeur.items():
            worksheet.column_dimensions[col].width = width

        worksheet.auto_filter.ref = worksheet.dimensions

        derniere_ligne = len(df) + 2

        # Ligne de totaux
        gris = PatternFill(start_color='E0E0E0', end_color='E0E0E0', fill_type='solid')

        worksheet[f'A{derniere_ligne}'] = 'TOTAL'
        worksheet[f'E{derniere_ligne}'] = f'=SUBTOTAL(109,E2:E{derniere_ligne-1})'
        worksheet[f'G{derniere_ligne}'] = f'=SUBTOTAL(109,G2:G{derniere_ligne-1})'
        worksheet[f'H{derniere_ligne}'] = f'=SUBTOTAL(109,H2:H{derniere_ligne-1})'

        for col in ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J']:
            cell = worksheet[f'{col}{derniere_ligne}']
            cell.font = Font(bold=True, size=11)
            cell.fill = gris
            cell.alignment = Alignment(horizontal='center')

    log_to_file(f"OK Fichier Excel créé avec succès!", log_file)
    log_to_file(f"  -> {len(df)} lignes exportées + ligne de totaux dynamiques", log_file)
    log_to_file(f"  -> Filtres activés sur toutes les colonnes", log_file)


# Routes
@app.route('/')
def index():
    return render_template('index.html', active_page='accueil')


@app.route('/aide')
def aide():
    return render_template('aide.html', active_page='aide')


@app.route('/historique')
def historique():
    return render_template('historique.html', active_page='historique')


@app.route('/donnees')
def donnees():
    return render_template('donnees.html', active_page='donnees')


@app.route('/statistiques')
def statistiques():
    return render_template('statistiques.html', active_page='statistiques')


@app.route('/api/statistiques')
def api_statistiques():
    try:
        date_debut = request.args.get('date_debut')
        date_fin = request.args.get('date_fin')
        stats = get_statistiques(DB_PATH, date_debut, date_fin)
        return jsonify(stats)
    except Exception as e:
        return jsonify({'erreur': str(e)}), 500


@app.route('/upload-pdf', methods=['POST'])
def upload_pdf():
    """Extrait le texte d'un fichier PDF uploadé."""
    try:
        fichier = request.files.get('pdf')
        if not fichier:
            return jsonify({'erreur': 'Aucun fichier fourni'}), 400

        if not fichier.filename.lower().endswith('.pdf'):
            return jsonify({'erreur': 'Le fichier doit être un PDF'}), 400

        import fitz
        doc = fitz.open(stream=fichier.read(), filetype="pdf")
        texte = "\n".join(page.get_text() for page in doc)
        doc.close()

        if not texte.strip():
            return jsonify({'erreur': 'Aucun texte extractible dans ce PDF'}), 400

        return jsonify({'texte': texte})

    except Exception as e:
        return jsonify({'erreur': f'Erreur lecture PDF: {str(e)}'}), 500


# Stockage temporaire des sessions de génération (pour le workflow doublons)
_sessions_temp = {}


def _parse_and_log(texte):
    """Parse le texte et génère le log. Retourne (lignes, erreurs, nom_excel, chemin_excel, chemin_log, log_contenu)."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    nom_excel = f"Enlevements_{timestamp}.xlsx"
    nom_log = f"log_{timestamp}.md"

    chemin_excel = HISTORIQUE_DIR / nom_excel
    chemin_log = LOGS_DIR / nom_log

    with open(chemin_log, 'w', encoding='utf-8') as f:
        f.write(f"# Log de génération - {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n\n")

    log_to_file("=" * 70, chemin_log)
    log_to_file("BIBILE - Extracteur d'enlèvements Hillebrand", chemin_log)
    log_to_file("=" * 70, chemin_log)
    log_to_file("", chemin_log)

    lignes_tableau, erreurs_controle = parser_texte(texte, chemin_log)

    log_to_file("", chemin_log)
    log_to_file("=" * 70, chemin_log)
    if erreurs_controle:
        log_to_file("TERMINE AVEC ALERTES!", chemin_log)
        for erreur in erreurs_controle:
            log_to_file(f"  {erreur}", chemin_log)
    else:
        log_to_file("TERMINE - Tous les controles OK!", chemin_log)
    log_to_file(f"Fichier cree: {nom_excel}", chemin_log)
    log_to_file("=" * 70, chemin_log)

    log_contenu = None
    if chemin_log.exists():
        with open(chemin_log, 'r', encoding='utf-8') as f:
            log_contenu = f.read()

    return lignes_tableau, erreurs_controle, nom_excel, chemin_excel, chemin_log, log_contenu


def _finalize_generation(lignes_tableau, nom_excel, chemin_excel, chemin_log, log_contenu):
    """Génère l'Excel, sauvegarde en DB, et retourne le fichier."""
    generer_excel(lignes_tableau, chemin_excel, chemin_log)
    save_extraction(DB_PATH, nom_excel, datetime.now(), lignes_tableau, log_contenu)
    return send_file(
        chemin_excel,
        as_attachment=True,
        download_name=nom_excel,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )


@app.route('/generer', methods=['POST'])
def generer():
    try:
        data = request.get_json()
        texte = data.get('texte', '').strip()

        if not texte:
            return jsonify({'erreur': 'Aucun texte fourni'}), 400

        lignes_tableau, erreurs_controle, nom_excel, chemin_excel, chemin_log, log_contenu = _parse_and_log(texte)

        if len(lignes_tableau) == 0:
            return jsonify({'erreur': 'Aucun enlèvement trouvé dans le texte. Vérifiez que vous avez copié le bon document.'}), 400

        # Vérifier les doublons
        duplicates = find_duplicates(DB_PATH, lignes_tableau)

        if duplicates:
            # Stocker la session temporaire
            import uuid
            session_id = str(uuid.uuid4())[:8]
            _sessions_temp[session_id] = {
                'lignes_tableau': lignes_tableau,
                'nom_excel': nom_excel,
                'chemin_excel': str(chemin_excel),
                'chemin_log': str(chemin_log),
                'log_contenu': log_contenu,
                'duplicates': duplicates,
            }

            # Compter les nouveaux vs doublons
            dup_keys = set(duplicates.keys())
            nb_doublons = 0
            nb_nouveaux = 0
            for ligne in lignes_tableau:
                num = ligne.get('N° ENLÈVEMENT')
                soc = ligne.get('SOCIÉTÉ / DOMAINE', '')
                if (num, soc) in dup_keys:
                    nb_doublons += 1
                else:
                    nb_nouveaux += 1

            details = []
            for (num, soc), info in list(duplicates.items())[:5]:
                details.append({
                    'num': num,
                    'societe': soc,
                    'extraction_date': info['extraction_date'],
                })

            return jsonify({
                'doublons': True,
                'session_id': session_id,
                'nb_total': len(lignes_tableau),
                'nb_doublons': nb_doublons,
                'nb_nouveaux': nb_nouveaux,
                'details_doublons': details,
            })

        # Pas de doublons : génération directe
        return _finalize_generation(lignes_tableau, nom_excel, chemin_excel, chemin_log, log_contenu)

    except Exception as e:
        import traceback
        return jsonify({'erreur': f'Erreur lors de la génération: {str(e)}'}), 500


@app.route('/generer/confirmer', methods=['POST'])
def generer_confirmer():
    """Confirme la génération après détection de doublons."""
    try:
        data = request.get_json()
        session_id = data.get('session_id')
        action = data.get('action')  # 'update', 'add_all', 'skip_duplicates'

        if session_id not in _sessions_temp:
            return jsonify({'erreur': 'Session expirée. Veuillez relancer la génération.'}), 400

        session = _sessions_temp.pop(session_id)
        lignes_tableau = session['lignes_tableau']
        nom_excel = session['nom_excel']
        chemin_excel = Path(session['chemin_excel'])
        chemin_log = Path(session['chemin_log'])
        log_contenu = session['log_contenu']
        duplicates = session['duplicates']

        if action == 'update':
            # Mettre à jour les enlèvements existants + ajouter les nouveaux
            nb_updated = update_enlevements(DB_PATH, lignes_tableau, duplicates)

            # Filtrer pour ne garder que les nouveaux dans l'extraction
            dup_keys = set(duplicates.keys())
            nouveaux = [l for l in lignes_tableau if (l.get('N° ENLÈVEMENT'), l.get('SOCIÉTÉ / DOMAINE', '')) not in dup_keys]

            if nouveaux:
                # Sauvegarder les nouveaux comme nouvelle extraction
                generer_excel(lignes_tableau, chemin_excel, chemin_log)  # Excel complet pour le téléchargement
                save_extraction(DB_PATH, nom_excel, datetime.now(), nouveaux, log_contenu)
            else:
                # Que des mises à jour, générer quand même l'Excel pour téléchargement
                generer_excel(lignes_tableau, chemin_excel, chemin_log)

            return send_file(
                chemin_excel,
                as_attachment=True,
                download_name=nom_excel,
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )

        elif action == 'add_all':
            # Tout ajouter comme nouvelle extraction (comportement classique)
            return _finalize_generation(lignes_tableau, nom_excel, chemin_excel, chemin_log, log_contenu)

        elif action == 'skip_duplicates':
            # N'ajouter que les nouveaux enlèvements
            dup_keys = set(duplicates.keys())
            nouveaux = [l for l in lignes_tableau if (l.get('N° ENLÈVEMENT'), l.get('SOCIÉTÉ / DOMAINE', '')) not in dup_keys]

            if not nouveaux:
                return jsonify({'erreur': 'Tous les enlèvements sont des doublons. Rien à ajouter.'}), 400

            return _finalize_generation(nouveaux, nom_excel, chemin_excel, chemin_log, log_contenu)

        else:
            return jsonify({'erreur': f'Action inconnue: {action}'}), 400

    except Exception as e:
        import traceback
        return jsonify({'erreur': f'Erreur: {str(e)}'}), 500


@app.route('/api/historique')
def api_historique():
    try:
        historique = list_extractions(DB_PATH)
        return jsonify({'historique': historique})
    except Exception as e:
        return jsonify({'erreur': str(e)}), 500


@app.route('/api/donnees/<filename>')
def api_donnees(filename):
    try:
        # Validation du filename (sécurité contre path traversal)
        if '..' in filename or '/' in filename or '\\' in filename:
            return jsonify({'erreur': 'Nom de fichier invalide'}), 400

        data = get_extraction_data(DB_PATH, filename)
        if not data:
            return jsonify({'erreur': 'Fichier non trouvé'}), 404

        return jsonify(data)

    except Exception as e:
        import traceback
        print(f"Erreur lecture données: {traceback.format_exc()}")
        return jsonify({'erreur': f'Erreur lecture fichier: {str(e)}'}), 500


@app.route('/telecharger/<filename>')
def telecharger(filename):
    try:
        # Vérifier d'abord si le fichier existe sur disque (cache)
        chemin_excel = HISTORIQUE_DIR / filename
        if chemin_excel.exists():
            return send_from_directory(HISTORIQUE_DIR, filename, as_attachment=True)

        # Sinon, générer depuis la DB
        df = generate_excel_from_db(DB_PATH, filename)
        if df is None:
            return jsonify({'erreur': 'Fichier non trouvé'}), 404

        # Écrire le fichier Excel avec formatage
        with pd.ExcelWriter(chemin_excel, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Enlèvements')
            workbook = writer.book
            worksheet = writer.sheets['Enlèvements']
            colonnes_largeur = {
                'A': 15, 'B': 18, 'C': 35, 'D': 25, 'E': 10,
                'F': 15, 'G': 12, 'H': 12, 'I': 18, 'J': 18,
            }
            for col, width in colonnes_largeur.items():
                worksheet.column_dimensions[col].width = width
            worksheet.auto_filter.ref = worksheet.dimensions

        return send_from_directory(HISTORIQUE_DIR, filename, as_attachment=True)
    except Exception as e:
        return jsonify({'erreur': str(e)}), 404


@app.route('/log/<filename>')
def voir_log(filename):
    try:
        # Chercher d'abord dans la DB
        # Le filename est "log_YYYYMMDD_HHMMSS.md", on retrouve le nom Excel
        timestamp_str = filename.replace('log_', '').replace('.md', '')
        nom_excel = f"Enlevements_{timestamp_str}.xlsx"
        contenu = get_extraction_log(DB_PATH, nom_excel)

        # Fallback : fichier sur disque
        if not contenu:
            chemin_log = LOGS_DIR / filename
            if not chemin_log.exists():
                return "Log non trouvé", 404
            with open(chemin_log, 'r', encoding='utf-8') as f:
                contenu = f.read()

        return f"<pre>{contenu}</pre>", 200, {'Content-Type': 'text/html; charset=utf-8'}

    except Exception as e:
        return str(e), 500


# ===== TOURNEES =====

@app.route('/tournees')
def page_tournees():
    return render_template('tournees.html', active_page='tournees')


@app.route('/parametres')
def page_parametres():
    return render_template('parametres.html', active_page='parametres')


@app.route('/api/tournees')
def api_list_tournees():
    try:
        date = request.args.get('date')
        if not date:
            return jsonify({'erreur': 'Parametre date requis'}), 400
        return jsonify({'tournees': list_tournees(DB_PATH, date)})
    except Exception as e:
        return jsonify({'erreur': str(e)}), 500


@app.route('/api/tournees', methods=['POST'])
def api_create_tournee():
    try:
        data = request.get_json()
        tournee_id = create_tournee(DB_PATH, data)
        return jsonify({'id': tournee_id})
    except Exception as e:
        return jsonify({'erreur': str(e)}), 500


@app.route('/api/tournees/<int:tid>', methods=['PUT'])
def api_update_tournee(tid):
    try:
        data = request.get_json()
        update_tournee(DB_PATH, tid, data)
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'erreur': str(e)}), 500


@app.route('/api/tournees/<int:tid>', methods=['DELETE'])
def api_delete_tournee(tid):
    try:
        delete_tournee(DB_PATH, tid)
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'erreur': str(e)}), 500


@app.route('/api/tournees/<int:tid>/enlevements', methods=['POST'])
def api_assign_enlevements(tid):
    try:
        data = request.get_json()
        enlevement_ids = data.get('enlevement_ids', [])
        assign_enlevements(DB_PATH, tid, enlevement_ids)
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'erreur': str(e)}), 500


@app.route('/api/tournees/<int:tid>/enlevements/<int:eid>', methods=['DELETE'])
def api_remove_enlevement(tid, eid):
    try:
        remove_enlevement(DB_PATH, tid, eid)
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'erreur': str(e)}), 500


@app.route('/api/tournees/<int:tid>/reorder', methods=['PUT'])
def api_reorder_enlevements(tid):
    try:
        data = request.get_json()
        ordered_ids = data.get('enlevement_ids', [])
        reorder_enlevements(DB_PATH, tid, ordered_ids)
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'erreur': str(e)}), 500


@app.route('/api/enlevements-non-assignes')
def api_unassigned():
    try:
        extraction_id = request.args.get('extraction_id', type=int)
        date = request.args.get('date')
        enlevements = get_unassigned_enlevements(DB_PATH, extraction_id=extraction_id, date=date)
        return jsonify({'enlevements': enlevements})
    except Exception as e:
        return jsonify({'erreur': str(e)}), 500


@app.route('/api/tournees/auto-distribuer', methods=['POST'])
def api_auto_distribuer():
    try:
        data = request.get_json()
        result = auto_distribuer(DB_PATH, data['date_tournee'], data.get('extraction_id'))
        return jsonify(result)
    except Exception as e:
        return jsonify({'erreur': str(e)}), 500


@app.route('/api/extractions-par-date')
def api_extractions_par_date():
    try:
        date = request.args.get('date')
        if not date:
            return jsonify({'erreur': 'Parametre date requis'}), 400
        return jsonify({'extractions': get_extractions_for_date(DB_PATH, date)})
    except Exception as e:
        return jsonify({'erreur': str(e)}), 500


# ===== CHAUFFEURS & VEHICULES =====

@app.route('/api/chauffeurs')
def api_list_chauffeurs():
    try:
        return jsonify({'chauffeurs': list_chauffeurs(DB_PATH)})
    except Exception as e:
        return jsonify({'erreur': str(e)}), 500


@app.route('/api/chauffeurs', methods=['POST'])
def api_save_chauffeur():
    try:
        data = request.get_json()
        cid = save_chauffeur(DB_PATH, data)
        return jsonify({'id': cid})
    except Exception as e:
        return jsonify({'erreur': str(e)}), 500


@app.route('/api/chauffeurs/<int:cid>', methods=['DELETE'])
def api_delete_chauffeur(cid):
    try:
        delete_chauffeur(DB_PATH, cid)
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'erreur': str(e)}), 500


@app.route('/api/vehicules')
def api_list_vehicules():
    try:
        return jsonify({'vehicules': list_vehicules(DB_PATH)})
    except Exception as e:
        return jsonify({'erreur': str(e)}), 500


@app.route('/api/vehicules', methods=['POST'])
def api_save_vehicule():
    try:
        data = request.get_json()
        vid = save_vehicule(DB_PATH, data)
        return jsonify({'id': vid})
    except Exception as e:
        return jsonify({'erreur': str(e)}), 500


@app.route('/api/vehicules/<int:vid>', methods=['DELETE'])
def api_delete_vehicule(vid):
    try:
        delete_vehicule(DB_PATH, vid)
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'erreur': str(e)}), 500


# ===== ZONES & VILLE-ZONE MAPPING =====

@app.route('/api/zones')
def api_list_zones():
    try:
        return jsonify({'zones': list_zones(DB_PATH)})
    except Exception as e:
        return jsonify({'erreur': str(e)}), 500


@app.route('/api/zones', methods=['POST'])
def api_save_zone():
    try:
        data = request.get_json()
        zid = save_zone(DB_PATH, data)
        return jsonify({'id': zid})
    except Exception as e:
        return jsonify({'erreur': str(e)}), 500


@app.route('/api/zones/<int:zid>', methods=['DELETE'])
def api_delete_zone(zid):
    try:
        delete_zone(DB_PATH, zid)
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'erreur': str(e)}), 500


@app.route('/api/ville-zone-mapping')
def api_ville_zone():
    try:
        return jsonify({'mapping': list_ville_zone_mapping(DB_PATH)})
    except Exception as e:
        return jsonify({'erreur': str(e)}), 500


@app.route('/api/ville-zone-mapping', methods=['POST'])
def api_save_ville_zone():
    try:
        data = request.get_json()
        # Auto-geocode si lat/lon absents
        ville = data.get('ville', '')
        if ville and not data.get('lat') and not data.get('lon'):
            coords = geocode_ville(ville)
            if coords:
                data['lat'] = coords['lat']
                data['lon'] = coords['lon']
        save_ville_zone(DB_PATH, data)
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'erreur': str(e)}), 500


@app.route('/api/villes-inconnues')
def api_villes_inconnues():
    try:
        return jsonify({'villes': get_villes_inconnues(DB_PATH)})
    except Exception as e:
        return jsonify({'erreur': str(e)}), 500


# ===== GEOCODAGE =====

def geocode_ville(ville):
    """Géocode une ville via l'API adresse.data.gouv.fr. Retourne {lat, lon} ou None."""
    import urllib.request
    import urllib.parse
    try:
        query = urllib.parse.urlencode({'q': ville, 'type': 'municipality', 'limit': '1'})
        url = f'https://api-adresse.data.gouv.fr/search/?{query}'
        req = urllib.request.Request(url, headers={'User-Agent': 'Bibile/3.0'})
        with urllib.request.urlopen(req, timeout=5) as resp:
            result = json.loads(resp.read().decode('utf-8'))
            features = result.get('features', [])
            if features:
                coords = features[0]['geometry']['coordinates']  # [lon, lat]
                return {'lat': coords[1], 'lon': coords[0]}
    except Exception as e:
        print(f"Geocodage erreur pour '{ville}': {e}")
    return None


@app.route('/api/geocode', methods=['POST'])
def api_geocode():
    try:
        data = request.get_json()
        ville = data.get('ville', '')
        if not ville:
            return jsonify({'erreur': 'Ville requise'}), 400
        coords = geocode_ville(ville)
        if coords:
            return jsonify(coords)
        return jsonify({'erreur': 'Ville non trouvée'}), 404
    except Exception as e:
        return jsonify({'erreur': str(e)}), 500


@app.route('/api/geocode-all', methods=['POST'])
def api_geocode_all():
    """Géocode toutes les villes du mapping qui n'ont pas encore de coordonnées."""
    try:
        mapping = list_ville_zone_mapping(DB_PATH)
        geocoded = 0
        errors = []
        for m in mapping:
            if m.get('lat') and m.get('lon'):
                continue
            coords = geocode_ville(m['ville'])
            if coords:
                save_ville_zone(DB_PATH, {
                    'ville': m['ville'],
                    'zone_id': m.get('zone_id'),
                    'tournee_defaut': m.get('tournee_defaut', ''),
                    'lat': coords['lat'],
                    'lon': coords['lon'],
                })
                geocoded += 1
            else:
                errors.append(m['ville'])
        return jsonify({'geocoded': geocoded, 'errors': errors})
    except Exception as e:
        return jsonify({'erreur': str(e)}), 500


# ===== SYNCHRO EXTERNE =====

@app.route('/api/external-db/config')
def api_get_ext_config():
    try:
        config = get_external_config(DB_PATH)
        if config:
            config.pop('password_encrypted', None)
        return jsonify({'config': config})
    except Exception as e:
        return jsonify({'erreur': str(e)}), 500


@app.route('/api/external-db/config', methods=['POST'])
def api_save_ext_config():
    try:
        data = request.get_json()
        save_external_config(DB_PATH, data)
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'erreur': str(e)}), 500


@app.route('/api/external-db/test', methods=['POST'])
def api_test_ext_connection():
    try:
        data = request.get_json()
        success, message = test_connection(data)
        return jsonify({'success': success, 'message': message})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@app.route('/api/external-db/sync', methods=['POST'])
def api_sync_now():
    try:
        global sync_manager
        if sync_manager:
            sync_manager.trigger_sync()
            return jsonify({'ok': True, 'message': 'Synchronisation declenchee'})
        return jsonify({'erreur': 'SyncManager non initialise'}), 500
    except Exception as e:
        return jsonify({'erreur': str(e)}), 500


@app.route('/api/external-db/status')
def api_sync_status():
    try:
        global sync_manager
        if sync_manager:
            return jsonify(sync_manager.get_status())
        return jsonify({'configured': False, 'actif': False})
    except Exception as e:
        return jsonify({'erreur': str(e)}), 500


@app.route('/api/external-db/chauffeurs')
def api_ext_chauffeurs():
    try:
        config = get_external_config(DB_PATH)
        if not config:
            return jsonify({'erreur': 'Connexion externe non configuree'}), 400
        vehicles = fetch_external_vehicles(config)
        return jsonify({'chauffeurs': vehicles})
    except Exception as e:
        return jsonify({'erreur': str(e)}), 500


@app.route('/api/external-db/vehicules')
def api_ext_vehicules():
    try:
        config = get_external_config(DB_PATH)
        if not config:
            return jsonify({'erreur': 'Connexion externe non configuree'}), 400
        vehicles = fetch_external_vehicles(config)
        return jsonify({'vehicules': vehicles})
    except Exception as e:
        return jsonify({'erreur': str(e)}), 500


@app.route('/api/external-db/chauffeurs/selection', methods=['POST'])
def api_save_ext_chauffeurs_selection():
    try:
        data = request.get_json()
        save_chauffeurs_sync_selection(DB_PATH, data.get('selections', []))
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'erreur': str(e)}), 500


@app.route('/api/external-db/vehicules/selection', methods=['POST'])
def api_save_ext_vehicules_selection():
    try:
        data = request.get_json()
        save_vehicules_sync_selection(DB_PATH, data.get('selections', []))
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'erreur': str(e)}), 500


@app.route('/api/vehicles/positions')
def api_vehicle_positions():
    """Positions GPS live des véhicules depuis la BDD DBI."""
    try:
        config = get_external_config(DB_PATH)
        if not config:
            return jsonify({'positions': []})
        positions = fetch_vehicle_positions(config)
        return jsonify({'positions': positions})
    except Exception as e:
        return jsonify({'erreur': str(e), 'positions': []}), 500


@app.route('/api/donnees-transport')
def api_donnees_transport():
    try:
        vehicule_id = request.args.get('vehicule_id', type=int)
        chauffeur_id = request.args.get('chauffeur_id', type=int)
        date_debut = request.args.get('date_debut')
        date_fin = request.args.get('date_fin')
        data = get_donnees_transport(DB_PATH, vehicule_id=vehicule_id,
                                     chauffeur_id=chauffeur_id,
                                     date_debut=date_debut, date_fin=date_fin)
        return jsonify({'donnees': data})
    except Exception as e:
        return jsonify({'erreur': str(e)}), 500


def init_sync_manager():
    """Initialise le SyncManager. Appelé depuis main.py."""
    global sync_manager
    sync_manager = SyncManager(DB_PATH)
    sync_manager.start()


if __name__ == '__main__':
    print("=" * 70)
    print("  BIBILE - Serveur démarré")
    print("=" * 70)
    print()
    print("  Ouvrez votre navigateur à l'adresse:")
    print("  http://localhost:5001")
    print()
    print("  Appuyez sur Ctrl+C pour arrêter le serveur")
    print("=" * 70)
    print()

    app.run(debug=False, host='0.0.0.0', port=5001, use_reloader=False)
