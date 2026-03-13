#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tests des corrections de bugs identifiés dans le rapport d'analyse BIBILE.

Bugs testés :
1. "euro au lieu de palette" / LOOSE LOADED non reconnu
2. "référence GLOBAL au lieu de celle du lot"
3. "enlèvement pas intégré" (lié aux en-têtes de page et LOOSE LOADED)
"""

import sys
sys.path.insert(0, r'C:\INFORMATIQUE\Benjamin-trie Hillebrand\bibile')

from server import nettoyer_texte, extraire_info_enlevement, parser_texte
from pathlib import Path
from datetime import datetime

PASS = 0
FAIL = 0


def check(nom, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  [OK] {nom}")
    else:
        FAIL += 1
        print(f"  [ECHEC] {nom}")
        if detail:
            print(f"         {detail}")


# =============================================================================
# TEST 1 : Détection du format LOOSE LOADED
# =============================================================================
print("=" * 70)
print("TEST 1 : Détection LOOSE LOADED")
print("=" * 70)

texte_loose = """Livraison 1
11/févr./2026 00:00 Au total: 2 Palettes 500 kg 30 Colis
Brevet SA
Some address
Enlèvement 1 Test Loose Loaded Company
11/févr./2026 00:00 (Exactly) Au total: 2 Palettes 500 kg 30 Colis
Test Loose Loaded Company
10 Rue du Test
21200 Beaune
France
2 Loose loaded 500 kg 30 Colis
Réf: TEST Test-France
Notre Réf: TESTLL123/T01
Product: Wines
Test Person T: +33 123456789
Fera partie de la Livraison 1"""

log_file = Path(r'C:\INFORMATIQUE\Benjamin-trie Hillebrand\bibile\logs\test_bugs.md')
with open(log_file, 'w', encoding='utf-8') as f:
    f.write(f"# Test bugs - {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n\n")

lignes_ll = texte_loose.split('\n')
# Trouver l'index de "Enlèvement 1"
idx = next(i for i, l in enumerate(lignes_ll) if l.startswith('Enlèvement 1'))
infos, palettes = extraire_info_enlevement(lignes_ll, idx, {'1': 'BREVET'})

check("Palette détectée", len(palettes) == 1, f"Attendu: 1, Obtenu: {len(palettes)}")
if palettes:
    check("Type = LOOSE LOADED", palettes[0]['type'] == "LOOSE LOADED", f"Obtenu: {palettes[0]['type']}")
    check("Nombre = 2", palettes[0]['nombre'] == "2", f"Obtenu: {palettes[0]['nombre']}")
    check("Référence = TESTLL123/T01", palettes[0]['notre_ref'] == "TESTLL123/T01", f"Obtenu: {palettes[0]['notre_ref']}")
print()

# =============================================================================
# TEST 2 : Nettoyage des en-têtes de page
# =============================================================================
print("=" * 70)
print("TEST 2 : Nettoyage des en-têtes de page (nettoyer_texte)")
print("=" * 70)

texte_avec_headers = """Date: 09/févr./2026 17:18
A: Brevet SA Crissey - Par Défaut Ramasse Locale
Notre Réf: FRBG164812 (Merci de reporter cette référence sur votre facture)
De: Laurie Jolliot - laurie.jolliot@hillebrandgori.com - T: +33 380244173
Instructions de transport
Enlèvement 1 Test Company
11/févr./2026 00:00 (Exactly) Au total: 1 Palette 500 kg 30 Colis
FRBG164812
µFRBG164812JÄ
Hillebrand Gori France SAS - 11 Rue Louis et Gaston Chevrolet - 21200 Beaune - France
T +33 380244300 - VAT number FR62392166781 Page 21/1
Date: 09/févr./2026 17:18
A: Brevet SA Crissey - Par Défaut Ramasse Locale
Notre Réf: FRBG164812 (Merci de reporter cette référence sur votre facture)
De: Laurie Jolliot - laurie.jolliot@hillebrandgori.com - T: +33 380244173
Instructions de transport
Test Company
10 Rue du Test
21200 Beaune
France
1 Euro Pallet 500 kg 30 Colis
Réf: TEST Test-France
Notre Réf: TESTREF123/T01
Fera partie de la Livraison 1"""

texte_nettoye = nettoyer_texte(texte_avec_headers)
lignes_nettoyes = texte_nettoye.split('\n')

# Le premier en-tête doit être préservé
check("Premier en-tête préservé", any('Merci de reporter' in l for l in lignes_nettoyes[:5]))

# Le deuxième en-tête (répété) doit être supprimé
# Compter les occurrences de "Instructions de transport"
nb_instructions = sum(1 for l in lignes_nettoyes if l.strip() == 'Instructions de transport')
check("En-tête répété supprimé", nb_instructions == 1, f"Occurrences 'Instructions de transport': {nb_instructions}")

# Les codes-barres doivent être supprimés
check("Code-barres FRBG supprimé", not any('µFRBG164812' in l for l in lignes_nettoyes))

# La référence du lot doit toujours être présente
check("Référence lot préservée", any('TESTREF123/T01' in l for l in lignes_nettoyes))

# Les données de l'enlèvement doivent être préservées
check("Données enlèvement préservées", any('1 Euro Pallet' in l for l in lignes_nettoyes))
print()

# =============================================================================
# TEST 3 : Référence globale vs lot (filtre "Merci de reporter")
# =============================================================================
print("=" * 70)
print("TEST 3 : Référence globale vs référence du lot")
print("=" * 70)

# Simuler un cas où le nettoyage n'a pas parfaitement fonctionné
# et la ref globale apparaît avant la ref du lot
texte_ref = """Enlèvement 1 Test Reference Company
11/févr./2026 00:00 (Exactly) Au total: 1 Palette 500 kg 30 Colis
Test Reference Company
10 Rue du Test
21200 Beaune
France
1 Euro Pallet 500 kg 30 Colis
Réf: TEST Test-France
Notre Réf: FRBG164812 (Merci de reporter cette référence sur votre facture)
Notre Réf: LOTREF999/T01
Fera partie de la Livraison 1"""

lignes_ref = texte_ref.split('\n')
idx = 0  # "Enlèvement 1" est la première ligne
infos_ref, palettes_ref = extraire_info_enlevement(lignes_ref, idx, {'1': 'BREVET'})

check("Palette détectée", len(palettes_ref) == 1, f"Attendu: 1, Obtenu: {len(palettes_ref)}")
if palettes_ref:
    check("Référence = LOTREF999/T01 (pas FRBG164812)",
          palettes_ref[0]['notre_ref'] == "LOTREF999/T01",
          f"Obtenu: {palettes_ref[0]['notre_ref']}")
print()

# =============================================================================
# TEST 4 : Validation avec les vrais fichiers de données
# =============================================================================
print("=" * 70)
print("TEST 4 : Validation sur données réelles")
print("=" * 70)

fichier_10fev = Path(r'C:\INFORMATIQUE\Benjamin-trie Hillebrand\Date 10févr.2026.txt')
if fichier_10fev.exists():
    with open(fichier_10fev, 'r', encoding='utf-8') as f:
        texte_10fev = f.read()

    lignes_tab, erreurs = parser_texte(texte_10fev, log_file)

    print(f"  Fichier: Date 10févr.2026.txt")
    print(f"  Lignes extraites: {len(lignes_tab)}")
    print(f"  Erreurs QC: {len(erreurs)}")

    # Vérifier qu'aucune référence n'est la ref globale FRBG164812
    refs_globales = [l for l in lignes_tab if l['NOTRE RÉFÉRENCE'] == 'FRBG164812']
    check("Aucune ref globale FRBG164812 dans les résultats",
          len(refs_globales) == 0,
          f"{len(refs_globales)} ligne(s) avec ref globale : " +
          ", ".join(f"Enl.{l['N° ENLÈVEMENT']}" for l in refs_globales))

    # Vérifier les types de palettes (aucun ne devrait être vide)
    types_vides = [l for l in lignes_tab if not l['TYPE DE PALETTES']]
    check("Tous les types de palettes sont remplis",
          len(types_vides) == 0,
          f"{len(types_vides)} palette(s) sans type")
else:
    print(f"  [SKIP] Fichier non trouvé: {fichier_10fev}")

print()

fichier_06fev = Path(r'C:\INFORMATIQUE\Benjamin-trie Hillebrand\Date 06févr.2026 0906.txt')
if fichier_06fev.exists():
    with open(fichier_06fev, 'r', encoding='utf-8') as f:
        texte_06fev = f.read()

    lignes_tab2, erreurs2 = parser_texte(texte_06fev, log_file)

    print(f"  Fichier: Date 06févr.2026 0906.txt")
    print(f"  Lignes extraites: {len(lignes_tab2)}")
    print(f"  Erreurs QC: {len(erreurs2)}")

    # Même vérification sur les refs globales
    # Identifier la ref globale de ce fichier (première ligne "Notre Réf:" avec "Merci de reporter")
    for line in texte_06fev.split('\n'):
        if 'Notre Réf:' in line and 'Merci de reporter' in line:
            import re
            m = re.search(r'Notre Ré[fF]:\s*([A-Z0-9]+)', line)
            if m:
                ref_glob = m.group(1)
                refs_glob2 = [l for l in lignes_tab2 if l['NOTRE RÉFÉRENCE'] == ref_glob]
                check(f"Aucune ref globale {ref_glob} dans les résultats",
                      len(refs_glob2) == 0,
                      f"{len(refs_glob2)} ligne(s) avec ref globale")
                break
else:
    print(f"  [SKIP] Fichier non trouvé: {fichier_06fev}")

print()

# =============================================================================
# RÉSUMÉ
# =============================================================================
print("=" * 70)
total = PASS + FAIL
print(f"RÉSULTAT : {PASS}/{total} tests passés", end="")
if FAIL > 0:
    print(f" ({FAIL} échec(s))")
else:
    print(" - Tous les tests sont OK!")
print("=" * 70)
