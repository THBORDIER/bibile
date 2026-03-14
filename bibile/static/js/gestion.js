/**
 * Bibile - Gestion
 * Gestion des zones, chauffeurs, vehicules et mapping villes
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

    // === RECHERCHE ===
    document.getElementById('searchChauffeurs').addEventListener('input', filterChauffeurs);
    document.getElementById('searchVehicules').addEventListener('input', filterVehicules);

    // === MODELES ===
    document.getElementById('btnAddModele').addEventListener('click', () => showModeleModal());
    document.getElementById('btnSaveModele').addEventListener('click', saveModele);
    document.getElementById('btnCancelModele').addEventListener('click', () => hideModal('modalModele'));

    // Charger les donnees
    loadZones();
    loadMapping();
    loadUnknownCities();
    loadChauffeurs();
    loadVehicules();
    loadTourneeNoms();
    loadModeles();
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
            <td>
                <input type="text" class="form-input form-input-sm" value="${escapeAttr(m.tournee_defaut || '')}" onchange="updateVilleTournee('${escapeAttr(m.ville)}', this.value)" list="datalistTourneeNoms" title="Surcharge la tournee de la zone si renseigne">
            </td>
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


// ===== MODELES DE TOURNEES =====

let modeles = [];

async function loadModeles() {
    try {
        const resp = await fetch('/api/tournee-modeles?actifs=1');
        const data = await resp.json();
        modeles = data.modeles || [];
        renderModeles();
    } catch (e) {
        console.error('Erreur chargement modeles:', e);
    }
}

function renderModeles() {
    const body = document.getElementById('modelesList');
    if (modeles.length === 0) {
        body.innerHTML = '<tr><td colspan="6" class="text-muted text-center">Aucun modele de tournee.</td></tr>';
        return;
    }
    body.innerHTML = modeles.map(m => `
        <tr>
            <td><span class="zone-color-dot" style="background:${m.couleur || '#4493f8'}"></span></td>
            <td><strong>${escapeHtml(m.nom)}</strong></td>
            <td>${m.chauffeur_nom ? escapeHtml(m.chauffeur_nom) + ' ' + escapeHtml(m.chauffeur_prenom || '') : '<span class="text-muted">--</span>'}</td>
            <td>${m.vehicule_immat ? escapeHtml(m.vehicule_immat) : '<span class="text-muted">--</span>'}</td>
            <td>${m.ordre_tri || 0}</td>
            <td>
                <button class="btn btn-sm btn-secondary" onclick="showModeleModal(${m.id})">Modifier</button>
                <button class="btn btn-sm btn-danger" onclick="deleteModele(${m.id})">Supprimer</button>
            </td>
        </tr>
    `).join('');
}

function showModeleModal(modeleId) {
    const m = modeleId ? modeles.find(x => x.id === modeleId) : null;
    document.getElementById('modeleModalTitle').textContent = m ? 'Modifier la tournee' : 'Nouvelle tournee';
    document.getElementById('modeleEditId').value = m ? m.id : '';
    document.getElementById('inputModeleNom').value = m ? m.nom : '';
    document.getElementById('inputModeleCouleur').value = m ? (m.couleur || '#4493f8') : '#4493f8';
    document.getElementById('inputModeleOrdre').value = m ? (m.ordre_tri || 0) : 0;

    // Remplir les selects chauffeur/vehicule
    const selChauffeur = document.getElementById('selectModeleChauffeur');
    selChauffeur.innerHTML = '<option value="">-- Aucun --</option>' +
        chauffeurs.map(c => `<option value="${c.id}" ${m && m.chauffeur_id === c.id ? 'selected' : ''}>${escapeHtml(c.nom)} ${escapeHtml(c.prenom || '')}</option>`).join('');

    const selVehicule = document.getElementById('selectModeleVehicule');
    selVehicule.innerHTML = '<option value="">-- Aucun --</option>' +
        vehicules.map(v => `<option value="${v.id}" ${m && m.vehicule_id === v.id ? 'selected' : ''}>${escapeHtml(v.immatriculation)}</option>`).join('');

    showModal('modalModele');
}

async function saveModele() {
    const data = {
        nom: document.getElementById('inputModeleNom').value.trim(),
        chauffeur_id: document.getElementById('selectModeleChauffeur').value ? parseInt(document.getElementById('selectModeleChauffeur').value) : null,
        vehicule_id: document.getElementById('selectModeleVehicule').value ? parseInt(document.getElementById('selectModeleVehicule').value) : null,
        couleur: document.getElementById('inputModeleCouleur').value,
        ordre_tri: parseInt(document.getElementById('inputModeleOrdre').value) || 0,
    };
    if (!data.nom) return;

    const editId = document.getElementById('modeleEditId').value;
    if (editId) data.id = parseInt(editId);

    try {
        await fetch('/api/tournee-modeles', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data),
        });
        hideModal('modalModele');
        loadModeles();
    } catch (e) {
        console.error('Erreur sauvegarde modele:', e);
    }
}

async function deleteModele(id) {
    if (!confirm('Desactiver cette tournee ? Elle ne sera plus creee automatiquement.')) return;
    try {
        await fetch(`/api/tournee-modeles/${id}`, { method: 'DELETE' });
        loadModeles();
    } catch (e) {
        console.error('Erreur suppression modele:', e);
    }
}


// ===== TOURNEE NOMS (autocomplete) =====

async function loadTourneeNoms() {
    try {
        const resp = await fetch('/api/tournees/noms');
        const data = await resp.json();
        const noms = data.noms || [];
        const datalist = document.getElementById('datalistTourneeNoms');
        datalist.innerHTML = noms.map(n => `<option value="${escapeAttr(n)}">${escapeHtml(n)}</option>`).join('');
    } catch (e) {
        console.error('Erreur chargement noms tournees:', e);
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


// ===== UTILS =====

function showModal(id) {
    document.getElementById(id).classList.remove('hidden');
}

function hideModal(id) {
    const modal = document.getElementById(id);
    modal.classList.add('hidden');
    modal.querySelectorAll('input:not([type="hidden"]), select, textarea').forEach(el => {
        if (el.type === 'color') el.value = '#4493f8';
        else if (el.type === 'number') el.value = '0';
        else if (el.tagName === 'SELECT') el.selectedIndex = 0;
        else el.value = '';
    });
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
