// Tachographe dashboard

let allRecords = [];

async function loadData() {
    try {
        // Charger en parallele : stats, chauffeurs, vehicules, status
        const [statsRes, chauffeursRes, vehiculesRes, statusRes] = await Promise.all([
            fetch('/api/tachographe/stats'),
            fetch('/api/chauffeurs'),
            fetch('/api/vehicules'),
            fetch('/api/tachographe/status')
        ]);

        const statsData = await statsRes.json();
        const chauffeursData = await chauffeursRes.json();
        const vehiculesData = await vehiculesRes.json();
        const statusData = await statusRes.json();

        allRecords = statsData.records || [];

        // Peupler les filtres
        populateFilters(
            (chauffeursData.chauffeurs || []).filter(c => c.actif),
            (vehiculesData.vehicules || []).filter(v => v.actif)
        );

        // Afficher le statut de sync
        updateSyncStatus(statusData);

        // Afficher les donnees
        updateDisplay();

    } catch (error) {
        console.error('Erreur:', error);
    }
}

function populateFilters(chauffeurs, vehicules) {
    const filterC = document.getElementById('filterChauffeur');
    filterC.innerHTML = '<option value="">Tous</option>';
    chauffeurs.forEach(c => {
        filterC.innerHTML += `<option value="${c.id}">${c.nom_complet}</option>`;
    });

    const filterV = document.getElementById('filterVehicule');
    filterV.innerHTML = '<option value="">Tous</option>';
    vehicules.forEach(v => {
        filterV.innerHTML += `<option value="${v.id}">${v.immatriculation}</option>`;
    });
}

function updateSyncStatus(status) {
    const lastSync = document.getElementById('lastSync');
    const statusText = document.getElementById('syncStatusText');

    if (status.derniere_sync) {
        const d = new Date(status.derniere_sync);
        lastSync.textContent = d.toLocaleString('fr-FR');
    } else {
        lastSync.textContent = 'Jamais';
    }

    if (status.statut === 'success') {
        statusText.textContent = `OK (${status.nb_records_sync} enregistrements)`;
        statusText.className = 'sync-ok';
    } else if (status.statut === 'error') {
        statusText.textContent = `Erreur: ${status.message}`;
        statusText.className = 'sync-error';
    } else if (status.statut === 'running') {
        statusText.textContent = 'En cours...';
        statusText.className = 'sync-running';
    } else {
        statusText.textContent = 'Aucune synchronisation effectuée';
    }
}

function getFilteredRecords() {
    const chauffeurId = document.getElementById('filterChauffeur').value;
    const vehiculeId = document.getElementById('filterVehicule').value;
    const dateDebut = document.getElementById('filterDateDebut').value;
    const dateFin = document.getElementById('filterDateFin').value;

    return allRecords.filter(r => {
        if (chauffeurId && r.chauffeur_id != chauffeurId) return false;
        if (vehiculeId && r.vehicule_id != vehiculeId) return false;
        if (dateDebut && r.date < dateDebut) return false;
        if (dateFin && r.date > dateFin) return false;
        return true;
    });
}

function updateDisplay() {
    const records = getFilteredRecords();

    // Stats
    let totalTemps = 0, totalDistance = 0, totalConso = 0;
    records.forEach(r => {
        totalTemps += r.temps_conduite_minutes || 0;
        totalDistance += r.distance_km || 0;
        totalConso += r.consommation_litres || 0;
    });

    document.getElementById('statTemps').textContent = `${Math.round(totalTemps / 60)}h`;
    document.getElementById('statDistance').textContent = `${Math.round(totalDistance).toLocaleString()} km`;
    document.getElementById('statConso').textContent = `${Math.round(totalConso)} L`;

    // Tableau
    const tbody = document.getElementById('tableBody');
    const emptyState = document.getElementById('emptyState');
    const rowCount = document.getElementById('rowCount');

    if (records.length === 0) {
        tbody.innerHTML = '';
        emptyState.classList.remove('hidden');
        rowCount.textContent = '0 enregistrements';
        return;
    }

    emptyState.classList.add('hidden');
    rowCount.textContent = `${records.length} enregistrement(s)`;

    tbody.innerHTML = records.map(r => `
        <tr>
            <td>${r.date}</td>
            <td>${escapeHtml(r.chauffeur_nom)}</td>
            <td>${escapeHtml(r.vehicule_immat)}</td>
            <td>${r.temps_conduite_heures}h</td>
            <td>${r.distance_km ? r.distance_km.toLocaleString() : '--'}</td>
            <td>${r.consommation_litres || '--'}</td>
        </tr>
    `).join('');
}

async function lancerSync() {
    const btn = document.getElementById('syncBtn');
    btn.disabled = true;
    btn.textContent = 'Synchronisation...';

    try {
        const response = await fetch('/api/tachographe/sync', { method: 'POST' });
        const data = await response.json();

        if (data.erreur) {
            alert(data.erreur);
        } else {
            alert(data.message || 'Synchronisation terminée');
            loadData();
        }
    } catch (error) {
        alert('Erreur réseau');
    } finally {
        btn.disabled = false;
        btn.textContent = 'Synchroniser';
    }
}

function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str || '';
    return div.innerHTML;
}

// Event listeners pour les filtres
document.getElementById('filterChauffeur').addEventListener('change', updateDisplay);
document.getElementById('filterVehicule').addEventListener('change', updateDisplay);
document.getElementById('filterDateDebut').addEventListener('change', updateDisplay);
document.getElementById('filterDateFin').addEventListener('change', updateDisplay);

// Init
loadData();
