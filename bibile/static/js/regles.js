// Regles de tournees CRUD

let chauffeursList = [];
let vehiculesList = [];

async function loadRegles() {
    try {
        // Charger regles + chauffeurs + vehicules en parallele
        const [reglesRes, chauffeursRes, vehiculesRes] = await Promise.all([
            fetch('/api/regles'),
            fetch('/api/chauffeurs'),
            fetch('/api/vehicules')
        ]);

        const reglesData = await reglesRes.json();
        const chauffeursData = await chauffeursRes.json();
        const vehiculesData = await vehiculesRes.json();

        chauffeursList = (chauffeursData.chauffeurs || []).filter(c => c.actif);
        vehiculesList = (vehiculesData.vehicules || []).filter(v => v.actif);

        renderList(reglesData.regles || []);
    } catch (error) {
        console.error('Erreur:', error);
        document.getElementById('reglesList').innerHTML =
            '<div class="status-message error">Erreur de chargement</div>';
    }
}

function renderList(regles) {
    const container = document.getElementById('reglesList');

    if (regles.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <div class="empty-icon">📋</div>
                <h3>Aucune règle</h3>
                <p>Cliquez sur "+ Ajouter une règle" pour définir une affectation automatique</p>
            </div>`;
        return;
    }

    container.innerHTML = `
        <div class="table-container">
            <table class="data-table">
                <thead>
                    <tr>
                        <th>Priorité</th>
                        <th>Nom</th>
                        <th>Livraison</th>
                        <th>Ville</th>
                        <th>Jour</th>
                        <th>Chauffeur</th>
                        <th>Véhicule</th>
                        <th>Statut</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody>
                    ${regles.map(r => `
                        <tr class="${r.actif ? '' : 'row-inactive'}">
                            <td><strong>${r.priorite}</strong></td>
                            <td>${escapeHtml(r.nom)}</td>
                            <td>${escapeHtml(r.livraison) || '<em>Toutes</em>'}</td>
                            <td>${escapeHtml(r.ville_pattern) || '<em>Toutes</em>'}</td>
                            <td>${r.jour_semaine_nom || '<em>Tous</em>'}</td>
                            <td>${escapeHtml(r.chauffeur_nom) || '--'}</td>
                            <td>${escapeHtml(r.vehicule_immat) || '--'}</td>
                            <td><span class="badge ${r.actif ? 'badge-success' : 'badge-inactive'}">${r.actif ? 'Active' : 'Inactive'}</span></td>
                            <td class="actions-cell">
                                <button class="btn-small btn-download" onclick="editRegle(${r.id})">Modifier</button>
                                <button class="btn-small btn-log" onclick="deleteRegle(${r.id}, '${escapeHtml(r.nom)}')">Supprimer</button>
                            </td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        </div>`;
}

function populateSelects() {
    const chauffeurSelect = document.getElementById('chauffeur_id');
    chauffeurSelect.innerHTML = '<option value="">-- Aucun --</option>';
    chauffeursList.forEach(c => {
        chauffeurSelect.innerHTML += `<option value="${c.id}">${escapeHtml(c.nom_complet)}</option>`;
    });

    const vehiculeSelect = document.getElementById('vehicule_id');
    vehiculeSelect.innerHTML = '<option value="">-- Aucun --</option>';
    vehiculesList.forEach(v => {
        vehiculeSelect.innerHTML += `<option value="${v.id}">${escapeHtml(v.immatriculation)} (${escapeHtml(v.marque)} ${escapeHtml(v.modele)})</option>`;
    });
}

function openModal(data = null) {
    populateSelects();
    document.getElementById('modal').classList.remove('hidden');
    document.getElementById('modalTitle').textContent = data ? 'Modifier la règle' : 'Ajouter une règle';
    document.getElementById('editId').value = data ? data.id : '';
    document.getElementById('nom').value = data ? data.nom : '';
    document.getElementById('livraison').value = data ? data.livraison : '';
    document.getElementById('ville_pattern').value = data ? data.ville_pattern : '';
    document.getElementById('jour_semaine').value = data && data.jour_semaine !== null ? data.jour_semaine : '';
    document.getElementById('chauffeur_id').value = data && data.chauffeur_id ? data.chauffeur_id : '';
    document.getElementById('vehicule_id').value = data && data.vehicule_id ? data.vehicule_id : '';
    document.getElementById('priorite').value = data ? data.priorite : 0;
    document.getElementById('actif').value = data ? String(data.actif) : 'true';
}

function closeModal() {
    document.getElementById('modal').classList.add('hidden');
}

async function editRegle(id) {
    const response = await fetch('/api/regles');
    const data = await response.json();
    const regle = (data.regles || []).find(r => r.id === id);
    if (regle) openModal(regle);
}

async function saveForm(event) {
    event.preventDefault();
    const id = document.getElementById('editId').value;
    const payload = {
        nom: document.getElementById('nom').value,
        livraison: document.getElementById('livraison').value || null,
        ville_pattern: document.getElementById('ville_pattern').value || null,
        jour_semaine: document.getElementById('jour_semaine').value !== '' ? parseInt(document.getElementById('jour_semaine').value) : null,
        chauffeur_id: document.getElementById('chauffeur_id').value ? parseInt(document.getElementById('chauffeur_id').value) : null,
        vehicule_id: document.getElementById('vehicule_id').value ? parseInt(document.getElementById('vehicule_id').value) : null,
        priorite: parseInt(document.getElementById('priorite').value) || 0,
        actif: document.getElementById('actif').value === 'true',
    };

    const url = id ? `/api/regles/${id}` : '/api/regles';
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
        loadRegles();
    } catch (error) {
        alert('Erreur réseau');
    }
}

async function deleteRegle(id, nom) {
    if (!confirm(`Supprimer la règle "${nom}" ?`)) return;
    try {
        await fetch(`/api/regles/${id}`, { method: 'DELETE' });
        loadRegles();
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
loadRegles();
