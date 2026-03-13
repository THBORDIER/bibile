/**
 * Bibile - Parametres
 * Gestion des zones, chauffeurs, vehicules et connexion externe
 */

let zones = [];
let chauffeurs = [];
let vehicules = [];

document.addEventListener('DOMContentLoaded', () => {
    // Onglets
    document.querySelectorAll('.settings-tab').forEach(tab => {
        tab.addEventListener('click', () => switchTab(tab.dataset.tab));
    });

    // === ZONES ===
    document.getElementById('btnAddZone').addEventListener('click', () => showZoneModal());
    document.getElementById('btnSaveZone').addEventListener('click', saveZone);
    document.getElementById('btnCancelZone').addEventListener('click', () => hideModal('modalAddZone'));
    document.getElementById('btnShowUnknown').addEventListener('click', showUnknownMapping);
    document.getElementById('btnSaveUnknownMapping').addEventListener('click', saveUnknownMapping);
    document.getElementById('btnCancelUnknownMapping').addEventListener('click', () => hideModal('modalUnknownMapping'));
    document.getElementById('btnGeocodeAll').addEventListener('click', geocodeAll);

    // === CHAUFFEURS ===
    document.getElementById('btnAddChauffeur').addEventListener('click', () => showChauffeurModal());
    document.getElementById('btnSaveChauffeur').addEventListener('click', saveChauffeur);
    document.getElementById('btnCancelChauffeur').addEventListener('click', () => hideModal('modalChauffeur'));

    // === VEHICULES ===
    document.getElementById('btnAddVehicule').addEventListener('click', () => showVehiculeModal());
    document.getElementById('btnSaveVehicule').addEventListener('click', saveVehicule);
    document.getElementById('btnCancelVehicule').addEventListener('click', () => hideModal('modalVehicule'));

    // === CONNEXION ===
    document.getElementById('btnTestConnection').addEventListener('click', testConnection);
    document.getElementById('btnSaveDbConfig').addEventListener('click', saveDbConfig);
    document.getElementById('btnSyncNow').addEventListener('click', syncNow);
    document.getElementById('btnRefreshExtDrivers').addEventListener('click', loadExtVehicles);

    // === DRAKKAR ===
    document.getElementById('btnTestDrakkar').addEventListener('click', testDrakkar);
    document.getElementById('btnSaveDrakkar').addEventListener('click', saveDrakkar);

    // === RECHERCHE ===
    document.getElementById('searchChauffeurs').addEventListener('input', filterChauffeurs);
    document.getElementById('searchVehicules').addEventListener('input', filterVehicules);
    document.getElementById('searchExtVehicles').addEventListener('input', filterExtVehicles);

    // Charger les données
    loadDrakkarConfig();
    loadZones();
    loadMapping();
    loadUnknownCities();
    loadChauffeurs();
    loadVehicules();
    loadDbConfig();
    loadSyncStatus();
    loadExtVehicles();
});


function switchTab(tabId) {
    document.querySelectorAll('.settings-tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.settings-panel').forEach(p => {
        p.classList.add('hidden');
        p.classList.remove('active');
    });
    document.querySelector(`.settings-tab[data-tab="${tabId}"]`).classList.add('active');
    const panel = document.getElementById('tab' + tabId.charAt(0).toUpperCase() + tabId.slice(1));
    panel.classList.remove('hidden');
    panel.classList.add('active');
}


// ===== ZONES =====

async function loadZones() {
    try {
        const resp = await fetch('/api/zones');
        const data = await resp.json();
        zones = data.zones || [];
        renderZones();
    } catch (e) {
        console.error('Erreur chargement zones:', e);
    }
}

function renderZones() {
    const container = document.getElementById('zonesList');
    if (zones.length === 0) {
        container.innerHTML = '<p class="text-muted">Aucune zone configuree.</p>';
        return;
    }
    container.innerHTML = zones.map(z => `
        <div class="zone-item">
            <div class="zone-header">
                <span class="zone-color-dot" style="background:${z.couleur}"></span>
                <strong>${escapeHtml(z.nom)}</strong>
                ${z.tournee_defaut ? `<span class="badge">${escapeHtml(z.tournee_defaut)}</span>` : ''}
                <span class="zone-city-count">${(z.villes || []).length} ville(s)</span>
            </div>
            <div class="zone-actions">
                <button class="btn btn-sm btn-secondary" onclick="showZoneModal(${z.id})">Modifier</button>
                <button class="btn btn-sm btn-danger" onclick="deleteZone(${z.id})">Supprimer</button>
            </div>
        </div>
    `).join('');
}

function showZoneModal(zoneId) {
    const zone = zoneId ? zones.find(z => z.id === zoneId) : null;
    document.getElementById('zoneModalTitle').textContent = zone ? 'Modifier la zone' : 'Nouvelle zone';
    document.getElementById('zoneEditId').value = zone ? zone.id : '';
    document.getElementById('inputZoneName').value = zone ? zone.nom : '';
    document.getElementById('inputZoneTournee').value = zone ? (zone.tournee_defaut || '') : '';
    document.getElementById('inputZoneColor').value = zone ? zone.couleur : '#4493f8';
    showModal('modalAddZone');
}

async function saveZone() {
    const data = {
        nom: document.getElementById('inputZoneName').value.trim(),
        tournee_defaut: document.getElementById('inputZoneTournee').value.trim(),
        couleur: document.getElementById('inputZoneColor').value,
    };
    if (!data.nom) return;

    const editId = document.getElementById('zoneEditId').value;
    if (editId) data.id = parseInt(editId);

    try {
        await fetch('/api/zones', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data),
        });
        hideModal('modalAddZone');
        loadZones();
    } catch (e) {
        console.error('Erreur sauvegarde zone:', e);
    }
}

async function deleteZone(zoneId) {
    if (!confirm('Supprimer cette zone ?')) return;
    try {
        await fetch(`/api/zones/${zoneId}`, { method: 'DELETE' });
        loadZones();
        loadMapping();
    } catch (e) {
        console.error('Erreur suppression zone:', e);
    }
}


// ===== MAPPING VILLES =====

async function loadMapping() {
    try {
        const resp = await fetch('/api/ville-zone-mapping');
        const data = await resp.json();
        renderMapping(data.mapping || []);
    } catch (e) {
        console.error('Erreur chargement mapping:', e);
    }
}

function renderMapping(mapping) {
    const body = document.getElementById('mappingBody');
    if (mapping.length === 0) {
        body.innerHTML = '<tr><td colspan="6" class="text-muted text-center">Aucun mapping configure.</td></tr>';
        return;
    }
    body.innerHTML = mapping.map(m => `
        <tr>
            <td>${escapeHtml(m.ville)}</td>
            <td>
                <select class="form-select form-select-sm" onchange="updateVilleZone('${escapeAttr(m.ville)}', this.value)">
                    <option value="">-- Aucune --</option>
                    ${zones.map(z => `<option value="${z.id}" ${m.zone_id === z.id ? 'selected' : ''}>${escapeHtml(z.nom)}</option>`).join('')}
                </select>
            </td>
            <td><input type="text" class="form-input form-input-sm" value="${escapeAttr(m.tournee_defaut || '')}" onchange="updateVilleTournee('${escapeAttr(m.ville)}', this.value)"></td>
            <td><input type="number" step="0.0001" class="form-input form-input-sm" value="${m.lat || ''}" onchange="updateVilleCoord('${escapeAttr(m.ville)}', 'lat', this.value)"></td>
            <td><input type="number" step="0.0001" class="form-input form-input-sm" value="${m.lon || ''}" onchange="updateVilleCoord('${escapeAttr(m.ville)}', 'lon', this.value)"></td>
            <td><button class="btn btn-sm btn-danger" onclick="deleteVilleMapping('${escapeAttr(m.ville)}')">X</button></td>
        </tr>
    `).join('');
}

async function updateVilleZone(ville, zoneId) {
    await fetch('/api/ville-zone-mapping', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ville, zone_id: zoneId ? parseInt(zoneId) : null }),
    });
}

async function updateVilleTournee(ville, tournee) {
    await fetch('/api/ville-zone-mapping', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ville, tournee_defaut: tournee }),
    });
}

async function updateVilleCoord(ville, field, value) {
    const data = { ville };
    data[field] = value ? parseFloat(value) : null;
    await fetch('/api/ville-zone-mapping', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
    });
}

async function deleteVilleMapping(ville) {
    // On supprime en mettant zone_id à null et tournee_defaut à ''
    await fetch('/api/ville-zone-mapping', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ville, zone_id: null, tournee_defaut: '' }),
    });
    loadMapping();
}


// ===== GEOCODAGE =====

async function geocodeAll() {
    const btn = document.getElementById('btnGeocodeAll');
    btn.disabled = true;
    btn.textContent = 'Geocodage en cours...';
    try {
        const resp = await fetch('/api/geocode-all', { method: 'POST' });
        const data = await resp.json();
        const msg = `${data.geocoded} ville(s) geocodee(s)`;
        const errMsg = data.errors && data.errors.length > 0
            ? ` | Non trouvees: ${data.errors.join(', ')}`
            : '';
        btn.textContent = msg + errMsg;
        setTimeout(() => { btn.textContent = 'Geocoder les villes'; btn.disabled = false; }, 4000);
        loadMapping();
    } catch (e) {
        console.error('Erreur geocodage:', e);
        btn.textContent = 'Erreur geocodage';
        setTimeout(() => { btn.textContent = 'Geocoder les villes'; btn.disabled = false; }, 3000);
    }
}


// ===== VILLES INCONNUES =====

async function loadUnknownCities() {
    try {
        const resp = await fetch('/api/villes-inconnues');
        const data = await resp.json();
        const villes = data.villes || [];
        const alert = document.getElementById('alertUnknownCities');
        if (villes.length > 0) {
            alert.classList.remove('hidden');
            document.getElementById('unknownCitiesCount').textContent = villes.length;
        } else {
            alert.classList.add('hidden');
        }
    } catch (e) {
        console.error('Erreur chargement villes inconnues:', e);
    }
}

async function showUnknownMapping() {
    try {
        const resp = await fetch('/api/villes-inconnues');
        const data = await resp.json();
        const villes = data.villes || [];

        const container = document.getElementById('unknownMappingList');
        container.innerHTML = villes.map(v => `
            <div class="unknown-mapping-item" data-ville="${escapeAttr(v.ville)}">
                <span class="unknown-ville">${escapeHtml(v.ville)} (${v.nb} enl.)</span>
                <select class="form-select form-select-sm unknown-zone-select">
                    <option value="">-- Choisir zone --</option>
                    ${zones.map(z => `<option value="${z.id}">${escapeHtml(z.nom)}</option>`).join('')}
                </select>
            </div>
        `).join('');

        showModal('modalUnknownMapping');
    } catch (e) {
        console.error('Erreur:', e);
    }
}

async function saveUnknownMapping() {
    const items = document.querySelectorAll('.unknown-mapping-item');
    for (const item of items) {
        const ville = item.dataset.ville;
        const zoneId = item.querySelector('.unknown-zone-select').value;
        const data = { ville };
        if (zoneId) data.zone_id = parseInt(zoneId);
        await fetch('/api/ville-zone-mapping', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data),
        });
    }
    hideModal('modalUnknownMapping');
    loadMapping();
    loadUnknownCities();
}


// ===== CHAUFFEURS =====

async function loadChauffeurs() {
    try {
        const resp = await fetch('/api/chauffeurs');
        const data = await resp.json();
        chauffeurs = data.chauffeurs || [];
        renderChauffeurs();
    } catch (e) {
        console.error('Erreur chargement chauffeurs:', e);
    }
}

function renderChauffeurs() {
    const body = document.getElementById('chauffeursList');
    if (chauffeurs.length === 0) {
        body.innerHTML = '<tr><td colspan="4" class="text-muted text-center">Aucun chauffeur.</td></tr>';
        return;
    }
    body.innerHTML = chauffeurs.map(c => `
        <tr>
            <td>${escapeHtml(c.nom)}</td>
            <td>${escapeHtml(c.prenom || '')}</td>
            <td>${escapeHtml(c.telephone || '')}</td>
            <td>
                <button class="btn btn-sm btn-secondary" onclick="showChauffeurModal(${c.id})">Modifier</button>
                <button class="btn btn-sm btn-danger" onclick="deleteChauffeur(${c.id})">Supprimer</button>
            </td>
        </tr>
    `).join('');
}

function showChauffeurModal(id) {
    const ch = id ? chauffeurs.find(c => c.id === id) : null;
    document.getElementById('chauffeurModalTitle').textContent = ch ? 'Modifier le chauffeur' : 'Nouveau chauffeur';
    document.getElementById('chauffeurEditId').value = ch ? ch.id : '';
    document.getElementById('inputChauffeurNom').value = ch ? ch.nom : '';
    document.getElementById('inputChauffeurPrenom').value = ch ? (ch.prenom || '') : '';
    document.getElementById('inputChauffeurTel').value = ch ? (ch.telephone || '') : '';
    showModal('modalChauffeur');
}

async function saveChauffeur() {
    const data = {
        nom: document.getElementById('inputChauffeurNom').value.trim(),
        prenom: document.getElementById('inputChauffeurPrenom').value.trim(),
        telephone: document.getElementById('inputChauffeurTel').value.trim(),
    };
    if (!data.nom) return;

    const editId = document.getElementById('chauffeurEditId').value;
    if (editId) data.id = parseInt(editId);

    try {
        await fetch('/api/chauffeurs', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data),
        });
        hideModal('modalChauffeur');
        loadChauffeurs();
    } catch (e) {
        console.error('Erreur sauvegarde chauffeur:', e);
    }
}

async function deleteChauffeur(id) {
    if (!confirm('Supprimer ce chauffeur ?')) return;
    try {
        await fetch(`/api/chauffeurs/${id}`, { method: 'DELETE' });
        loadChauffeurs();
    } catch (e) {
        console.error('Erreur suppression chauffeur:', e);
    }
}


// ===== VEHICULES =====

async function loadVehicules() {
    try {
        const resp = await fetch('/api/vehicules');
        const data = await resp.json();
        vehicules = data.vehicules || [];
        renderVehicules();
    } catch (e) {
        console.error('Erreur chargement vehicules:', e);
    }
}

function renderVehicules() {
    const body = document.getElementById('vehiculesList');
    if (vehicules.length === 0) {
        body.innerHTML = '<tr><td colspan="4" class="text-muted text-center">Aucun vehicule.</td></tr>';
        return;
    }
    body.innerHTML = vehicules.map(v => `
        <tr>
            <td>${escapeHtml(v.immatriculation)}</td>
            <td>${escapeHtml(v.type_vehicule || '')}</td>
            <td>${v.capacite_palettes || 0}</td>
            <td>
                <button class="btn btn-sm btn-secondary" onclick="showVehiculeModal(${v.id})">Modifier</button>
                <button class="btn btn-sm btn-danger" onclick="deleteVehicule(${v.id})">Supprimer</button>
            </td>
        </tr>
    `).join('');
}

function showVehiculeModal(id) {
    const vh = id ? vehicules.find(v => v.id === id) : null;
    document.getElementById('vehiculeModalTitle').textContent = vh ? 'Modifier le vehicule' : 'Nouveau vehicule';
    document.getElementById('vehiculeEditId').value = vh ? vh.id : '';
    document.getElementById('inputVehiculeImmat').value = vh ? vh.immatriculation : '';
    document.getElementById('inputVehiculeType').value = vh ? (vh.type_vehicule || '') : '';
    document.getElementById('inputVehiculeCap').value = vh ? vh.capacite_palettes : 0;
    showModal('modalVehicule');
}

async function saveVehicule() {
    const data = {
        immatriculation: document.getElementById('inputVehiculeImmat').value.trim(),
        type_vehicule: document.getElementById('inputVehiculeType').value.trim(),
        capacite_palettes: parseInt(document.getElementById('inputVehiculeCap').value) || 0,
    };
    if (!data.immatriculation) return;

    const editId = document.getElementById('vehiculeEditId').value;
    if (editId) data.id = parseInt(editId);

    try {
        await fetch('/api/vehicules', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data),
        });
        hideModal('modalVehicule');
        loadVehicules();
    } catch (e) {
        console.error('Erreur sauvegarde vehicule:', e);
    }
}

async function deleteVehicule(id) {
    if (!confirm('Supprimer ce vehicule ?')) return;
    try {
        await fetch(`/api/vehicules/${id}`, { method: 'DELETE' });
        loadVehicules();
    } catch (e) {
        console.error('Erreur suppression vehicule:', e);
    }
}


// ===== CONNEXION EXTERNE =====

async function loadDbConfig() {
    try {
        const resp = await fetch('/api/external-db/config');
        const data = await resp.json();
        if (data.config) {
            const c = data.config;
            document.getElementById('inputDbType').value = c.db_type || 'sqlserver';
            document.getElementById('inputDbHost').value = c.host || '';
            document.getElementById('inputDbPort').value = c.port || 1433;
            document.getElementById('inputDbName').value = c.database_name || '';
            document.getElementById('inputDbUser').value = c.username || '';
            document.getElementById('inputSyncInterval').value = c.sync_interval_minutes || 60;
        }
    } catch (e) {
        console.error('Erreur chargement config:', e);
    }
}

async function loadSyncStatus() {
    try {
        const resp = await fetch('/api/external-db/status');
        const data = await resp.json();
        const status = document.getElementById('syncStatus');
        const dot = status.querySelector('.sync-dot');
        const text = status.querySelector('.sync-text');

        if (!data.configured) {
            dot.className = 'sync-dot';
            text.textContent = 'Non configure';
        } else if (data.is_syncing) {
            dot.className = 'sync-dot sync-active';
            text.textContent = 'Synchronisation en cours...';
        } else if (data.last_error) {
            dot.className = 'sync-dot sync-error';
            text.textContent = `Erreur: ${data.last_error}`;
        } else if (data.last_sync) {
            dot.className = 'sync-dot sync-ok';
            const d = new Date(data.last_sync);
            text.textContent = `Derniere synchro: ${d.toLocaleString('fr-FR')}`;
        } else {
            dot.className = 'sync-dot sync-ok';
            text.textContent = 'Configure - En attente';
        }
    } catch (e) {
        console.error('Erreur statut sync:', e);
    }
}

function getDbFormData() {
    return {
        db_type: document.getElementById('inputDbType').value,
        host: document.getElementById('inputDbHost').value.trim(),
        port: parseInt(document.getElementById('inputDbPort').value) || 1433,
        database_name: document.getElementById('inputDbName').value.trim(),
        username: document.getElementById('inputDbUser').value.trim(),
        password_encrypted: document.getElementById('inputDbPass').value,
        sync_interval_minutes: parseInt(document.getElementById('inputSyncInterval').value) || 60,
    };
}

async function testConnection() {
    const result = document.getElementById('connectionResult');
    result.classList.remove('hidden', 'alert-success', 'alert-danger');
    result.textContent = 'Test en cours...';
    result.classList.add('alert-info');

    try {
        const resp = await fetch('/api/external-db/test', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(getDbFormData()),
        });
        const data = await resp.json();
        result.classList.remove('alert-info');
        if (data.success) {
            result.classList.add('alert-success');
            result.textContent = 'Connexion reussie !';
        } else {
            result.classList.add('alert-danger');
            result.textContent = `Echec: ${data.message}`;
        }
    } catch (e) {
        result.classList.remove('alert-info');
        result.classList.add('alert-danger');
        result.textContent = `Erreur: ${e.message}`;
    }
}

async function saveDbConfig() {
    try {
        await fetch('/api/external-db/config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(getDbFormData()),
        });
        const result = document.getElementById('connectionResult');
        result.classList.remove('hidden', 'alert-danger', 'alert-info');
        result.classList.add('alert-success');
        result.textContent = 'Configuration enregistree.';
        loadSyncStatus();
    } catch (e) {
        console.error('Erreur sauvegarde config:', e);
    }
}

async function syncNow() {
    try {
        await fetch('/api/external-db/sync', { method: 'POST' });
        const result = document.getElementById('connectionResult');
        result.classList.remove('hidden', 'alert-danger', 'alert-info');
        result.classList.add('alert-success');
        result.textContent = 'Synchronisation declenchee.';
        setTimeout(loadSyncStatus, 2000);
    } catch (e) {
        console.error('Erreur sync:', e);
    }
}

async function loadExtVehicles() {
    const container = document.getElementById('extDriversList');
    container.innerHTML = '<p class="text-muted">Chargement...</p>';
    try {
        const resp = await fetch('/api/external-db/vehicules');
        const data = await resp.json();
        if (data.erreur) {
            container.innerHTML = `<p class="text-muted">${escapeHtml(data.erreur)}</p>`;
            return;
        }
        const vehicles = data.vehicules || [];
        if (vehicles.length === 0) {
            container.innerHTML = '<p class="text-muted">Aucun vehicule trouve.</p>';
            return;
        }

        // Charger les sélections actuelles
        const syncResp = await fetch('/api/external-db/vehicules');
        const syncData = await syncResp.json();
        const selectedIds = new Set((syncData.vehicules || []).filter(v => v.selectionne).map(v => v.externe_id));

        container.innerHTML = vehicles.map(v => `
            <label class="ext-driver-item">
                <input type="checkbox" class="ext-vehicle-check" data-id="${escapeAttr(v.externe_id)}" data-immat="${escapeAttr(v.immatriculation)}" ${selectedIds.has(v.externe_id) ? 'checked' : ''}>
                ${escapeHtml(v.immatriculation)}
            </label>
        `).join('') + '<br><button class="btn btn-primary btn-sm" onclick="saveExtVehicleSelection()">Enregistrer la selection</button>';
    } catch (e) {
        container.innerHTML = `<p class="text-muted">Erreur: ${e.message}</p>`;
    }
}

async function saveExtVehicleSelection() {
    const checks = document.querySelectorAll('.ext-vehicle-check');
    const selections = Array.from(checks).map(ch => ({
        externe_id: ch.dataset.id,
        immatriculation: ch.dataset.immat,
        selectionne: ch.checked ? 1 : 0,
    }));

    try {
        await fetch('/api/external-db/vehicules/selection', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ selections }),
        });
        const result = document.getElementById('connectionResult');
        result.classList.remove('hidden', 'alert-danger', 'alert-info');
        result.classList.add('alert-success');
        result.textContent = 'Selection vehicules enregistree.';
    } catch (e) {
        console.error('Erreur sauvegarde selection:', e);
    }
}


// ===== RECHERCHE / FILTRAGE =====

function filterChauffeurs() {
    const q = document.getElementById('searchChauffeurs').value.toLowerCase();
    document.querySelectorAll('#chauffeursList tr').forEach(tr => {
        const text = tr.textContent.toLowerCase();
        tr.style.display = text.includes(q) ? '' : 'none';
    });
}

function filterVehicules() {
    const q = document.getElementById('searchVehicules').value.toLowerCase();
    document.querySelectorAll('#vehiculesList tr').forEach(tr => {
        const text = tr.textContent.toLowerCase();
        tr.style.display = text.includes(q) ? '' : 'none';
    });
}

function filterExtVehicles() {
    const q = document.getElementById('searchExtVehicles').value.toLowerCase();
    document.querySelectorAll('#extDriversList .ext-driver-item').forEach(el => {
        const text = el.textContent.toLowerCase();
        el.style.display = text.includes(q) ? '' : 'none';
    });
}


// ===== UTILS =====

function showModal(id) {
    document.getElementById(id).classList.remove('hidden');
}

function hideModal(id) {
    document.getElementById(id).classList.add('hidden');
}

function escapeHtml(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

function escapeAttr(str) {
    if (!str) return '';
    return str.replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}


// ===== DRAKKAR (EDI) =====

async function loadDrakkarConfig() {
    try {
        const resp = await fetch('/api/drakkar/config');
        const data = await resp.json();
        if (data.config) {
            const c = data.config;
            document.getElementById('inputDrakkarHost').value = c.host || '';
            document.getElementById('inputDrakkarPort').value = c.port || 49372;
            document.getElementById('inputDrakkarName').value = c.database_name || '';
            document.getElementById('inputDrakkarUser').value = c.username || '';
        }
    } catch (e) {
        console.error('Erreur chargement config Drakkar:', e);
    }
}

function getDrakkarFormData() {
    return {
        host: document.getElementById('inputDrakkarHost').value,
        port: parseInt(document.getElementById('inputDrakkarPort').value) || 49372,
        database_name: document.getElementById('inputDrakkarName').value,
        username: document.getElementById('inputDrakkarUser').value,
        password_encrypted: document.getElementById('inputDrakkarPass').value,
        db_type: 'sqlserver',
    };
}

async function testDrakkar() {
    const resultDiv = document.getElementById('drakkarResult');
    resultDiv.classList.remove('hidden', 'alert-success', 'alert-danger');
    resultDiv.textContent = 'Test en cours...';
    resultDiv.classList.add('alert-info');
    try {
        const resp = await fetch('/api/drakkar/test', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(getDrakkarFormData()),
        });
        const data = await resp.json();
        resultDiv.classList.remove('alert-info');
        if (data.success) {
            resultDiv.classList.add('alert-success');
            resultDiv.textContent = data.message;
        } else {
            resultDiv.classList.add('alert-danger');
            resultDiv.textContent = data.message;
        }
    } catch (e) {
        resultDiv.classList.remove('alert-info');
        resultDiv.classList.add('alert-danger');
        resultDiv.textContent = 'Erreur: ' + e.message;
    }
}

async function saveDrakkar() {
    try {
        const resp = await fetch('/api/drakkar/config', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(getDrakkarFormData()),
        });
        const data = await resp.json();
        if (data.ok) {
            const resultDiv = document.getElementById('drakkarResult');
            resultDiv.classList.remove('hidden', 'alert-danger', 'alert-info');
            resultDiv.classList.add('alert-success');
            resultDiv.textContent = 'Configuration Drakkar enregistree.';
        }
    } catch (e) {
        console.error('Erreur sauvegarde config Drakkar:', e);
    }
}
