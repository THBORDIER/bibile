// Elements
const historyList = document.getElementById('historyList');
const emptyState = document.getElementById('emptyState');
const refreshBtn = document.getElementById('refreshBtn');
const searchInput = document.getElementById('searchInput');
const periodFilter = document.getElementById('periodFilter');

let allHistory = [];
let filteredHistory = [];

// Load history
async function loadHistory() {
    historyList.innerHTML = '<div class="loading">Chargement de l\'historique...</div>';
    emptyState.classList.add('hidden');

    try {
        const response = await fetch('/api/historique');

        if (!response.ok) {
            throw new Error('Erreur lors du chargement de l\'historique');
        }

        const data = await response.json();
        allHistory = data.historique || [];
        filteredHistory = [...allHistory];

        renderHistory();

    } catch (error) {
        console.error('Error:', error);
        historyList.innerHTML = `
            <div class="status-message error">
                Erreur de chargement de l'historique<br>
                <small>Le serveur est peut-etre en cours de demarrage. Cliquez sur "Actualiser" dans quelques secondes.</small>
            </div>
        `;
    }
}

// Render history
function renderHistory() {
    historyList.innerHTML = '';

    if (filteredHistory.length === 0) {
        emptyState.classList.remove('hidden');
        return;
    }

    emptyState.classList.add('hidden');

    filteredHistory.forEach(item => {
        const historyItem = createHistoryItem(item);
        historyList.appendChild(historyItem);
    });
}

// Create history item element
function createHistoryItem(item) {
    const div = document.createElement('div');
    div.className = 'history-item';

    const date = new Date(item.date);
    const dateStr = date.toLocaleDateString('fr-FR', {
        day: '2-digit',
        month: '2-digit',
        year: 'numeric'
    });
    const timeStr = date.toLocaleTimeString('fr-FR', {
        hour: '2-digit',
        minute: '2-digit'
    });

    div.innerHTML = `
        <div class="history-info">
            <div class="history-title">📄 ${item.nom_fichier}</div>
            <div class="history-meta">
                <span>📅 ${dateStr}</span>
                <span>🕐 ${timeStr}</span>
                <span>📊 ${item.nb_lignes} lignes</span>
            </div>
        </div>
        <div class="history-actions">
            <a href="/telecharger/${item.fichier}" class="btn-small btn-download">
                <span>⬇️</span>
                Télécharger
            </a>
            <a href="/log/${item.log_fichier}" class="btn-small btn-log" target="_blank">
                <span>📋</span>
                Log
            </a>
        </div>
    `;

    return div;
}

// Filter history by period
function filterByPeriod(period) {
    const now = new Date();
    const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());

    filteredHistory = allHistory.filter(item => {
        const itemDate = new Date(item.date);

        switch (period) {
            case 'today':
                return itemDate >= today;

            case 'week':
                const weekAgo = new Date(today);
                weekAgo.setDate(weekAgo.getDate() - 7);
                return itemDate >= weekAgo;

            case 'month':
                const monthAgo = new Date(today);
                monthAgo.setMonth(monthAgo.getMonth() - 1);
                return itemDate >= monthAgo;

            case 'all':
            default:
                return true;
        }
    });

    applySearch();
}

// Apply search filter
function applySearch() {
    const searchTerm = searchInput.value.toLowerCase();

    if (searchTerm) {
        filteredHistory = filteredHistory.filter(item => {
            return item.nom_fichier.toLowerCase().includes(searchTerm) ||
                   item.date.toLowerCase().includes(searchTerm);
        });
    }

    renderHistory();
}

// Event listeners
refreshBtn.addEventListener('click', () => {
    refreshBtn.disabled = true;
    refreshBtn.innerHTML = '<span class="btn-icon">⏳</span> Actualisation...';

    loadHistory().then(() => {
        refreshBtn.disabled = false;
        refreshBtn.innerHTML = '<span class="btn-icon">🔄</span> Actualiser';
    });
});

periodFilter.addEventListener('change', (e) => {
    filterByPeriod(e.target.value);
});

searchInput.addEventListener('input', () => {
    // Reset to full history before applying new search
    filterByPeriod(periodFilter.value);
});

// Initialize
loadHistory();
