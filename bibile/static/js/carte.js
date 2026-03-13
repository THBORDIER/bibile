/**
 * Bibile - Vue Carte (Leaflet)
 * Affiche les enlèvements sur une carte OpenStreetMap
 */

let map = null;
let markersLayer = null;
let routesLayer = null;
let vehiclesLayer = null;
let mapInitialized = false;
let vehiclesVisible = false;
let vehicleRefreshInterval = null;

// Couleurs pour les tournées (cycle)
const TOUR_COLORS = [
    '#4493f8', '#3fb950', '#e3952d', '#f85149',
    '#a371f7', '#79c0ff', '#d29922', '#f778ba',
];


function initMap() {
    if (mapInitialized) return;

    const container = document.getElementById('mapContainer');
    if (!container) return;

    map = L.map('mapContainer').setView([47.02, 4.84], 9); // Centre Bourgogne (Beaune)

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; OpenStreetMap contributors',
        maxZoom: 18,
    }).addTo(map);

    markersLayer = L.layerGroup().addTo(map);
    routesLayer = L.layerGroup().addTo(map);
    vehiclesLayer = L.layerGroup().addTo(map);
    mapInitialized = true;

    // Fix rendering si le conteneur était hidden
    setTimeout(() => map.invalidateSize(), 100);
}


// ===== VEHICULES LIVE =====

const TRUCK_SVG_GREEN = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="28" height="28"><rect x="1" y="6" width="15" height="10" rx="2" fill="#3fb950" stroke="#fff" stroke-width="1"/><rect x="16" y="9" width="7" height="7" rx="1" fill="#2ea043" stroke="#fff" stroke-width="1"/><circle cx="6" cy="18" r="2" fill="#333" stroke="#fff" stroke-width="1"/><circle cx="19" cy="18" r="2" fill="#333" stroke="#fff" stroke-width="1"/></svg>`;
const TRUCK_SVG_GREY = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="28" height="28"><rect x="1" y="6" width="15" height="10" rx="2" fill="#6e7681" stroke="#fff" stroke-width="1"/><rect x="16" y="9" width="7" height="7" rx="1" fill="#545d68" stroke="#fff" stroke-width="1"/><circle cx="6" cy="18" r="2" fill="#333" stroke="#fff" stroke-width="1"/><circle cx="19" cy="18" r="2" fill="#333" stroke="#fff" stroke-width="1"/></svg>`;

function toggleVehicles() {
    vehiclesVisible = !vehiclesVisible;
    const btn = document.getElementById('btnToggleVehicles');
    if (btn) btn.classList.toggle('active', vehiclesVisible);

    if (vehiclesVisible) {
        fetchVehiclePositions();
        vehicleRefreshInterval = setInterval(fetchVehiclePositions, 30000);
    } else {
        if (vehicleRefreshInterval) clearInterval(vehicleRefreshInterval);
        vehicleRefreshInterval = null;
        if (vehiclesLayer) vehiclesLayer.clearLayers();
    }
}

async function fetchVehiclePositions() {
    if (!map || !vehiclesLayer) return;
    try {
        const resp = await fetch('/api/vehicles/positions');
        const data = await resp.json();
        if (data.erreur) {
            console.warn('Positions vehicules:', data.erreur);
            return;
        }
        const positions = data.positions || [];
        vehiclesLayer.clearLayers();

        positions.forEach(p => {
            if (!p.latitude || !p.longitude) return;

            const svg = p.isFresh ? TRUCK_SVG_GREEN : TRUCK_SVG_GREY;
            const icon = L.divIcon({
                className: 'truck-marker',
                html: svg,
                iconSize: [28, 28],
                iconAnchor: [14, 14],
            });

            const marker = L.marker([p.latitude, p.longitude], { icon });

            const speed = p.speed != null ? `${p.speed} km/h` : 'N/A';
            const driver = (p.firstName || p.lastName)
                ? `${p.firstName || ''} ${p.lastName || ''}`.trim()
                : 'Inconnu';
            const ts = p.gpsTimestampEpochMs
                ? new Date(p.gpsTimestampEpochMs).toLocaleString('fr-FR')
                : 'N/A';
            const freshLabel = p.isFresh
                ? '<span style="color:#3fb950">En ligne</span>'
                : '<span style="color:#6e7681">Hors ligne</span>';

            marker.bindPopup(`
                <div class="map-popup">
                    <strong>${escapeHtmlCarte(p.licensePlateNumber)}</strong> ${freshLabel}
                    <br>Chauffeur: ${escapeHtmlCarte(driver)}
                    <br>Vitesse: ${speed}
                    <br>MAJ: ${ts}
                </div>
            `);

            vehiclesLayer.addLayer(marker);
        });
    } catch (e) {
        console.error('Erreur positions vehicules:', e);
    }
}


function updateMap(tournees, unassigned) {
    if (!map || !markersLayer) return;

    markersLayer.clearLayers();
    routesLayer.clearLayers();

    const legendHtml = [];
    const bounds = [];

    // Afficher les enlèvements non assignés (gris)
    unassigned.forEach(e => {
        if (e.lat && e.lon) {
            const marker = createMarker(e, '#545d68', 'Non assigne');
            markersLayer.addLayer(marker);
            bounds.push([e.lat, e.lon]);
        }
    });

    if (unassigned.length > 0) {
        legendHtml.push(`<div class="legend-item"><span class="legend-dot" style="background:#545d68"></span>Non assigne (${unassigned.length})</div>`);
    }

    // Afficher chaque tournée
    tournees.forEach((t, idx) => {
        const color = TOUR_COLORS[idx % TOUR_COLORS.length];
        const points = [];

        (t.enlevements || []).forEach(e => {
            if (e.lat && e.lon) {
                const marker = createMarker(e, color, t.nom);
                markersLayer.addLayer(marker);
                points.push([e.lat, e.lon]);
                bounds.push([e.lat, e.lon]);
            }
        });

        // Tracer la polyligne du parcours
        if (points.length >= 2) {
            const polyline = L.polyline(points, {
                color: color,
                weight: 3,
                opacity: 0.7,
                dashArray: '5, 10',
            });
            routesLayer.addLayer(polyline);
        }

        const nbEnl = (t.enlevements || []).length;
        legendHtml.push(`<div class="legend-item"><span class="legend-dot" style="background:${color}"></span>${escapeHtmlCarte(t.nom)} (${nbEnl})</div>`);
    });

    // Ajuster la vue si on a des points
    if (bounds.length > 0) {
        map.fitBounds(bounds, { padding: [30, 30] });
    }

    // Mettre à jour la légende
    const legendEl = document.getElementById('mapLegend');
    if (legendEl) {
        legendEl.innerHTML = legendHtml.join('');
    }
}


function createMarker(e, color, tourName) {
    const icon = L.divIcon({
        className: 'custom-marker',
        html: `<div style="background:${color};width:12px;height:12px;border-radius:50%;border:2px solid #fff;box-shadow:0 1px 4px rgba(0,0,0,0.4)"></div>`,
        iconSize: [16, 16],
        iconAnchor: [8, 8],
    });

    const marker = L.marker([e.lat, e.lon], { icon });

    marker.bindPopup(`
        <div class="map-popup">
            <strong>#${e.num_enlevement}</strong> - ${escapeHtmlCarte(e.societe || '')}
            <br>${escapeHtmlCarte(e.ville || '')}
            <br>${e.nb_palettes || 0} ${e.type_palettes || ''} - ${e.poids_total || 0} kg
            <br><em>${escapeHtmlCarte(tourName)}</em>
        </div>
    `);

    return marker;
}


function escapeHtmlCarte(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}
