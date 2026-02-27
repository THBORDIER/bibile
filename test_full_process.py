#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test complet du processus d'extraction avec mapping dynamique
"""

import sys
sys.path.insert(0, r'C:\INFORMATIQUE\Benjamin-trie Hillebrand\bibile')

from server import parser_texte, generer_excel
from pathlib import Path
from datetime import datetime

# Charger le fichier de test
fichier_test = Path(r'C:\INFORMATIQUE\Benjamin-trie Hillebrand\Date 10févr.2026.txt')
with open(fichier_test, 'r', encoding='utf-8') as f:
    texte = f.read()

print("=" * 70)
print("TEST COMPLET DU PROCESSUS D'EXTRACTION")
print("=" * 70)
print()

# Créer les fichiers de sortie
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
nom_excel = f"TEST_Enlevements_{timestamp}.xlsx"
nom_log = f"TEST_log_{timestamp}.md"

base_dir = Path(r'C:\INFORMATIQUE\Benjamin-trie Hillebrand\bibile')
historique_dir = base_dir / 'historique'
logs_dir = base_dir / 'logs'

chemin_excel = historique_dir / nom_excel
chemin_log = logs_dir / nom_log

# Créer le fichier de log
with open(chemin_log, 'w', encoding='utf-8') as f:
    f.write(f"# Test complet - {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n\n")

# Parser le texte
print(">> Parsing du fichier texte...")
lignes_tableau, erreurs_controle = parser_texte(texte, chemin_log)

print(f"   {len(lignes_tableau)} lignes de palettes extraites")
print()

# Afficher un échantillon des données
print(">> Echantillon des données extraites (5 premières lignes):")
print()
for i, ligne in enumerate(lignes_tableau[:5], 1):
    print(f"  Ligne {i}:")
    print(f"    Enlevement: {ligne['N° ENLÈVEMENT']}")
    print(f"    Societe: {ligne['SOCIÉTÉ / DOMAINE']}")
    print(f"    Ville: {ligne['VILLE']}")
    print(f"    Livraison: {ligne['LIVRAISON ASSOCIÉE']}")
    print(f"    Palettes: {ligne['NOMBRE DE PALETTES']} {ligne['TYPE DE PALETTES']}")
    print()

# Générer l'Excel
print(">> Generation du fichier Excel...")
generer_excel(lignes_tableau, chemin_excel, chemin_log)
print(f"   Fichier créé: {chemin_excel}")
print()

# Afficher les résultats du contrôle qualité
print(">> Résultats du contrôle qualité:")
if erreurs_controle:
    print(f"   {len(erreurs_controle)} alerte(s) détectée(s):")
    for erreur in erreurs_controle:
        print(f"     - {erreur}")
else:
    print("   Tous les contrôles sont OK!")

print()
print("=" * 70)
print(f"TERMINE - Consultez le log complet: {chemin_log}")
print("=" * 70)
