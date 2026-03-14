// Chauffeurs CRUD

async function loadChauffeurs() {
    try {
        const response = await fetch('/api/chauffeurs');
        const data = await response.json();
        renderList(data.chauffeurs || []);
    } catch (error) {
        console.error('Erreur:', error);
        document.getElementById('chauffeursList').innerHTML =
            '<div class="status-message error">Erreur de chargement</div>';
    }
}

function renderList(chauffeurs) {
    const container = document.getElementById('chauffeursList');

    if (chauffeurs.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <div class="empty-icon">👤</div>
                <h3>Aucun chauffeur</h3>
                <p>Cliquez sur "+ Ajouter" pour créer un chauffeur</p>
            </div>`;
        return;
    }

    container.innerHTML = `
        <div class="table-container">
            <table class="data-table">
                <thead>
                    <tr>
                        <th>Nom</th>
                        <th>Prénom</th>
                        <th>Téléphone</th>
                        <th>N° Permis</th>
                        <th>Expiration</th>
                        <th>Statut</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody>
                    ${chauffeurs.map(c => `
                        <tr class="${c.actif ? '' : 'row-inactive'}">
                            <td>${escapeHtml(c.nom)}</td>
                            <td>${escapeHtml(c.prenom)}</td>
                            <td>${escapeHtml(c.telephone)}</td>
                            <td>${escapeHtml(c.permis_numero)}</td>
                            <td>${c.permis_expiration || '--'}</td>
                            <td><span class="badge ${c.actif ? 'badge-success' : 'badge-inactive'}">${c.actif ? 'Actif' : 'Inactif'}</span></td>
                            <td class="actions-cell">
                                <button class="btn-small btn-download" onclick="editChauffeur(${c.id})">Modifier</button>
                                <button class="btn-small btn-log" onclick="deleteChauffeur(${c.id}, '${escapeHtml(c.nom_complet)}')">Supprimer</button>
                            </td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        </div>`;
}

function openModal(data = null) {
    document.getElementById('modal').classList.remove('hidden');
    document.getElementById('modalTitle').textContent = data ? 'Modifier le chauffeur' : 'Ajouter un chauffeur';
    document.getElementById('editId').value = data ? data.id : '';
    document.getElementById('nom').value = data ? data.nom : '';
    document.getElementById('prenom').value = data ? data.prenom : '';
    document.getElementById('telephone').value = data ? data.telephone : '';
    document.getElementById('permis_numero').value = data ? data.permis_numero : '';
    document.getElementById('permis_expiration').value = data ? data.permis_expiration : '';
    document.getElementById('actif').value = data ? String(data.actif) : 'true';
    document.getElementById('notes').value = data ? data.notes : '';
}

function closeModal() {
    document.getElementById('modal').classList.add('hidden');
}

async function editChauffeur(id) {
    const response = await fetch('/api/chauffeurs');
    const data = await response.json();
    const chauffeur = (data.chauffeurs || []).find(c => c.id === id);
    if (chauffeur) openModal(chauffeur);
}

async function saveForm(event) {
    event.preventDefault();
    const id = document.getElementById('editId').value;
    const payload = {
        nom: document.getElementById('nom').value,
        prenom: document.getElementById('prenom').value,
        telephone: document.getElementById('telephone').value,
        permis_numero: document.getElementById('permis_numero').value,
        permis_expiration: document.getElementById('permis_expiration').value || null,
        actif: document.getElementById('actif').value === 'true',
        notes: document.getElementById('notes').value,
    };

    const url = id ? `/api/chauffeurs/${id}` : '/api/chauffeurs';
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
        loadChauffeurs();
    } catch (error) {
        alert('Erreur réseau');
    }
}

async function deleteChauffeur(id, nom) {
    if (!confirm(`Supprimer le chauffeur "${nom}" ?`)) return;
    try {
        await fetch(`/api/chauffeurs/${id}`, { method: 'DELETE' });
        loadChauffeurs();
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
loadChauffeurs();
