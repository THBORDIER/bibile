/**
 * Bibile - Page EDI
 * Comparaison messages EDI (Drakkar) vs extractions PDF
 */

let _lastCompareDate = null;

document.addEventListener('DOMContentLoaded', () => {
    const picker = document.getElementById('ediDatePicker');
    picker.value = new Date().toISOString().split('T')[0];

    document.getElementById('btnCompare').addEventListener('click', doCompare);
    document.getElementById('btnViewEdiRaw').addEventListener('click', viewEdiRaw);
    document.getElementById('btnExportExcel').addEventListener('click', exportExcel);
    document.getElementById('btnTodayEdi').addEventListener('click', () => {
        picker.value = new Date().toISOString().split('T')[0];
    });
    document.getElementById('btnPrevDayEdi').addEventListener('click', () => {
        const d = new Date(picker.value);
        d.setDate(d.getDate() - 1);
        picker.value = d.toISOString().split('T')[0];
    });
    document.getElementById('btnNextDayEdi').addEventListener('click', () => {
        const d = new Date(picker.value);
        d.setDate(d.getDate() + 1);
        picker.value = d.toISOString().split('T')[0];
    });
});


function showLoading(msg) {
    const el = document.getElementById('ediLoading');
    el.querySelector('.loading-text').textContent = msg || 'Chargement...';
    el.classList.remove('hidden');
}
function hideLoading() {
    document.getElementById('ediLoading').classList.add('hidden');
}


async function doCompare() {
    const date = document.getElementById('ediDatePicker').value;
    if (!date) return;

    _lastCompareDate = date;
    document.getElementById('ediRawCard').classList.add('hidden');
    document.getElementById('ediResultCard').classList.add('hidden');
    document.getElementById('ediStats').classList.add('hidden');
    showLoading('Comparaison EDI vs PDF en cours...');

    try {
        const resp = await fetch(`/api/drakkar/compare?date=${date}`);
        const data = await resp.json();

        hideLoading();

        if (data.erreur) {
            if (data.erreur.includes('non configuree')) {
                document.getElementById('ediNotConfigured').classList.remove('hidden');
            } else {
                alert('Erreur: ' + data.erreur);
            }
            return;
        }

        document.getElementById('ediNotConfigured').classList.add('hidden');

        // Stats
        const s = data.stats;
        document.getElementById('statPdf').textContent = s.total_pdf;
        document.getElementById('statEdi').textContent = s.total_edi;
        document.getElementById('statMatched').textContent = s.matched;
        document.getElementById('statEcarts').textContent = s.ecarts;
        document.getElementById('statPdfOnly').textContent = s.pdf_only;
        document.getElementById('statEdiOnly').textContent = s.edi_only;

        // Taux de correspondance avec couleur
        const pct = s.match_pct || 0;
        const pctEl = document.getElementById('statMatchPct');
        pctEl.textContent = pct + '%';
        const pctCard = pctEl.closest('.stat-card');
        pctCard.className = 'stat-card stat-pct';
        if (pct >= 80) pctCard.classList.add('pct-high');
        else if (pct >= 50) pctCard.classList.add('pct-mid');
        else pctCard.classList.add('pct-low');

        document.getElementById('ediStats').classList.remove('hidden');

        // Tableau
        const tbody = document.getElementById('ediResultBody');
        tbody.innerHTML = '';

        // Matches
        data.matches.forEach(m => {
            const statusClass = m.ok ? 'edi-match' : 'edi-ecart';
            const statusText = m.ok ? 'OK' : 'Ecart';
            const scoreClass = m.score >= 80 ? 'score-high' : m.score >= 60 ? 'score-mid' : 'score-low';
            const ecartTitle = m.ecarts && m.ecarts.length
                ? m.ecarts.map(e => `${e.champ}: PDF=${e.pdf}, EDI=${e.edi}`).join('\n')
                : '';
            const matchedBy = m.matched_by ? `<span class="matched-by">${esc(m.matched_by)}</span>` : '';
            tbody.innerHTML += `<tr class="${statusClass}" title="${esc(ecartTitle)}">
                <td><span class="edi-badge ${statusClass}">${statusText}</span></td>
                <td>${esc(m.num_enlevement)}</td>
                <td>${esc(m.societe)}</td>
                <td>${esc(m.edi_societe)}</td>
                <td><span class="score-badge ${scoreClass}">${m.score}%</span> ${matchedBy}</td>
                <td>${m.pdf.nb_palettes}</td>
                <td>${m.edi.total_palettes}</td>
                <td>${m.pdf.poids_total}</td>
                <td>${m.edi.total_poids}</td>
                <td>${m.pdf.nb_colis}</td>
                <td>${m.edi.total_colis}</td>
            </tr>`;
            // Sous-ligne ecarts si present
            if (m.ecarts && m.ecarts.length) {
                const details = m.ecarts.map(e =>
                    `<span class="ecart-detail">${e.champ}: PDF <b>${e.pdf}</b> / EDI <b>${e.edi}</b></span>`
                ).join(' ');
                tbody.innerHTML += `<tr class="ecart-detail-row">
                    <td colspan="11">${details}</td>
                </tr>`;
            }
        });

        // PDF seul
        data.pdf_only.forEach(p => {
            tbody.innerHTML += `<tr class="edi-pdf-only">
                <td><span class="edi-badge edi-pdf-only">PDF seul</span></td>
                <td>${esc(p.num_enlevement)}</td>
                <td>${esc(p.societe)}</td>
                <td>-</td>
                <td>-</td>
                <td>${p.nb_palettes}</td>
                <td>-</td>
                <td>${p.poids_total}</td>
                <td>-</td>
                <td>${p.nb_colis}</td>
                <td>-</td>
            </tr>`;
        });

        // EDI seul
        data.edi_only.forEach(e => {
            const ediInfo = [e.sold_by, e.delivery_city, e.delivery_name].filter(Boolean).join(' | ');
            tbody.innerHTML += `<tr class="edi-edi-only">
                <td><span class="edi-badge edi-edi-only">EDI seul</span></td>
                <td>${esc(e.shipment_id || e.transaction_ref)}</td>
                <td>-</td>
                <td title="${esc(ediInfo)}">${esc(e.sold_by)}</td>
                <td>-</td>
                <td>-</td>
                <td>${e.total_palettes}</td>
                <td>-</td>
                <td>${e.total_poids}</td>
                <td>-</td>
                <td>${e.total_colis}</td>
            </tr>`;
        });

        // Diagnostic: meilleurs scores rejetes (sous le seuil)
        if (data.best_rejected && data.best_rejected.length) {
            tbody.innerHTML += `<tr class="ecart-detail-row"><td colspan="11" style="text-align:center; color:#8b949e; padding: 8px;">
                <em>Meilleurs scores rejetes (sous le seuil) :</em>
                ${data.best_rejected.map(r => `${esc(r.pdf_societe)} / ${esc(r.edi_sold_by)} = ${r.score}pts (${esc(r.matched_by)})`).join(' | ')}
            </td></tr>`;
        }

        document.getElementById('ediResultCard').classList.remove('hidden');
        makeSortable(document.querySelector('#ediResultCard .data-table'));

    } catch (e) {
        hideLoading();
        alert('Erreur de comparaison: ' + e.message);
    }
}


async function viewEdiRaw() {
    const date = document.getElementById('ediDatePicker').value;
    if (!date) return;

    document.getElementById('ediResultCard').classList.add('hidden');
    document.getElementById('ediStats').classList.add('hidden');
    document.getElementById('ediRawCard').classList.add('hidden');
    showLoading('Chargement des EDI bruts...');

    try {
        const resp = await fetch(`/api/drakkar/edi?date=${date}`);
        const data = await resp.json();

        hideLoading();

        if (data.erreur) {
            if (data.erreur.includes('non configuree')) {
                document.getElementById('ediNotConfigured').classList.remove('hidden');
            } else {
                alert('Erreur: ' + data.erreur);
            }
            return;
        }

        document.getElementById('ediNotConfigured').classList.add('hidden');
        document.getElementById('ediRawCount').textContent = data.count;

        const tbody = document.getElementById('ediRawBody');
        tbody.innerHTML = '';

        (data.shipments || []).forEach(s => {
            tbody.innerHTML += `<tr>
                <td>${esc(s.shipment_id)}</td>
                <td>${esc(s.transaction_ref)}</td>
                <td>${esc(s.sold_by)}</td>
                <td>${esc(s.sold_by_city)}</td>
                <td>${s.total_colis}</td>
                <td>${s.total_palettes}</td>
                <td>${esc(s.type_palettes)}</td>
                <td>${s.poids_total}</td>
                <td>${esc(s.pickup_date)}</td>
                <td>${esc(s.delivery_name)}</td>
            </tr>`;
        });

        document.getElementById('ediRawCard').classList.remove('hidden');
        makeSortable(document.querySelector('#ediRawCard .data-table'));

    } catch (e) {
        hideLoading();
        alert('Erreur chargement EDI: ' + e.message);
    }
}


function exportExcel() {
    if (!_lastCompareDate) {
        alert('Lancez une comparaison d\'abord.');
        return;
    }
    window.open(`/api/drakkar/compare/export?date=${_lastCompareDate}`, '_blank');
}


function esc(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = String(str);
    return div.innerHTML;
}


// ===== Tri des colonnes par clic sur les en-tetes =====

let _sortState = {};

function makeSortable(table) {
    const headers = table.querySelectorAll('thead th');
    headers.forEach((th, idx) => {
        th.style.cursor = 'pointer';
        th.style.userSelect = 'none';
        th.addEventListener('click', () => sortTable(table, idx));
    });
}

function sortTable(table, colIdx) {
    const tbody = table.querySelector('tbody');
    const rows = Array.from(tbody.querySelectorAll('tr:not(.ecart-detail-row)'));
    if (!rows.length) return;

    const key = table.id + '_' + colIdx;
    const asc = _sortState[key] !== 'asc';
    _sortState[key] = asc ? 'asc' : 'desc';

    // Indicateur visuel
    table.querySelectorAll('thead th').forEach((th, i) => {
        th.textContent = th.textContent.replace(/ [▲▼]$/, '');
        if (i === colIdx) th.textContent += asc ? ' ▲' : ' ▼';
    });

    rows.sort((a, b) => {
        const cellA = a.cells[colIdx]?.textContent.trim() || '';
        const cellB = b.cells[colIdx]?.textContent.trim() || '';
        const numA = parseFloat(cellA);
        const numB = parseFloat(cellB);
        if (!isNaN(numA) && !isNaN(numB)) {
            return asc ? numA - numB : numB - numA;
        }
        return asc ? cellA.localeCompare(cellB, 'fr') : cellB.localeCompare(cellA, 'fr');
    });

    // Re-append rows, keeping ecart-detail-rows right after their parent
    rows.forEach(r => {
        tbody.appendChild(r);
        const next = r.nextElementSibling;
        if (next && next.classList.contains('ecart-detail-row')) {
            tbody.appendChild(next);
        }
    });
}
