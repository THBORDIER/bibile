// ===== Statistiques Page =====

const periodFilter = document.getElementById('periodFilter');
const customDates = document.getElementById('customDates');
const dateDebut = document.getElementById('dateDebut');
const dateFin = document.getElementById('dateFin');
const refreshBtn = document.getElementById('refreshStats');
const emptyStats = document.getElementById('emptyStats');
const filterLivraison = document.getElementById('filterLivraison');
const filterZone = document.getElementById('filterZone');

// Chart instances
let charts = {};

// Color palette matching the app theme
const COLORS = {
    BREVET: '#4493f8',
    TRANSIT: '#e3952d',
    CHEVROLET: '#3fb950',
    HILLEBRAND: '#a371f7',
    default: '#8b949e',
};

const PALETTE_COLORS = {
    'EURO': '#4493f8',
    'VMF': '#e3952d',
    'HALF PALLET': '#3fb950',
    'PART PALLET': '#a371f7',
    'LOOSE LOADED': '#f85149',
};

function getColor(label) {
    return COLORS[label] || COLORS.default;
}

function getPaletteColor(label) {
    return PALETTE_COLORS[label] || '#8b949e';
}

// Chart.js global defaults for dark theme
Chart.defaults.color = '#8b949e';
Chart.defaults.borderColor = '#30363d';
Chart.defaults.font.family = 'system-ui, -apple-system, sans-serif';

// ===== Date range calculation =====
function getDateRange() {
    const period = periodFilter.value;
    const now = new Date();

    if (period === 'custom') {
        return { date_debut: dateDebut.value, date_fin: dateFin.value };
    }

    if (period === 'all') return {};

    let start;
    if (period === 'today') {
        start = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    } else if (period === 'week') {
        const day = now.getDay() || 7;
        start = new Date(now);
        start.setDate(now.getDate() - day + 1);
        start.setHours(0, 0, 0, 0);
    } else if (period === 'month') {
        start = new Date(now.getFullYear(), now.getMonth(), 1);
    }

    const fmt = d => d.toISOString().split('T')[0];
    return { date_debut: fmt(start), date_fin: fmt(now) };
}

// ===== Build query params =====
function buildParams() {
    const range = getDateRange();
    const params = new URLSearchParams();
    if (range.date_debut) params.set('date_debut', range.date_debut);
    if (range.date_fin) params.set('date_fin', range.date_fin);
    if (filterLivraison.value) params.set('livraison', filterLivraison.value);
    if (filterZone.value) params.set('zone', filterZone.value);
    return params;
}

// ===== Fetch stats =====
async function loadStats() {
    const params = buildParams();

    try {
        const resp = await fetch(`/api/statistiques?${params}`);
        const data = await resp.json();

        if (data.erreur) {
            emptyStats.querySelector('p').textContent = 'Erreur: ' + data.erreur;
            emptyStats.classList.remove('hidden');
            document.querySelectorAll('.charts-row, .chart-wide, .stats-totaux').forEach(el => {
                el.classList.add('hidden');
            });
            return;
        }

        const hasData = data.totaux.nb_enlevements > 0;
        emptyStats.classList.toggle('hidden', hasData);
        document.querySelectorAll('.charts-row, .chart-wide, .stats-totaux').forEach(el => {
            el.classList.toggle('hidden', !hasData);
        });

        if (!hasData) return;

        updateTotaux(data.totaux);
        renderChartLivraison(data.par_livraison);
        renderChartPalettes(data.par_type_palette);
        renderChartPoids(data.poids_par_livraison);
        renderChartColis(data.colis_par_livraison);
        renderChartEvolution(data.evolution_quotidienne);
        renderChartSocietes(data.top_societes);

        // Peupler le filtre livraison (une seule fois)
        if (filterLivraison.options.length <= 1 && data.livraisons) {
            data.livraisons.forEach(l => {
                const opt = document.createElement('option');
                opt.value = l;
                opt.textContent = l;
                filterLivraison.appendChild(opt);
            });
        }

    } catch (err) {
        console.error('Erreur chargement stats:', err);
        emptyStats.querySelector('p').textContent = 'Erreur de chargement des statistiques.';
        emptyStats.classList.remove('hidden');
    }
}

// ===== Update totaux cards =====
function updateTotaux(totaux) {
    document.getElementById('totalExtractions').textContent = totaux.nb_extractions.toLocaleString();
    document.getElementById('totalEnlevements').textContent = totaux.nb_enlevements.toLocaleString();
    document.getElementById('totalPalettes').textContent = Math.round(totaux.palettes_total).toLocaleString();
    document.getElementById('totalPoids').textContent = Math.round(totaux.poids_total).toLocaleString();
    document.getElementById('totalColis').textContent = Math.round(totaux.colis_total).toLocaleString();
}

// ===== Chart helpers =====
function destroyChart(name) {
    if (charts[name]) {
        charts[name].destroy();
        charts[name] = null;
    }
}

function createDoughnut(canvasId, chartName, labels, values, colorFn) {
    destroyChart(chartName);
    const ctx = document.getElementById(canvasId).getContext('2d');
    charts[chartName] = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: labels,
            datasets: [{
                data: values,
                backgroundColor: labels.map(colorFn),
                borderColor: '#161b22',
                borderWidth: 2,
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: { padding: 16, usePointStyle: true, pointStyleWidth: 10 }
                }
            },
            cutout: '55%',
        }
    });
}

function createBar(canvasId, chartName, labels, values, colorFn, horizontal) {
    destroyChart(chartName);
    const ctx = document.getElementById(canvasId).getContext('2d');
    charts[chartName] = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                data: values,
                backgroundColor: labels.map(colorFn),
                borderRadius: 4,
                maxBarThickness: 50,
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            indexAxis: horizontal ? 'y' : 'x',
            plugins: { legend: { display: false } },
            scales: {
                x: { grid: { color: '#21262d' } },
                y: { grid: { color: '#21262d' } }
            }
        }
    });
}

// ===== Render individual charts =====
function renderChartLivraison(data) {
    const labels = Object.keys(data);
    const values = Object.values(data);
    createDoughnut('chartLivraison', 'livraison', labels, values, getColor);
}

function renderChartPalettes(data) {
    const labels = Object.keys(data);
    const values = Object.values(data);
    createDoughnut('chartPalettes', 'palettes', labels, values, getPaletteColor);
}

function renderChartPoids(data) {
    const labels = Object.keys(data);
    const values = Object.values(data);
    createBar('chartPoids', 'poids', labels, values, getColor, false);
}

function renderChartColis(data) {
    const labels = Object.keys(data);
    const values = Object.values(data);
    createBar('chartColis', 'colis', labels, values, getColor, false);
}

function renderChartEvolution(data) {
    destroyChart('evolution');
    const ctx = document.getElementById('chartEvolution').getContext('2d');

    const labels = data.map(d => {
        const date = new Date(d.date + 'T00:00:00');
        return date.toLocaleDateString('fr-FR', { day: '2-digit', month: 'short' });
    });

    charts['evolution'] = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [
                {
                    label: 'Enlevements',
                    data: data.map(d => d.nb_enlevements),
                    borderColor: '#4493f8',
                    backgroundColor: 'rgba(68, 147, 248, 0.1)',
                    fill: true,
                    tension: 0.3,
                    pointRadius: 4,
                    pointHoverRadius: 6,
                },
                {
                    label: 'Palettes',
                    data: data.map(d => d.nb_palettes),
                    borderColor: '#3fb950',
                    backgroundColor: 'rgba(63, 185, 80, 0.1)',
                    fill: true,
                    tension: 0.3,
                    pointRadius: 4,
                    pointHoverRadius: 6,
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'top',
                    labels: { usePointStyle: true, pointStyleWidth: 10, padding: 16 }
                }
            },
            scales: {
                x: { grid: { color: '#21262d' } },
                y: { grid: { color: '#21262d' }, beginAtZero: true }
            }
        }
    });
}

function renderChartSocietes(data) {
    const labels = data.map(d => d.societe);
    const values = data.map(d => d.nb);
    createBar('chartSocietes', 'societes', labels, values, () => '#4493f8', true);
}

// ===== Export PDF =====
function exportPdf() {
    window.print();
}

// ===== Export Excel =====
function exportExcel() {
    const params = buildParams();
    window.open(`/api/statistiques/export?${params}`, '_blank');
}

// ===== Load zones for filter =====
async function loadZones() {
    try {
        const resp = await fetch('/api/zones');
        const data = await resp.json();
        if (data.zones) {
            data.zones.forEach(z => {
                const opt = document.createElement('option');
                opt.value = z.nom;
                opt.textContent = z.nom;
                filterZone.appendChild(opt);
            });
        }
    } catch (e) {
        console.warn('Zones non disponibles:', e.message);
    }
}

// ===== Event listeners =====
periodFilter.addEventListener('change', () => {
    customDates.classList.toggle('hidden', periodFilter.value !== 'custom');
    if (periodFilter.value !== 'custom') {
        loadStats();
    }
});

refreshBtn.addEventListener('click', loadStats);
dateDebut.addEventListener('change', loadStats);
dateFin.addEventListener('change', loadStats);
filterLivraison.addEventListener('change', loadStats);
filterZone.addEventListener('change', loadStats);
document.getElementById('btnExportPdf').addEventListener('click', exportPdf);
document.getElementById('btnExportExcel').addEventListener('click', exportExcel);

// Init
loadZones();
loadStats();
