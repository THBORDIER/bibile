/**
 * Bibile - Parametres
 * Configuration des connexions externes (DBI + Drakkar)
 */

document.addEventListener('DOMContentLoaded', () => {
    // Onglets
    document.querySelectorAll('.settings-tab').forEach(tab => {
        tab.addEventListener('click', () => switchTab(tab.dataset.tab));
    });

    // === CONNEXION ===
    document.getElementById('btnTestConnection').addEventListener('click', testConnection);
    document.getElementById('btnSaveDbConfig').addEventListener('click', saveDbConfig);
    document.getElementById('btnSyncNow').addEventListener('click', syncNow);
    document.getElementById('btnRefreshExtDrivers').addEventListener('click', loadExtVehicles);

    // === DRAKKAR ===
    document.getElementById('btnTestDrakkar').addEventListener('click', testDrakkar);
    document.getElementById('btnSaveDrakkar').addEventListener('click', saveDrakkar);

    // === MISE A JOUR ===
    document.getElementById('btnCheckUpdate').addEventListener('click', diagUpdate);

    // === RECHERCHE ===
    document.getElementById('searchExtVehicles').addEventListener('input', filterExtVehicles);

    // Charger les donnees
    loadDrakkarConfig();
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

        // Charger les selections actuelles
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

function filterExtVehicles() {
    const q = document.getElementById('searchExtVehicles').value.toLowerCase();
    document.querySelectorAll('#extDriversList .ext-driver-item').forEach(el => {
        const text = el.textContent.toLowerCase();
        el.style.display = text.includes(q) ? '' : 'none';
    });
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
        const resultDiv = document.getElementById('drakkarResult');
        if (!resp.ok) {
            resultDiv.classList.remove('hidden', 'alert-success', 'alert-info');
            resultDiv.classList.add('alert-danger');
            resultDiv.textContent = 'Erreur serveur lors de la sauvegarde.';
            return;
        }
        const data = await resp.json();
        if (data.ok) {
            resultDiv.classList.remove('hidden', 'alert-danger', 'alert-info');
            resultDiv.classList.add('alert-success');
            resultDiv.textContent = 'Configuration Drakkar enregistree.';
        }
    } catch (e) {
        console.error('Erreur sauvegarde config Drakkar:', e);
    }
}


// ===== MISE A JOUR =====

async function diagUpdate() {
    const container = document.getElementById('updateDiagResult');
    container.innerHTML = '<p class="text-muted">Verification en cours...</p>';

    try {
        const resp = await fetch('/api/update/debug');
        const data = await resp.json();

        if (data.error) {
            container.innerHTML = `
                <div class="alert alert-danger">Erreur: ${escapeHtml(data.error)} (${escapeHtml(data.type || '')})</div>`;
            return;
        }

        const hasUpdate = data.update_result != null;
        const statusClass = hasUpdate ? 'alert-success' : 'alert-info';
        const statusText = hasUpdate
            ? `Mise a jour disponible: v${data.update_result.version}`
            : 'Application a jour';

        container.innerHTML = `
            <div class="alert ${statusClass}">${statusText}</div>
            <table class="data-table" style="margin-top: 12px;">
                <tr><td><strong>Version locale</strong></td><td>${escapeHtml(data.local_version)}</td></tr>
                <tr><td><strong>Version GitHub</strong></td><td>${escapeHtml(data.remote_tag || 'N/A')}</td></tr>
                <tr><td><strong>Assets</strong></td><td>${(data.assets || []).map(a => escapeHtml(a)).join(', ') || 'Aucun'}</td></tr>
                <tr><td><strong>Cache MAJ</strong></td><td>${data.update_available_cache ? 'Oui' : 'Non'}</td></tr>
                <tr><td><strong>URL API</strong></td><td style="font-size: 0.85em;">${escapeHtml(data.github_url || '')}</td></tr>
            </table>`;
    } catch (e) {
        container.innerHTML = `<div class="alert alert-danger">Erreur reseau: ${escapeHtml(e.message)}</div>`;
    }
}


// ===== UTILS =====

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
