#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de test pour vérifier le mapping dynamique des livraisons
"""

import sys
sys.path.insert(0, r'C:\INFORMATIQUE\Benjamin-trie Hillebrand\bibile')

from server import extraire_totaux_livraisons, extraire_info_enlevement, parser_texte
from pathlib import Path

# Charger le fichier de test
fichier_test = Path(r'C:\INFORMATIQUE\Benjamin-trie Hillebrand\Date 10févr.2026.txt')
with open(fichier_test, 'r', encoding='utf-8') as f:
    texte = f.read()

print("=" * 70)
print("TEST DU MAPPING DYNAMIQUE DES LIVRAISONS")
print("=" * 70)
print()

# Étape 1: Tester l'extraction des totaux et du mapping
print(">> Test 1: Extraction des totaux et mapping des destinataires")
print()

totaux_livraisons, mapping_destinataires = extraire_totaux_livraisons(texte)

print(f"Nombre de livraisons trouvées: {len(totaux_livraisons)}")
print()

for num, totaux in totaux_livraisons.items():
    destinataire = mapping_destinataires.get(num, "NON TROUVÉ")
    print(f"  Livraison {num}:")
    print(f"    Destinataire: {destinataire}")
    print(f"    Totaux: {totaux['palettes']} pal, {totaux['poids']} kg, {totaux['colis']} colis")
    print()

# Étape 2: Vérifier que le mapping attendu est correct
print(">> Test 2: Vérification du mapping attendu")
print()

mapping_attendu = {
    '1': 'BREVET',
    '2': 'TRANSIT',
    '3': 'CHEVROLET',
    '4': 'HILLEBRAND'  # ou STORAGE
}

tout_ok = True
for num, nom_attendu in mapping_attendu.items():
    nom_extrait = mapping_destinataires.get(num, "NON TROUVÉ")
    statut = "OK OK" if nom_extrait == nom_attendu or (num == '4' and nom_extrait in ['HILLEBRAND', 'STORAGE']) else "X ERREUR"

    if statut == "X ERREUR":
        tout_ok = False

    print(f"  Livraison {num}: attendu '{nom_attendu}', extrait '{nom_extrait}' -> {statut}")

print()
print("=" * 70)
if tout_ok:
    print("RÉSULTAT: TOUS LES TESTS PASSÉS OK")
else:
    print("RÉSULTAT: CERTAINS TESTS ONT ÉCHOUÉ X")
print("=" * 70)
