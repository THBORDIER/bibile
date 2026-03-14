// Vehicules CRUD

async function loadVehicules() {
    try {
        const response = await fetch('/api/vehicules');
        const data = await response.json();
        renderList(data.vehicules || []);
    } catch (error) {
        console.error('Erreur:', error);
        document.getElementById('vehiculesList').innerHTML =
            '<div class="status-message error">Erreur de chargement</div>';
    }
}

function renderList(vehicules) {
    const container = document.getElementById('vehiculesList');

    if (vehicules.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <div class="empty-icon">🚛</div>
                <h3>Aucun véhicule</h3>
                <p>Cliquez sur "+ Ajouter" pour créer un véhicule</p>
            </div>`;
        return;
    }

    container.innerHTML = `
        <div class="table-container">
            <table class="data-table">
                <thead>
                    <tr>
                        <th>Immatriculation</th>
                        <th>Marque</th>
                        <th>Modèle</th>
                        <th>Type</th>
                        <th>Cap. palettes</th>
                        <th>Cap. kg</th>
                        <th>Statut</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody>
                    ${vehicules.map(v => `
                        <tr class="${v.actif ? '' : 'row-inactive'}">
                            <td><strong>${escapeHtml(v.immatriculation)}</strong></td>
                            <td>${escapeHtml(v.marque)}</td>
                            <td>${escapeHtml(v.modele)}</td>
                            <td>${escapeHtml(v.type_vehicule)}</td>
                            <td>${v.capacite_palettes || '--'}</td>
                            <td>${v.capacite_kg ? v.capacite_kg.toLocaleString() : '--'}</td>
                            <td><span class="badge ${v.actif ? 'badge-success' : 'badge-inactive'}">${v.actif ? 'Actif' : 'Inactif'}</span></td>
                            <td class="actions-cell">
                                <button class="btn-small btn-download" onclick="editVehicule(${v.id})">Modifier</button>
                                <button class="btn-small btn-log" onclick="deleteVehicule(${v.id}, '${escapeHtml(v.immatriculation)}')">Supprimer</button>
                            </td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        </div>`;
}

function openModal(data = null) {
    document.getElementById('modal').classList.remove('hidden');
    document.getElementById('modalTitle').textContent = data ? 'Modifier le véhicule' : 'Ajouter un véhicule';
    document.getElementById('editId').value = data ? data.id : '';
    document.getElementById('immatriculation').value = data ? data.immatriculation : '';
    document.getElementById('marque').value = data ? data.marque : '';
    document.getElementById('modele').value = data ? data.modele : '';
    document.getElementById('type_vehicule').value = data ? data.type_vehicule : '';
    document.getElementById('capacite_palettes').value = data ? data.capacite_palettes : '';
    document.getElementById('capacite_kg').value = data ? data.capacite_kg : '';
    document.getElementById('actif').value = data ? String(data.actif) : 'true';
    document.getElementById('notes').value = data ? data.notes : '';
}

function closeModal() {
    document.getElementById('modal').classList.add('hidden');
}

async function editVehicule(id) {
    const response = await fetch('/api/vehicules');
    const data = await response.json();
    const vehicule = (data.vehicules || []).find(v => v.id === id);
    if (vehicule) openModal(vehicule);
}

async function saveForm(event) {
    event.preventDefault();
    const id = document.getElementById('editId').value;
    const payload = {
        immatriculation: document.getElementById('immatriculation').value,
        marque: document.getElementById('marque').value,
        modele: document.getElementById('modele').value,
        type_vehicule: document.getElementById('type_vehicule').value,
        capacite_palettes: parseInt(document.getElementById('capacite_palettes').value) || null,
        capacite_kg: parseFloat(document.getElementById('capacite_kg').value) || null,
        actif: document.getElementById('actif').value === 'true',
        notes: document.getElementById('notes').value,
    };

    const url = id ? `/api/vehicules/${id}` : '/api/vehicules';
    const method = id ? 'PUT' : 'POST';

    try {
        const response = await fetch(url, {
            method,
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        if (!response.ok) {
            const err = await response.json();
            alert(err.erreur || 'Erreur');
            return;
        }
        closeModal();
        loadVehicules();
    } catch (error) {
        alert('Erreur réseau');
    }
}

async function deleteVehicule(id, immat) {
    if (!confirm(`Supprimer le véhicule "${immat}" ?`)) return;
    try {
        await fetch(`/api/vehicules/${id}`, { method: 'DELETE' });
        loadVehicules();
    } catch (error) {
        alert('Erreur réseau');
    }
}

function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str || '';
    return div.innerHTML;
}

// Init
loadVehicules();
