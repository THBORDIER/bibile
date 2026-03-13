/**
 * Bibile - Vue Carte (Leaflet)
 * Affiche les enlèvements sur une carte OpenStreetMap
 */

let map = null;
let markersLayer = null;
let routesLayer = null;
let mapInitialized = false;

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
    mapInitialized = true;

    // Fix rendering si le conteneur était hidden
    setTimeout(() => map.invalidateSize(), 100);
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
