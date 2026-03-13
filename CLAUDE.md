# BIBILE - Bible de Tri des Enlevements Hillebrand

## Architecture

Application Flask mono-fichier backend pour extraire les donnees d'enlevements depuis du texte PDF Hillebrand et generer des fichiers Excel.

```
bibile/
  server.py          # Backend Flask (toute la logique metier)
  launcher.pyw       # Lanceur silencieux (sans console)
  templates/         # Pages HTML (index, aide, historique, donnees)
  static/            # CSS + JS frontend
  historique/        # Fichiers Excel generes
  logs/              # Logs de traitement (Markdown)
  deployment/        # Scripts deploiement Linux
```

## Fonctions cles (server.py)

- `nettoyer_texte(texte)` - Pre-traitement : supprime les en-tetes/pieds de page PDF repetes
- `extraire_totaux_livraisons(texte)` - Extrait totaux livraisons + mapping destinataires
- `controler_totaux(...)` - Controle qualite (compare extrait vs attendu)
- `extraire_info_enlevement(lignes, index, mapping)` - Extraction d'un enlevement
- `parser_texte(texte, log_file)` - Orchestrateur principal
- `generer_excel(lignes, nom, log_file)` - Generation Excel avec openpyxl

## Types de palettes

| Type | Comptage Excel | Comptage QC |
|------|---------------|-------------|
| PART PALLET | 0 | Non compte |
| HALF PALLET | 1 | Non compte |
| EURO | Nombre indique | Compte |
| VMF | Nombre indique | Compte |
| LOOSE LOADED | Nombre indique | Compte |

## Regles de controle qualite

- "Au total:" dans le PDF source ne compte que EURO et VMF
- Le QC ne verifie que EURO/VMF/LOOSE LOADED, pas HALF/PART
- Poids et colis sont verifies pour tous les types

## Structure du texte PDF

Le texte copie du PDF contient des en-tetes/pieds de page repetes a chaque saut de page. Ces blocs sont supprimes par `nettoyer_texte()` avant le parsing.

Signature du pied de page : `Hillebrand Gori France SAS - 11 Rue Louis et Gaston Chevrolet`
Signature de la ref globale : `Notre Ref: FRBGXXXXXX (Merci de reporter...)`

## Commandes

```bash
# Demarrer le serveur (port 5001)
python bibile/server.py

# Lancer les tests
python test_full_process.py
python test_dynamic_mapping.py
python test_bug_fixes.py

# Installation
bibile/INSTALLER.bat
```

## Donnees de test

- `Date 06fevr.2026 0906.txt` - 38 enlevements, 4 livraisons
- `Date 10fevr.2026.txt` - 36 enlevements, 4 livraisons
