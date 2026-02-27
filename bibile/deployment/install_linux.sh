#!/bin/bash

# Installation de Bibile sur Linux
# Usage: sudo bash install_linux.sh

set -e

echo "================================================================================"
echo "  INSTALLATION DE BIBILE SUR LINUX"
echo "================================================================================"
echo ""

# Vérifier que le script est exécuté en root
if [ "$EUID" -ne 0 ]; then
    echo "ERREUR: Ce script doit etre execute avec sudo"
    echo "Usage: sudo bash install_linux.sh"
    exit 1
fi

# Installer Python et pip
echo "[1/6] Installation de Python..."
if command -v apt-get &> /dev/null; then
    apt-get update
    apt-get install -y python3 python3-pip python3-venv
elif command -v yum &> /dev/null; then
    yum install -y python3 python3-pip
else
    echo "ERREUR: Gestionnaire de paquets non supporte"
    exit 1
fi

# Créer le répertoire d'installation
echo "[2/6] Creation du repertoire /opt/bibile..."
mkdir -p /opt/bibile
cd /opt/bibile

# Copier les fichiers (si pas déjà fait)
echo "[3/6] Copie des fichiers..."
if [ ! -f "server.py" ]; then
    echo "ERREUR: server.py non trouve. Copiez d'abord les fichiers dans /opt/bibile"
    exit 1
fi

# Créer les dossiers nécessaires
mkdir -p historique logs static templates

# Installer les dépendances Python
echo "[4/6] Installation des dependances Python..."
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt

# Créer le service systemd
echo "[5/6] Creation du service systemd..."
cat > /etc/systemd/system/bibile.service <<EOF
[Unit]
Description=Bibile - Extracteur d'enlevements Hillebrand
After=network.target

[Service]
Type=simple
User=root
Group=root
WorkingDirectory=/opt/bibile
Environment="PATH=/usr/bin"
ExecStart=/usr/bin/python3 /opt/bibile/server.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Activer et démarrer le service
echo "[6/6] Demarrage du service..."
systemctl daemon-reload
systemctl enable bibile
systemctl start bibile

# Afficher le statut
echo ""
echo "================================================================================"
echo "  INSTALLATION TERMINEE!"
echo "================================================================================"
echo ""
systemctl status bibile --no-pager
echo ""
echo "Bibile est maintenant accessible sur:"
echo "  http://$(hostname -I | awk '{print $1}'):5001"
echo ""
echo "Commandes utiles:"
echo "  sudo systemctl status bibile   # Voir le statut"
echo "  sudo systemctl stop bibile     # Arreter le service"
echo "  sudo systemctl start bibile    # Demarrer le service"
echo "  sudo systemctl restart bibile  # Redemarrer le service"
echo "  sudo journalctl -u bibile -f   # Voir les logs en temps reel"
echo ""
