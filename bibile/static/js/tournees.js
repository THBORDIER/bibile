/**
 * Bibile - Tournees Kanban
 * Gestion drag-and-drop des enlèvements dans les tournées
 */

let currentDate = '';
let currentExtractionId = null;
let tournees = [];
let unassigned = [];
let chauffeurs = [];
let vehicules = [];

document.addEventListener('DOMContentLoaded', () => {
    // Initialiser la date à aujourd'hui
    const today = new Date().toISOString().split('T')[0];
    document.getElementById('datePicker').value = today;
    currentDate = today;

    // Event listeners
    document.getElementById('datePicker').addEventListener('change', onDateChange);
    document.getElementById('extractionSelect').addEventListener('change', onExtractionChange);
    document.getElementById('btnNewTournee').addEventListener('click', showNewTourneeModal);
    document.getElementById('btnAutoDistrib').addEventListener('click', autoDistribuer);
    document.getElementById('btnCreateTournee').addEventListener('click', createTournee);
    document.getElementById('btnCancelTournee').addEventListener('click', () => hideModal('modalNewTournee'));
    document.getElementById('btnCloseUnknown').addEventListener('click', () => hideModal('modalUnknownCities'));
    document.getElementById('btnSaveEditTournee').addEventListener('click', saveEditTournee);
    document.getElementById('btnDeleteTournee').addEventListener('click', deleteTournee);
    document.getElementById('btnCancelEditTournee').addEventListener('click', () => hideModal('modalEditTournee'));
    document.getElementById('btnSaveEnlevement').addEventListener('click', saveEnlevement);
    document.getElementById('btnCancelEnlevement').addEventListener('click', () => hideModal('modalEnlevement'));

    // Navigation date
    document.getElementById('btnPrevDay').addEventListener('click', () => changeDay(-1));
    document.getElementById('btnNextDay').addEventListener('click', () => changeDay(1));
    document.getElementById('btnToday').addEventListener('click', () => {
        const today = new Date().toISOString().split('T')[0];
        document.getElementById('datePicker').value = today;
        onDateChange();
    });

    // Toggle vues
    document.querySelectorAll('.btn-view[data-view]').forEach(btn => {
        btn.addEventListener('click', () => toggleView(btn.dataset.view));
    });

    // Charger les données initiales
    loadChauffeurs();
    loadVehicules();
    loadExtractions();
    loadData();
});


function onDateChange() {
    currentDate = document.getElementById('datePicker').value;
    currentExtractionId = null;
    loadExtractions();
    loadData();
}


function changeDay(delta) {
    const picker = document.getElementById('datePicker');
    const d = new Date(picker.value);
    d.setDate(d.getDate() + delta);
    picker.value = d.toISOString().split('T')[0];
    onDateChange();
}


function onExtractionChange() {
    const val = document.getElementById('extractionSelect').value;
    currentExtractionId = val ? parseInt(val) : null;
    loadData();
}


async function loadExtractions() {
    try {
        const resp = await fetch(`/api/extractions-par-date?date=${currentDate}`);
        const data = await resp.json();
        const select = document.getElementById('extractionSelect');
        select.innerHTML = '<option value="">-- Toutes --</option>';
        (data.extractions || []).forEach(e => {
            const opt = document.createElement('option');
            opt.value = e.id;
            opt.textContent = `${e.nom_fichier} (${e.nb_lignes} lignes)`;
            select.appendChild(opt);
        });
    } catch (e) {
        console.error('Erreur chargement extractions:', e);
    }
}


async function loadChauffeurs() {
    try {
        const resp = await fetch('/api/chauffeurs');
        const data = await resp.json();
        chauffeurs = data.chauffeurs || [];
        populateSelect('selectChauffeur', chauffeurs, 'id', c => `${c.nom} ${c.prenom || ''}`.trim());
        populateSelect('editChauffeur', chauffeurs, 'id', c => `${c.nom} ${c.prenom || ''}`.trim());
    } catch (e) {
        console.error('Erreur chargement chauffeurs:', e);
    }
}


async function loadVehicules() {
    try {
        const resp = await fetch('/api/vehicules');
        const data = await resp.json();
        vehicules = data.vehicules || [];
        populateSelect('selectVehicule', vehicules, 'id', v => `${v.immatriculation} (${v.type_vehicule || ''})`);
        populateSelect('editVehicule', vehicules, 'id', v => `${v.immatriculation} (${v.type_vehicule || ''})`);
    } catch (e) {
        console.error('Erreur chargement vehicules:', e);
    }
}


function populateSelect(selectId, items, valueKey, labelFn) {
    const select = document.getElementById(selectId);
    const first = select.querySelector('option');
    select.innerHTML = '';
    select.appendChild(first);
    items.forEach(item => {
        const opt = document.createElement('option');
        opt.value = item[valueKey];
        opt.textContent = labelFn(item);
        select.appendChild(opt);
    });
}


async function loadData() {
    try {
        // Charger tournées et non-assignés en parallèle
        const params = currentExtractionId
            ? `extraction_id=${currentExtractionId}`
            : `date=${currentDate}`;

        const [tourneesResp, unassignedResp] = await Promise.all([
            fetch(`/api/tournees?date=${currentDate}`),
            fetch(`/api/enlevements-non-assignes?${params}`),
        ]);

        const tourneesData = await tourneesResp.json();
        const unassignedData = await unassignedResp.json();

        tournees = tourneesData.tournees || [];
        unassigned = unassignedData.enlevements || [];

        renderKanban();

        // Mettre à jour la feuille de route si visible
        if (!document.getElementById('feuilleView').classList.contains('hidden')) {
            renderFeuille();
        }

        // Mettre à jour la carte si visible
        if (typeof updateMap === 'function' && !document.getElementById('mapView').classList.contains('hidden')) {
            await updateMap(tournees, unassigned);
        }

        // Mettre à jour les badges de progression dans le Kanban (après updateMap pour que progressionData soit rempli)
        updateKanbanProgression();
    } catch (e) {
        console.error('Erreur chargement données:', e);
    }
}


function renderKanban() {
    const container = document.getElementById('kanbanView');

    // Garder la colonne non-assigné, supprimer les autres
    const existing = container.querySelectorAll('.kanban-column:not(#colUnassigned)');
    existing.forEach(el => el.remove());

    // Remplir la colonne non-assigné
    const listUnassigned = document.getElementById('listUnassigned');
    listUnassigned.innerHTML = '';
    unassigned.forEach(e => {
        listUnassigned.appendChild(createCard(e));
    });
    document.getElementById('countUnassigned').textContent = unassigned.length;

    // Créer les colonnes de tournées
    tournees.forEach(t => {
        const col = document.createElement('div');
        col.className = 'kanban-column';
        col.dataset.statut = t.statut || 'brouillon';

        const chauffeurOptions = chauffeurs.map(c =>
            `<option value="${c.id}" ${t.chauffeur_id === c.id ? 'selected' : ''}>${escapeHtml(c.nom)} ${escapeHtml(c.prenom || '')}</option>`
        ).join('');

        const vehiculeOptions = vehicules.map(v =>
            `<option value="${v.id}" ${t.vehicule_id === v.id ? 'selected' : ''}>${escapeHtml(v.immatriculation)}</option>`
        ).join('');

        const nbEnl = (t.enlevements || []).length;
        const totalPal = (t.enlevements || []).reduce((s, e) => s + (e.nb_palettes || 0), 0);
        const totalKg = (t.enlevements || []).reduce((s, e) => s + (e.poids_total || 0), 0);

        col.innerHTML = `
            <div class="kanban-column-header">
                <div class="kanban-header-top">
                    ${t.couleur ? `<span class="zone-color-dot" style="background:${t.couleur}"></span>` : ''}
                    <h3 class="kanban-title-click" data-tournee-id="${t.id}">${escapeHtml(t.nom)}</h3>
                    <span class="kanban-count">${nbEnl}</span>
                </div>
                <div class="kanban-assigns">
                    <select class="kanban-select kanban-select-chauffeur" data-tournee-id="${t.id}" title="Chauffeur">
                        <option value="">Chauffeur...</option>
                        ${chauffeurOptions}
                    </select>
                    <select class="kanban-select kanban-select-vehicule" data-tournee-id="${t.id}" title="Vehicule">
                        <option value="">Vehicule...</option>
                        ${vehiculeOptions}
                    </select>
                </div>
                <div class="kanban-header-meta">
                    <span class="badge badge-statut badge-${t.statut}">${t.statut}</span>
                    ${nbEnl > 0 ? `<span class="badge">${totalPal} pal. / ${totalKg} kg</span>` : ''}
                    <span class="kanban-progress" id="progress_${t.id}"></span>
                </div>
            </div>
            <div class="kanban-column-body" data-tournee-id="${t.id}"></div>
        `;

        // Remplir les cartes
        const body = col.querySelector('.kanban-column-body');
        (t.enlevements || []).forEach(e => {
            body.appendChild(createCard(e));
        });

        // Click sur le titre pour éditer la tournée
        col.querySelector('.kanban-title-click').addEventListener('click', () => showEditTourneeModal(t));

        // Selects inline chauffeur/vehicule
        col.querySelector('.kanban-select-chauffeur').addEventListener('change', async (e) => {
            const resp = await fetch(`/api/tournees/${t.id}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ chauffeur_id: e.target.value || null }),
            });
            if (!resp.ok) alert('Erreur lors de l\'attribution du chauffeur.');
        });
        col.querySelector('.kanban-select-vehicule').addEventListener('change', async (e) => {
            const resp = await fetch(`/api/tournees/${t.id}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ vehicule_id: e.target.value || null }),
            });
            if (!resp.ok) alert('Erreur lors de l\'attribution du vehicule.');
        });

        container.appendChild(col);
    });

    // Initialiser SortableJS sur toutes les colonnes
    initSortable();
}


function createCard(e) {
    const card = document.createElement('div');
    card.className = 'kanban-card';
    card.dataset.id = e.id;

    const livraison = (e.livraison || '').toLowerCase();
    if (livraison === 'brevet') card.classList.add('card-brevet');
    else if (livraison === 'transit') card.classList.add('card-transit');
    else if (livraison === 'chevrolet') card.classList.add('card-chevrolet');

    card.innerHTML = `
        <div class="card-header-row">
            <span class="card-num">#${e.num_enlevement || ''}</span>
            <span class="card-palettes">${e.nb_palettes || 0} ${e.type_palettes || ''}</span>
        </div>
        <div class="card-societe">${escapeHtml(e.societe || '')}</div>
        <div class="card-footer-row">
            <span class="card-ville">${escapeHtml(e.ville || '')}</span>
            <span class="card-poids">${e.poids_total || 0} kg</span>
        </div>
    `;
    return card;
}


function initSortable() {
    document.querySelectorAll('.kanban-column-body').forEach(el => {
        // Détruire l'ancien Sortable si existant
        if (el._sortable) el._sortable.destroy();

        const isTermine = el.closest('.kanban-column')?.dataset.statut === 'termine';
        el._sortable = new Sortable(el, {
            group: 'tournees',
            animation: 150,
            ghostClass: 'kanban-card-ghost',
            dragClass: 'kanban-card-dragging',
            disabled: isTermine,
            onEnd: onDragEnd,
        });
    });
}


async function onDragEnd(evt) {
    const enlevementId = parseInt(evt.item.dataset.id);
    const fromTourneeId = parseInt(evt.from.dataset.tourneeId);
    const toTourneeId = parseInt(evt.to.dataset.tourneeId);

    if (fromTourneeId === toTourneeId && evt.oldIndex === evt.newIndex) return;

    try {
        // Retirer de l'ancienne tournée (si ce n'est pas "non assigné")
        if (fromTourneeId && fromTourneeId !== 0) {
            await fetch(`/api/tournees/${fromTourneeId}/enlevements/${enlevementId}`, { method: 'DELETE' });
        }

        // Ajouter à la nouvelle tournée (si ce n'est pas "non assigné")
        if (toTourneeId && toTourneeId !== 0) {
            await fetch(`/api/tournees/${toTourneeId}/enlevements`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ enlevement_ids: [enlevementId] }),
            });

            // Mettre à jour l'ordre
            const cards = evt.to.querySelectorAll('.kanban-card');
            const orderedIds = Array.from(cards).map(c => parseInt(c.dataset.id));
            await fetch(`/api/tournees/${toTourneeId}/reorder`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ enlevement_ids: orderedIds }),
            });
        }

        // Recharger les données pour synchroniser les compteurs
        loadData();
    } catch (e) {
        console.error('Erreur drag-drop:', e);
        loadData(); // Recharger en cas d'erreur
    }
}


// ===== MODALS =====

function showNewTourneeModal() {
    document.getElementById('inputTourneeName').value = '';
    document.getElementById('selectChauffeur').value = '';
    document.getElementById('selectVehicule').value = '';
    showModal('modalNewTournee');
}


async function createTournee() {
    const nom = document.getElementById('inputTourneeName').value.trim();
    if (!nom) return;

    try {
        await fetch('/api/tournees', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                nom,
                date_tournee: currentDate,
                chauffeur_id: document.getElementById('selectChauffeur').value || null,
                vehicule_id: document.getElementById('selectVehicule').value || null,
            }),
        });
        hideModal('modalNewTournee');
        loadData();
    } catch (e) {
        console.error('Erreur création tournée:', e);
    }
}


function showEditTourneeModal(t) {
    document.getElementById('editTourneeId').value = t.id;
    document.getElementById('editTourneeName').value = t.nom;
    document.getElementById('editChauffeur').value = t.chauffeur_id || '';
    document.getElementById('editVehicule').value = t.vehicule_id || '';
    document.getElementById('editStatut').value = t.statut || 'brouillon';
    showModal('modalEditTournee');
}


async function saveEditTournee() {
    const id = document.getElementById('editTourneeId').value;
    try {
        await fetch(`/api/tournees/${id}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                nom: document.getElementById('editTourneeName').value.trim(),
                chauffeur_id: document.getElementById('editChauffeur').value || null,
                vehicule_id: document.getElementById('editVehicule').value || null,
                statut: document.getElementById('editStatut').value,
            }),
        });
        hideModal('modalEditTournee');
        loadData();
    } catch (e) {
        console.error('Erreur modification tournée:', e);
    }
}


async function deleteTournee() {
    const id = document.getElementById('editTourneeId').value;
    if (!confirm('Supprimer cette tournée ?')) return;
    try {
        await fetch(`/api/tournees/${id}`, { method: 'DELETE' });
        hideModal('modalEditTournee');
        loadData();
    } catch (e) {
        console.error('Erreur suppression tournée:', e);
    }
}


async function autoDistribuer() {
    try {
        const resp = await fetch('/api/tournees/auto-distribuer', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                date_tournee: currentDate,
                extraction_id: currentExtractionId,
            }),
        });
        const result = await resp.json();

        if (result.unknown_cities && result.unknown_cities.length > 0) {
            const list = document.getElementById('unknownCitiesList');
            list.innerHTML = result.unknown_cities.map(c =>
                `<div class="unknown-city-item">${escapeHtml(c)}</div>`
            ).join('');
            showModal('modalUnknownCities');
        }

        loadData();
    } catch (e) {
        console.error('Erreur auto-distribution:', e);
    }
}


async function toggleView(view) {
    document.querySelectorAll('.btn-view[data-view]').forEach(b => b.classList.remove('active'));
    document.querySelector(`.btn-view[data-view="${view}"]`).classList.add('active');

    document.getElementById('kanbanView').classList.add('hidden');
    document.getElementById('feuilleView').classList.add('hidden');
    document.getElementById('mapView').classList.add('hidden');

    if (view === 'kanban') {
        document.getElementById('kanbanView').classList.remove('hidden');
    } else if (view === 'feuille') {
        document.getElementById('feuilleView').classList.remove('hidden');
        renderFeuille();
    } else if (view === 'map') {
        document.getElementById('mapView').classList.remove('hidden');
        if (typeof initMap === 'function') {
            initMap();
            await updateMap(tournees, unassigned);
        }
    }
}


// ===== UTILS =====

function showModal(id) {
    document.getElementById(id).classList.remove('hidden');
}

function hideModal(id) {
    document.getElementById(id).classList.add('hidden');
}

function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}


// ===== FEUILLE DE ROUTE =====

function renderFeuille() {
    const container = document.getElementById('feuilleView');
    container.innerHTML = '';

    if (tournees.length === 0) {
        container.innerHTML = '<div class="text-center text-muted" style="padding:40px;">Aucune tournee pour cette date.</div>';
        return;
    }

    // Format date for header
    const dateObj = new Date(currentDate + 'T00:00:00');
    const dateStr = dateObj.toLocaleDateString('fr-FR', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' });

    tournees.forEach(t => {
        const chauffeurName = t.chauffeur_nom ? `${t.chauffeur_nom} ${t.chauffeur_prenom || ''}`.trim() : 'Non assigne';
        const vehiculeName = t.vehicule_immat || 'Non assigne';
        const vehiculeType = t.type_vehicule || '';
        const enlevements = t.enlevements || [];

        let totalPal = 0, totalPoids = 0, totalColis = 0;
        enlevements.forEach(e => {
            totalPal += (e.nb_palettes || 0);
            totalPoids += (e.poids_total || 0);
            totalColis += (e.nb_colis || 0);
        });

        const div = document.createElement('div');
        div.className = 'feuille-tournee';
        div.innerHTML = `
            <div class="feuille-header">
                <span class="feuille-header-title">${escapeHtml(t.nom)}</span>
                <div class="feuille-header-info">
                    <span>Date : <strong>${escapeHtml(dateStr)}</strong></span>
                    <span>Chauffeur : <strong>${escapeHtml(chauffeurName)}</strong></span>
                    <span>Camion : <strong>${escapeHtml(vehiculeName)}${vehiculeType ? ' (' + escapeHtml(vehiculeType) + ')' : ''}</strong></span>
                    <span>Tel : <strong>${escapeHtml(t.chauffeur_tel || '-')}</strong></span>
                </div>
                <div class="feuille-header-actions">
                    <button class="btn btn-sm btn-primary" onclick="showAddEnlevement(${t.id})">+ Enlevement</button>
                    <button class="btn btn-sm btn-secondary" onclick="printFeuille(${t.id})">Imprimer</button>
                </div>
            </div>
            <div class="feuille-table-wrapper">
                <table class="feuille-table" id="feuilleTable_${t.id}">
                    <thead>
                        <tr>
                            <th style="width:40px">N&deg;</th>
                            <th>REF</th>
                            <th>CLIENT</th>
                            <th>VILLE</th>
                            <th style="text-align:right">PALS</th>
                            <th>TYPE</th>
                            <th style="text-align:right">POIDS</th>
                            <th style="text-align:right">COLIS</th>
                            <th>DESTINATION</th>
                            <th>OBSERVATION</th>
                            <th style="width:60px"></th>
                        </tr>
                    </thead>
                    <tbody>
                        ${enlevements.map((e, idx) => feuilleRow(e, idx + 1, t.id)).join('')}
                    </tbody>
                    <tfoot>
                        <tr>
                            <td colspan="4" style="text-align:right">TOTAUX</td>
                            <td style="text-align:right">${totalPal}</td>
                            <td></td>
                            <td style="text-align:right">${totalPoids} kg</td>
                            <td style="text-align:right">${totalColis}</td>
                            <td></td>
                            <td></td>
                            <td></td>
                        </tr>
                    </tfoot>
                </table>
            </div>
        `;
        container.appendChild(div);
    });
}


function feuilleRow(e, num, tourneeId) {
    const livClass = (e.livraison || '').toLowerCase();
    const livCls = livClass === 'brevet' ? 'livraison-brevet'
        : livClass === 'transit' ? 'livraison-transit'
        : livClass === 'chevrolet' ? 'livraison-chevrolet' : '';
    const obs = e.observation || '';
    const obsClass = obs ? 'obs-text has-content' : 'obs-text';
    const obsDisplay = obs || 'Cliquer pour ajouter...';

    return `<tr data-enl-id="${e.id}" data-te-id="${e.te_id || ''}">
        <td class="td-num">${num}</td>
        <td class="td-ref">${escapeHtml(e.reference || '')}</td>
        <td>${escapeHtml(e.societe || '')}</td>
        <td>${escapeHtml(e.ville || '')}</td>
        <td class="td-right">${e.nb_palettes || 0}</td>
        <td>${escapeHtml(e.type_palettes || '')}</td>
        <td class="td-right">${e.poids_total || 0} kg</td>
        <td class="td-right">${e.nb_colis || 0}</td>
        <td class="td-livraison ${livCls}">${escapeHtml(e.livraison || '')}</td>
        <td class="td-observation">
            <span class="${obsClass}" data-te-id="${e.te_id || ''}" onclick="editObservation(this)">${escapeHtml(obsDisplay)}</span>
        </td>
        <td>
            <div class="feuille-row-actions">
                <button class="btn-edit-enl" title="Modifier" onclick='showEditEnlevement(${JSON.stringify({id:e.id, reference:e.reference||"", societe:e.societe||"", ville:e.ville||"", livraison:e.livraison||"", nb_palettes:e.nb_palettes||0, type_palettes:e.type_palettes||"", poids_total:e.poids_total||0, nb_colis:e.nb_colis||0}).replace(/'/g,"&#39;")})'>&#9998;</button>
            </div>
        </td>
    </tr>`;
}


function editObservation(el) {
    const teId = el.dataset.teId;
    if (!teId) return;
    const currentVal = el.classList.contains('has-content') ? el.textContent : '';
    const input = document.createElement('input');
    input.type = 'text';
    input.className = 'obs-input';
    input.value = currentVal;
    el.replaceWith(input);
    input.focus();

    const save = async () => {
        const val = input.value.trim();
        try {
            await fetch(`/api/tournee-enlevements/${teId}/observation`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ observation: val }),
            });
        } catch (err) {
            console.error('Erreur sauvegarde observation:', err);
        }
        const span = document.createElement('span');
        span.className = val ? 'obs-text has-content' : 'obs-text';
        span.dataset.teId = teId;
        span.setAttribute('onclick', 'editObservation(this)');
        span.textContent = val || 'Cliquer pour ajouter...';
        input.replaceWith(span);
    };

    input.addEventListener('blur', save);
    input.addEventListener('keydown', (ev) => {
        if (ev.key === 'Enter') input.blur();
        if (ev.key === 'Escape') {
            input.value = currentVal;
            input.blur();
        }
    });
}


// ===== ENLEVEMENT CREATE/EDIT MODAL =====

function showAddEnlevement(tourneeId) {
    document.getElementById('modalEnlevementTitle').textContent = 'Ajouter un enlevement';
    document.getElementById('enlEditId').value = '';
    document.getElementById('enlEditTourneeId').value = tourneeId;
    document.getElementById('enlRef').value = '';
    document.getElementById('enlSociete').value = '';
    document.getElementById('enlVille').value = '';
    document.getElementById('enlLivraison').value = 'BREVET';
    document.getElementById('enlPalettes').value = '0';
    document.getElementById('enlTypePal').value = 'VMF';
    document.getElementById('enlPoids').value = '0';
    document.getElementById('enlColis').value = '0';
    showModal('modalEnlevement');
}


function showEditEnlevement(data) {
    document.getElementById('modalEnlevementTitle').textContent = 'Modifier l\'enlevement';
    document.getElementById('enlEditId').value = data.id;
    document.getElementById('enlEditTourneeId').value = '';
    document.getElementById('enlRef').value = data.reference || '';
    document.getElementById('enlSociete').value = data.societe || '';
    document.getElementById('enlVille').value = data.ville || '';
    document.getElementById('enlLivraison').value = (data.livraison || 'BREVET').toUpperCase();
    document.getElementById('enlPalettes').value = data.nb_palettes || 0;
    document.getElementById('enlTypePal').value = data.type_palettes || 'VMF';
    document.getElementById('enlPoids').value = data.poids_total || 0;
    document.getElementById('enlColis').value = data.nb_colis || 0;
    showModal('modalEnlevement');
}


async function saveEnlevement() {
    const editId = document.getElementById('enlEditId').value;
    const tourneeId = document.getElementById('enlEditTourneeId').value;
    const payload = {
        reference: document.getElementById('enlRef').value.trim(),
        societe: document.getElementById('enlSociete').value.trim(),
        ville: document.getElementById('enlVille').value.trim(),
        livraison: document.getElementById('enlLivraison').value,
        nb_palettes: parseFloat(document.getElementById('enlPalettes').value) || 0,
        type_palettes: document.getElementById('enlTypePal').value,
        poids_total: parseFloat(document.getElementById('enlPoids').value) || 0,
        nb_colis: parseInt(document.getElementById('enlColis').value) || 0,
        date_enlevement: currentDate,
    };

    try {
        if (editId) {
            // Edit existing
            await fetch(`/api/enlevements/${editId}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload),
            });
        } else {
            // Create new + assign to tournee
            const resp = await fetch('/api/enlevements', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload),
            });
            const result = await resp.json();
            if (result.id && tourneeId) {
                await fetch(`/api/tournees/${tourneeId}/enlevements`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ enlevement_ids: [result.id] }),
                });
            }
        }
        hideModal('modalEnlevement');
        loadData();
        // Re-render feuille if visible
        if (!document.getElementById('feuilleView').classList.contains('hidden')) {
            setTimeout(renderFeuille, 200);
        }
    } catch (err) {
        console.error('Erreur sauvegarde enlevement:', err);
        alert('Erreur lors de la sauvegarde.');
    }
}


function printFeuille(tourneeId) {
    // Hide all tournees except the one to print, then print
    const allT = document.querySelectorAll('.feuille-tournee');
    const hidden = [];
    allT.forEach(el => {
        const table = el.querySelector(`#feuilleTable_${tourneeId}`);
        if (!table) {
            el.style.display = 'none';
            hidden.push(el);
        }
    });
    window.print();
    hidden.forEach(el => el.style.display = '');
}


function updateKanbanProgression() {
    // Utilise progressionData de carte.js (variable globale)
    if (typeof progressionData === 'undefined') return;

    tournees.forEach(t => {
        const el = document.getElementById(`progress_${t.id}`);
        if (!el) return;
        const prog = progressionData[t.id];
        if (prog) {
            const pct = Math.round(100 * prog.done / prog.total);
            el.innerHTML = `<span class="progress-badge">${prog.done}/${prog.total}</span>
                <span class="progress-bar-mini"><span class="progress-fill" style="width:${pct}%"></span></span>`;
        } else {
            el.innerHTML = '';
        }
    });
}
