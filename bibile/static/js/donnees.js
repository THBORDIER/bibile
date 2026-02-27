// State management
let allData = [];           // Original data from API
let filteredData = [];      // After filters applied
let currentFile = '';       // Currently selected file

// DOM Elements
const fileSelect = document.getElementById('fileSelect');
const statsSection = document.getElementById('statsSection');
const filtersCard = document.getElementById('filtersCard');
const tableCard = document.getElementById('tableCard');
const emptyState = document.getElementById('emptyState');
const loadingState = document.getElementById('loadingState');
const tableBody = document.getElementById('tableBody');
const rowCount = document.getElementById('rowCount');

// Stat elements
const statBrevet = document.getElementById('statBrevet');
const statTransit = document.getElementById('statTransit');
const statChevrolet = document.getElementById('statChevrolet');

// Filter elements
const filterLivraison = document.getElementById('filterLivraison');
const filterVille = document.getElementById('filterVille');
const filterEnlevement = document.getElementById('filterEnlevement');
const filterReference = document.getElementById('filterReference');
const filterSearch = document.getElementById('filterSearch');
const clearFilters = document.getElementById('clearFilters');

// Initialize: Load file list
async function loadFileList() {
    try {
        const response = await fetch('/api/historique');
        if (!response.ok) throw new Error('Erreur chargement historique');

        const data = await response.json();
        const files = data.historique || [];

        // Populate file select
        fileSelect.innerHTML = '<option value="">-- Choisir un fichier --</option>';
        files.forEach(file => {
            const option = document.createElement('option');
            option.value = file.fichier;
            option.textContent = `${file.nom_fichier} (${file.nb_lignes} lignes)`;
            fileSelect.appendChild(option);
        });

    } catch (error) {
        console.error('Error loading files:', error);
    }
}

// Load Excel data when file is selected
async function loadExcelData(filename) {
    if (!filename) {
        resetView();
        return;
    }

    // Show loading
    emptyState.classList.add('hidden');
    statsSection.classList.add('hidden');
    filtersCard.classList.add('hidden');
    tableCard.classList.add('hidden');
    loadingState.classList.remove('hidden');

    try {
        const response = await fetch(`/api/donnees/${filename}`);
        if (!response.ok) throw new Error('Erreur chargement données');

        const result = await response.json();
        allData = result.donnees || [];
        filteredData = [...allData];
        currentFile = filename;

        // Hide loading, show content
        loadingState.classList.add('hidden');
        statsSection.classList.remove('hidden');
        filtersCard.classList.remove('hidden');
        tableCard.classList.remove('hidden');

        // Populate ville filter options
        populateVilleFilter();

        // Calculate statistics
        updateStatistics();

        // Render table
        renderTable();

    } catch (error) {
        console.error('Error loading data:', error);
        loadingState.classList.remove('hidden');
        loadingState.innerHTML = `
            <div class="status-message error">
                Erreur de chargement des données
            </div>
        `;
    }
}

// Populate ville filter with unique cities
function populateVilleFilter() {
    const villes = [...new Set(allData.map(row => row['VILLE']).filter(v => v))];
    villes.sort();

    filterVille.innerHTML = '<option value="">Toutes</option>';
    villes.forEach(ville => {
        const option = document.createElement('option');
        option.value = ville;
        option.textContent = ville;
        filterVille.appendChild(option);
    });
}

// Calculate and update statistics
function updateStatistics() {
    const stats = {
        BREVET: 0,
        TRANSIT: 0,
        CHEVROLET: 0
    };

    filteredData.forEach(row => {
        const livraison = row['LIVRAISON ASSOCIÉE'] || '';
        const nbPalettes = parseFloat(row['NOMBRE DE PALETTES']) || 0;

        if (livraison.includes('BREVET')) stats.BREVET += nbPalettes;
        else if (livraison.includes('TRANSIT')) stats.TRANSIT += nbPalettes;
        else if (livraison.includes('CHEVROLET')) stats.CHEVROLET += nbPalettes;
    });

    statBrevet.textContent = stats.BREVET;
    statTransit.textContent = stats.TRANSIT;
    statChevrolet.textContent = stats.CHEVROLET;
}

// Render table with current filtered data
function renderTable() {
    tableBody.innerHTML = '';

    filteredData.forEach(row => {
        const tr = document.createElement('tr');

        // Determine color class based on livraison
        const livraison = row['LIVRAISON ASSOCIÉE'] || '';
        let colorClass = '';
        if (livraison.includes('BREVET')) colorClass = 'row-brevet';
        else if (livraison.includes('TRANSIT')) colorClass = 'row-transit';
        else if (livraison.includes('CHEVROLET')) colorClass = 'row-chevrolet';

        tr.className = colorClass;

        // Create cells for all 10 columns
        const cells = [
            row['N° ENLÈVEMENT'] || '',
            row['NOTRE RÉFÉRENCE'] || '',
            row['SOCIÉTÉ / DOMAINE'] || '',
            row['VILLE'] || '',
            row['NOMBRE DE PALETTES'] || '',
            row['TYPE DE PALETTES'] || '',
            row['POIDS TOTAL (KG)'] || '',
            row['NOMBRE DE COLIS'] || '',
            row['LIVRAISON ASSOCIÉE'] || '',
            row['TÉLÉPHONE'] || ''
        ];

        cells.forEach(cellData => {
            const td = document.createElement('td');
            td.textContent = cellData;
            tr.appendChild(td);
        });

        tableBody.appendChild(tr);
    });

    rowCount.textContent = `${filteredData.length} ligne${filteredData.length > 1 ? 's' : ''}`;
}

// Apply all filters
function applyFilters() {
    filteredData = allData.filter(row => {
        // Livraison filter
        const livraisonVal = filterLivraison.value;
        if (livraisonVal) {
            const rowLivraison = row['LIVRAISON ASSOCIÉE'] || '';
            if (!rowLivraison.includes(livraisonVal)) return false;
        }

        // Ville filter
        const villeVal = filterVille.value;
        if (villeVal) {
            if (row['VILLE'] !== villeVal) return false;
        }

        // N° Enlèvement filter
        const enlevementVal = filterEnlevement.value.trim();
        if (enlevementVal) {
            const rowEnlevement = String(row['N° ENLÈVEMENT'] || '');
            if (!rowEnlevement.includes(enlevementVal)) return false;
        }

        // Reference filter
        const referenceVal = filterReference.value.trim().toLowerCase();
        if (referenceVal) {
            const rowRef = String(row['NOTRE RÉFÉRENCE'] || '').toLowerCase();
            if (!rowRef.includes(referenceVal)) return false;
        }

        // Global search
        const searchVal = filterSearch.value.trim().toLowerCase();
        if (searchVal) {
            const rowStr = Object.values(row).join(' ').toLowerCase();
            if (!rowStr.includes(searchVal)) return false;
        }

        return true;
    });

    updateStatistics();
    renderTable();
}

// Reset all filters
function resetFilters() {
    filterLivraison.value = '';
    filterVille.value = '';
    filterEnlevement.value = '';
    filterReference.value = '';
    filterSearch.value = '';
    applyFilters();
}

// Reset view to empty state
function resetView() {
    emptyState.classList.remove('hidden');
    statsSection.classList.add('hidden');
    filtersCard.classList.add('hidden');
    tableCard.classList.add('hidden');
    loadingState.classList.add('hidden');
    allData = [];
    filteredData = [];
}

// Debounce helper for input filters
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// Event listeners
fileSelect.addEventListener('change', (e) => {
    loadExcelData(e.target.value);
});

filterLivraison.addEventListener('change', applyFilters);
filterVille.addEventListener('change', applyFilters);
filterEnlevement.addEventListener('input', debounce(applyFilters, 300));
filterReference.addEventListener('input', debounce(applyFilters, 300));
filterSearch.addEventListener('input', debounce(applyFilters, 300));
clearFilters.addEventListener('click', resetFilters);

// Initialize on page load
loadFileList();
