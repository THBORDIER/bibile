================================================================================
  BIBILE - EXTRACTEUR D'ENLEVEMENTS HILLEBRAND
================================================================================

INSTALLATION
------------

1. PREREQUIS: Python doit etre installe sur l'ordinateur

   Si Python n'est pas installe:
   - Telecharger depuis: https://www.python.org/downloads/
   - Pendant l'installation, COCHER "Add Python to PATH"
   - Version recommandee: Python 3.8 ou superieur

2. COPIER le dossier "bibile" complet sur l'ordinateur de l'utilisateur
   Exemple: C:\INFORMATIQUE\bibile

3. DOUBLE-CLIQUER sur "INSTALLER.bat"
   - Installe les dependances automatiquement
   - Cree un raccourci sur le bureau

4. C'EST PRET!


UTILISATION
-----------

LANCER BIBILE:
  - Double-cliquez sur le raccourci "Bibile - Extracteur Hillebrand" sur le bureau
  - Le navigateur s'ouvre automatiquement sur http://localhost:5001

ARRETER BIBILE:
  - Double-cliquez sur "ARRETER_BIBILE.bat" dans le dossier d'installation


FONCTIONNALITES
---------------

1. PAGE ACCUEIL (http://localhost:5001/)
   - Collez le texte du PDF
   - Cliquez sur "Generer le fichier Excel"
   - Le fichier Excel se telecharge automatiquement

2. PAGE DONNEES (http://localhost:5001/donnees)
   - Visualisez les donnees sans ouvrir Excel
   - Statistiques par livraison (BREVET, TRANSIT, CHEVROLET)
   - Filtres instantanes
   - Codes couleurs

3. PAGE HISTORIQUE (http://localhost:5001/historique)
   - Liste de tous les fichiers generes
   - Re-telechargez les anciens fichiers
   - Consultez les logs

4. PAGE AIDE (http://localhost:5001/aide)
   - Guide d'utilisation complet


STRUCTURE DES FICHIERS
-----------------------

bibile/
  INSTALLER.bat               <- Installation (a lancer une seule fois)
  LANCER_BIBILE_SILENCIEUX.bat <- Lancer l'application
  ARRETER_BIBILE.bat          <- Arreter l'application

  server.py                   <- Serveur Flask (ne pas modifier)
  launcher.pyw                <- Lanceur Python (ne pas modifier)
  requirements.txt            <- Dependances Python (ne pas modifier)

  historique/                 <- Fichiers Excel generes
  logs/                       <- Logs d'activite
  templates/                  <- Pages HTML
  static/                     <- CSS et JavaScript


COMPTAGE DES PALETTES
----------------------

  PART PALLET  = 0 palette
  HALF PALLET  = 1 palette
  Autres types = quantite indiquee


TYPES DE LIVRAISON
------------------

  Livraison 1 = BREVET
  Livraison 2 = TRANSIT
  Livraison 3 = BREVET
  Livraison 4 = CHEVROLET


EN CAS DE PROBLEME
------------------

1. Verifier que le serveur est lance (raccourci bureau ou LANCER_BIBILE_SILENCIEUX.bat)
2. Verifier que le port 5001 n'est pas utilise par un autre programme
3. Consulter les logs dans le dossier "logs/"
4. Relancer le serveur:
   - Executer ARRETER_BIBILE.bat
   - Executer LANCER_BIBILE_SILENCIEUX.bat

Si le probleme persiste:
  - Contacter le support informatique
  - Fournir le dernier fichier log dans logs/


VERSION
-------

Bibile v1.0 - Fevrier 2026
Outil interne Hillebrand
