================================================================================
  DEPLOIEMENT DE BIBILE SUR VM LINUX
================================================================================

AVANTAGES
---------

✅ Un seul serveur centralise
✅ Pas besoin d'installer Python sur les postes utilisateurs
✅ Les utilisateurs accedent via leur navigateur web
✅ Fichiers et historique centralises
✅ Service toujours disponible (demarre automatiquement)
✅ Maintenance simplifiee


PREREQUIS
---------

1. VM Linux (Ubuntu 20.04+, Debian 11+, CentOS 8+, ou RHEL 8+)
2. Acces SSH a la VM (pour l'installation)
3. La VM doit etre accessible sur le reseau local
4. Ports requis: 5001 (HTTP)


INSTALLATION
------------

ETAPE 1: COPIER LES FICHIERS SUR LA VM

  Option A - Via WinSCP (GUI):
    - Telechargez WinSCP: https://winscp.net/
    - Connectez-vous a la VM
    - Copiez le dossier "bibile" vers /tmp/bibile sur la VM

  Option B - Via rsync (ligne de commande):
    rsync -avz bibile/ user@VM_IP:/tmp/bibile/

  Option C - Via partage reseau Windows/Samba
    - Montez le partage depuis la VM
    - Copiez les fichiers


ETAPE 2: SE CONNECTER A LA VM

  ssh user@VM_IP
  # Ou utilisez PuTTY depuis Windows


ETAPE 3: COPIER LES FICHIERS AU BON ENDROIT

  sudo mkdir -p /opt/bibile
  sudo cp -r /tmp/bibile/* /opt/bibile/
  cd /opt/bibile


ETAPE 4: LANCER L'INSTALLATION

  sudo bash deployment/install_linux.sh

  Le script va:
  - Installer Python et les dependances
  - Installer les packages Python requis (Flask, pandas, openpyxl)
  - Creer un service systemd
  - Demarrer Bibile automatiquement


ETAPE 5: OBTENIR L'ADRESSE IP DE LA VM

  hostname -I
  # Exemple: 192.168.1.50

  Bibile sera accessible sur: http://192.168.1.50:5001


ACCES UTILISATEURS
------------------

Les utilisateurs Windows accedent simplement via leur navigateur:

1. Ouvrir Chrome, Edge, ou Firefox
2. Aller sur: http://IP_DE_LA_VM:5001
   Exemple: http://192.168.1.50:5001

3. Mettre en favori pour acces rapide!


CREER UN RACCOURCI (optionnel)
-------------------------------

Pour faciliter l'acces, creez un raccourci .url sur les bureaux:

  Contenu du fichier "Bibile.url":

    [InternetShortcut]
    URL=http://192.168.1.50:5001
    IconIndex=0

  Copiez ce fichier sur les bureaux utilisateurs.


GESTION DU SERVICE
------------------

Voir le statut:
  sudo systemctl status bibile

Arreter le service:
  sudo systemctl stop bibile

Demarrer le service:
  sudo systemctl start bibile

Redemarrer le service:
  sudo systemctl restart bibile

Voir les logs en temps reel:
  sudo journalctl -u bibile -f

Voir les derniers logs:
  sudo journalctl -u bibile -n 100


FICHIERS GENERES
-----------------

Les fichiers Excel et logs sont stockes sur la VM:

  /opt/bibile/historique/   <- Fichiers Excel generes
  /opt/bibile/logs/         <- Logs d'activite

Pour telecharger les fichiers depuis la VM vers Windows:
  - Via WinSCP
  - Via le navigateur (page Historique dans Bibile)


MISE A JOUR DE BIBILE
---------------------

1. Arreter le service:
   sudo systemctl stop bibile

2. Sauvegarder les donnees:
   sudo cp -r /opt/bibile/historique /opt/bibile_backup_historique
   sudo cp -r /opt/bibile/logs /opt/bibile_backup_logs

3. Copier les nouveaux fichiers:
   sudo cp server.py /opt/bibile/
   sudo cp -r templates /opt/bibile/
   sudo cp -r static /opt/bibile/

4. Redemarrer le service:
   sudo systemctl restart bibile


SECURITE (OPTIONNEL)
--------------------

Pour plus de securite, vous pouvez:

1. RESTREINDRE L'ACCES PAR IP (firewall):
   sudo ufw allow from 192.168.1.0/24 to any port 5001

2. AJOUTER UNE AUTHENTIFICATION (nginx reverse proxy avec auth basic)

3. UTILISER HTTPS (certificat SSL via nginx)


PARE-FEU
--------

Si le service n'est pas accessible depuis les postes Windows:

Ubuntu/Debian:
  sudo ufw allow 5001/tcp
  sudo ufw reload

CentOS/RHEL:
  sudo firewall-cmd --permanent --add-port=5001/tcp
  sudo firewall-cmd --reload


TROUBLESHOOTING
---------------

Service ne demarre pas:
  sudo journalctl -u bibile -n 50
  # Verifier les erreurs Python

Port 5001 deja utilise:
  sudo lsof -i :5001
  # Tuer le processus ou changer le port dans server.py

Pas accessible depuis Windows:
  - Verifier le pare-feu Linux
  - Verifier le pare-feu Windows
  - Pinger la VM: ping 192.168.1.50

Performance lente:
  - Augmenter la RAM de la VM (2GB recommande)
  - Verifier la charge CPU: htop


SAUVEGARDE
----------

Script de sauvegarde automatique (cron):

  sudo crontab -e

  Ajouter:
  0 2 * * * tar -czf /backup/bibile_$(date +\%Y\%m\%d).tar.gz /opt/bibile/historique /opt/bibile/logs


CONTACT
-------

En cas de probleme, contacter le support informatique.
