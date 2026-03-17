/**
 * facturation.js - Page de generation du fichier de facturation Hillebrand
 */

let factData = [];  // Lignes de facturation chargees

// --- Init ---
document.addEventListener('DOMContentLoaded', () => {
    const today = new Date().toISOString().slice(0, 10);
    document.getElementById('dateFacturation').value = today;

    document.getElementById('btnCharger').addEventListener('click', chargerDonnees);
    document.getElementById('btnGenerer').addEventListener('click', genererExcel);
});

// --- Charger les donnees ---
async function chargerDonnees() {
    const date = document.getElementById('dateFacturation').value;
    const ref = document.getElementById('refFacturation').value.trim();
    if (!date) return;

    const btn = document.getElementById('btnCharger');
    btn.disabled = true;
    btn.textContent = 'Chargement...';

    try {
        const url = `/api/facturation/charger?date=${date}` + (ref ? `&ref=${encodeURIComponent(ref)}` : '');
        const resp = await fetch(url);
        const data = await resp.json();
        if (data.erreur) {
            alert(data.erreur);
            return;
        }
        factData = data.lignes || [];
        renderTable();
        updateStats();

        document.getElementById('factEmpty').classList.add('hidden');
        document.getElementById('factResumeSection').classList.remove('hidden');
        document.getElementById('factTableSection').classList.remove('hidden');
        document.getElementById('btnGenerer').disabled = factData.length === 0;

        if (data.ref_suggestion && !ref) {
            document.getElementById('refFacturation').value = data.ref_suggestion;
        }
    } catch (e) {
        alert('Erreur: ' + e.message);
    } finally {
        btn.disabled = false;
        btn.textContent = 'Charger';
    }
}

// --- Rendu du tableau ---
function renderTable() {
    const tbody = document.getElementById('factTableBody');
    const tfoot = document.getElementById('factTableFoot');
    tbody.innerHTML = '';
    tfoot.innerHTML = '';

    factData.forEach((row, idx) => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td><input type="text" class="fact-input fact-input-sm" data-idx="${idx}" data-field="num_recep" value="${esc(row.num_recep)}"></td>
            <td><input type="text" class="fact-input fact-input-sm" data-idx="${idx}" data-field="origine" value="${esc(row.origine)}"></td>
            <td class="cell-expediteur">${esc(row.expediteur)}</td>
            <td><input type="text" class="fact-input fact-input-xs" data-idx="${idx}" data-field="dpt" value="${esc(row.dpt)}"></td>
            <td class="cell-dest ${destClass(row.destinataire)}">${esc(row.destinataire)}</td>
            <td><input type="text" class="fact-input fact-input-xs" data-idx="${idx}" data-field="cp_dest" value="${esc(row.cp_dest)}"></td>
            <td><input type="text" class="fact-input fact-input-sm" data-idx="${idx}" data-field="localite_dest" value="${esc(row.localite_dest)}"></td>
            <td><input type="text" class="fact-input fact-input-xs" data-idx="${idx}" data-field="dpt2" value="${esc(row.dpt2)}"></td>
            <td><input type="text" class="fact-input fact-input-xs" data-idx="${idx}" data-field="pec" value="${esc(row.pec)}"></td>
            <td><input type="text" class="fact-input fact-input-xs" data-idx="${idx}" data-field="liv" value="${esc(row.liv)}"></td>
            <td class="cell-tournee">${esc(row.tournee)}</td>
            <td><input type="number" class="fact-input fact-input-xs" data-idx="${idx}" data-field="paq" value="${row.paq}" min="0"></td>
            <td class="cell-num">${row.um}</td>
            <td class="cell-num">${row.colis}</td>
            <td class="cell-num">${row.poids}</td>
            <td><input type="number" class="fact-input fact-input-sm" data-idx="${idx}" data-field="ca_trs" value="${row.ca_trs || ''}" step="0.01" min="0"></td>
            <td class="cell-ref">${esc(row.ref_cli1)}</td>
            <td class="cell-ref">${esc(row.ref_cli2)}</td>
        `;
        tbody.appendChild(tr);
    });

    // Ecouter les changements
    tbody.querySelectorAll('.fact-input').forEach(input => {
        input.addEventListener('change', (e) => {
            const idx = parseInt(e.target.dataset.idx);
            const field = e.target.dataset.field;
            const val = e.target.type === 'number' ? parseFloat(e.target.value) || 0 : e.target.value;
            factData[idx][field] = val;
            updateStats();
        });
    });

    // Totaux en pied de tableau
    renderFooter();
}

function renderFooter() {
    const tfoot = document.getElementById('factTableFoot');
    const totPaq = factData.reduce((s, r) => s + (parseInt(r.paq) || 0), 0);
    const totUm = factData.reduce((s, r) => s + (parseInt(r.um) || 0), 0);
    const totColis = factData.reduce((s, r) => s + (parseInt(r.colis) || 0), 0);
    const totPoids = factData.reduce((s, r) => s + (parseInt(r.poids) || 0), 0);
    const totCa = factData.reduce((s, r) => s + (parseFloat(r.ca_trs) || 0), 0);

    tfoot.innerHTML = `
        <tr class="fact-total-row">
            <td colspan="11" class="text-right"><strong>TOTAUX</strong></td>
            <td class="cell-num"><strong>${totPaq}</strong></td>
            <td class="cell-num"><strong>${totUm}</strong></td>
            <td class="cell-num"><strong>${totColis}</strong></td>
            <td class="cell-num"><strong>${totPoids}</strong></td>
            <td class="cell-num"><strong>${totCa ? totCa.toFixed(2) : ''}</strong></td>
            <td colspan="2"></td>
        </tr>
    `;
}

function updateStats() {
    document.getElementById('statEnlevements').textContent = factData.length;
    document.getElementById('statPalettes').textContent = factData.reduce((s, r) => s + (parseInt(r.um) || 0), 0);
    document.getElementById('statColis').textContent = factData.reduce((s, r) => s + (parseInt(r.colis) || 0), 0);
    document.getElementById('statPoids').textContent = factData.reduce((s, r) => s + (parseInt(r.poids) || 0), 0);
    document.getElementById('statPaq').textContent = factData.reduce((s, r) => s + (parseInt(r.paq) || 0), 0);
    renderFooter();
}

// --- Generer Excel ---
async function genererExcel() {
    const date = document.getElementById('dateFacturation').value;
    const ref = document.getElementById('refFacturation').value.trim();
    if (!date || factData.length === 0) return;

    const btn = document.getElementById('btnGenerer');
    btn.disabled = true;
    btn.textContent = 'Generation...';

    try {
        const resp = await fetch('/api/facturation/generer', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ date, ref: ref, lignes: factData })
        });
        if (!resp.ok) {
            const err = await resp.json();
            alert(err.erreur || 'Erreur generation');
            return;
        }
        const blob = await resp.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `${ref || 'facturation'}_${date}.xlsx`;
        a.click();
        URL.revokeObjectURL(url);
    } catch (e) {
        alert('Erreur: ' + e.message);
    } finally {
        btn.disabled = false;
        btn.textContent = 'Generer Excel';
    }
}

// --- Helpers ---
function esc(val) {
    if (val === null || val === undefined) return '';
    return String(val).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function destClass(dest) {
    if (!dest) return '';
    const d = dest.toUpperCase();
    if (d.includes('TRANSIT')) return 'livraison-transit';
    if (d.includes('CHEVRO') || d.includes('STOCKAGE')) return 'livraison-chevrolet';
    if (d.includes('BREVET')) return 'livraison-brevet';
    return '';
}
