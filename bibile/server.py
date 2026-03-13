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
import re
import pandas as pd
from datetime import datetime
import json
from pathlib import Path
from openpyxl.styles import Font, PatternFill, Alignment

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max

# Dossiers
BASE_DIR = Path(__file__).parent
LOGS_DIR = BASE_DIR / 'logs'
HISTORIQUE_DIR = BASE_DIR / 'historique'

# Créer les dossiers s'ils n'existent pas
LOGS_DIR.mkdir(exist_ok=True)
HISTORIQUE_DIR.mkdir(exist_ok=True)



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
    return render_template('index.html')


@app.route('/aide')
def aide():
    return render_template('aide.html')


@app.route('/historique')
def historique():
    return render_template('historique.html')


@app.route('/donnees')
def donnees():
    return render_template('donnees.html')


@app.route('/generer', methods=['POST'])
def generer():
    try:
        data = request.get_json()
        texte = data.get('texte', '').strip()

        if not texte:
            return jsonify({'erreur': 'Aucun texte fourni'}), 400

        # Créer les noms de fichiers
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        nom_excel = f"Enlevements_{timestamp}.xlsx"
        nom_log = f"log_{timestamp}.md"

        chemin_excel = HISTORIQUE_DIR / nom_excel
        chemin_log = LOGS_DIR / nom_log

        # Créer le fichier de log
        with open(chemin_log, 'w', encoding='utf-8') as f:
            f.write(f"# Log de génération - {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n\n")

        log_to_file("=" * 70, chemin_log)
        log_to_file("BIBILE - Extracteur d'enlèvements Hillebrand", chemin_log)
        log_to_file("=" * 70, chemin_log)
        log_to_file("", chemin_log)

        # Parser le texte
        lignes_tableau, erreurs_controle = parser_texte(texte, chemin_log)

        if len(lignes_tableau) == 0:
            log_to_file("ERREUR: Aucun enlèvement trouvé", chemin_log)
            return jsonify({'erreur': 'Aucun enlèvement trouvé dans le texte. Vérifiez que vous avez copié le bon document.'}), 400

        # Générer l'Excel
        generer_excel(lignes_tableau, chemin_excel, chemin_log)

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

        # Retourner le fichier Excel
        return send_file(
            chemin_excel,
            as_attachment=True,
            download_name=nom_excel,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )

    except Exception as e:
        import traceback
        error_msg = str(e)
        traceback_str = traceback.format_exc()

        # Log l'erreur
        if 'chemin_log' in locals():
            log_to_file(f"ERREUR: {error_msg}", chemin_log)
            log_to_file(traceback_str, chemin_log)

        return jsonify({'erreur': f'Erreur lors de la génération: {error_msg}'}), 500


@app.route('/api/historique')
def api_historique():
    try:
        historique = []

        # Liste tous les fichiers Excel dans le dossier historique
        for fichier in sorted(HISTORIQUE_DIR.glob('Enlevements_*.xlsx'), reverse=True):
            timestamp_str = fichier.stem.replace('Enlevements_', '')

            try:
                # Parse le timestamp
                timestamp = datetime.strptime(timestamp_str, '%Y%m%d_%H%M%S')

                # Lit le fichier Excel pour compter les lignes
                df = pd.read_excel(fichier)
                nb_lignes = len(df)

                # Trouve le log correspondant
                log_fichier = f"log_{timestamp_str}.md"

                historique.append({
                    'fichier': fichier.name,
                    'nom_fichier': fichier.name,
                    'date': timestamp.isoformat(),
                    'nb_lignes': nb_lignes,
                    'log_fichier': log_fichier
                })

            except Exception as e:
                print(f"Erreur lors de la lecture de {fichier}: {e}")
                continue

        return jsonify({'historique': historique})

    except Exception as e:
        return jsonify({'erreur': str(e)}), 500


@app.route('/api/donnees/<filename>')
def api_donnees(filename):
    try:
        # Validation du filename (sécurité contre path traversal)
        if '..' in filename or '/' in filename or '\\' in filename:
            return jsonify({'erreur': 'Nom de fichier invalide'}), 400

        # Vérifier que le fichier existe
        chemin_excel = HISTORIQUE_DIR / filename
        if not chemin_excel.exists():
            return jsonify({'erreur': 'Fichier non trouvé'}), 404

        # Lire le fichier Excel
        df = pd.read_excel(chemin_excel)

        # Convertir en liste de dictionnaires, remplacer NaN par chaînes vides
        data = df.fillna('').to_dict('records')

        # Retourner les données en JSON
        return jsonify({
            'fichier': filename,
            'nb_lignes': len(data),
            'colonnes': list(df.columns),
            'donnees': data
        })

    except Exception as e:
        import traceback
        print(f"Erreur lecture Excel: {traceback.format_exc()}")
        return jsonify({'erreur': f'Erreur lecture fichier: {str(e)}'}), 500


@app.route('/telecharger/<filename>')
def telecharger(filename):
    try:
        return send_from_directory(HISTORIQUE_DIR, filename, as_attachment=True)
    except Exception as e:
        return jsonify({'erreur': str(e)}), 404


@app.route('/log/<filename>')
def voir_log(filename):
    try:
        chemin_log = LOGS_DIR / filename

        if not chemin_log.exists():
            return "Log non trouvé", 404

        with open(chemin_log, 'r', encoding='utf-8') as f:
            contenu = f.read()

        # Retourne en texte brut
        return f"<pre>{contenu}</pre>", 200, {'Content-Type': 'text/html; charset=utf-8'}

    except Exception as e:
        return str(e), 500


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
