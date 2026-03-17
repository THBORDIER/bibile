/**
 * Bibile - Vue Carte (Leaflet)
 * Affiche les enlèvements, itinéraires routiers (OSRM) et véhicules live
 */

let map = null;
let markersLayer = null;
let routesLayer = null;
let vehiclesLayer = null;
let mapInitialized = false;
let vehicleRefreshInterval = null;
let vehiclePositions = [];  // Positions live des véhicules (partagé avec tournees.js)
let routeCache = {};        // Cache des itinéraires OSRM par clé de points
let routeInfos = {};        // Distance/durée par tournée id

// Dépôt Transport Brevet (départ et arrivée de chaque tournée)
const DEPOT = [46.78106, 4.79925];

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

    // Charger les véhicules automatiquement + refresh toutes les 30s
    fetchVehiclePositions();
    vehicleRefreshInterval = setInterval(fetchVehiclePositions, 30000);
}


// ===== VEHICULES LIVE =====

const TRUCK_SVG_BLUE = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="32" height="32"><rect x="1" y="6" width="15" height="10" rx="2" fill="#4493f8" stroke="#fff" stroke-width="1.5"/><rect x="16" y="9" width="7" height="7" rx="1" fill="#316dca" stroke="#fff" stroke-width="1.5"/><circle cx="6" cy="18" r="2" fill="#222" stroke="#fff" stroke-width="1"/><circle cx="19" cy="18" r="2" fill="#222" stroke="#fff" stroke-width="1"/></svg>`;
const TRUCK_SVG_GREY = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="20" height="20"><rect x="1" y="6" width="15" height="10" rx="2" fill="#6e7681" stroke="#ccc" stroke-width="0.8"/><rect x="16" y="9" width="7" height="7" rx="1" fill="#545d68" stroke="#ccc" stroke-width="0.8"/><circle cx="6" cy="18" r="2" fill="#333" stroke="#ccc" stroke-width="0.8"/><circle cx="19" cy="18" r="2" fill="#333" stroke="#ccc" stroke-width="0.8"/></svg>`;


async function fetchVehiclePositions() {
    if (!map || !vehiclesLayer) return;
    try {
        const resp = await fetch('/api/vehicles/positions');
        const data = await resp.json();
        if (data.erreur) {
            console.warn('Positions vehicules:', data.erreur);
            return;
        }
        vehiclePositions = data.positions || [];
        vehiclesLayer.clearLayers();

        vehiclePositions.forEach(p => {
            if (p.lat == null || p.lon == null) return;

            const isSelected = p.selected;
            const svg = isSelected ? TRUCK_SVG_BLUE : TRUCK_SVG_GREY;
            const size = isSelected ? 32 : 20;
            const icon = L.divIcon({
                className: 'truck-marker',
                html: svg,
                iconSize: [size, size],
                iconAnchor: [size / 2, size / 2],
            });

            const marker = L.marker([p.lat, p.lon], {
                icon,
                zIndexOffset: isSelected ? 1000 : 0,
            });

            const speed = p.speed != null ? `${p.speed} km/h` : 'N/A';
            const driver = p.chauffeur || 'Inconnu';
            const freshLabel = p.isFresh
                ? '<span style="color:#3fb950">En ligne</span>'
                : '<span style="color:#6e7681">Hors ligne</span>';
            const selectedLabel = isSelected ? '' : ' <span style="color:#6e7681">(non suivi)</span>';

            marker.bindPopup(`
                <div class="map-popup">
                    <strong>${escapeHtmlCarte(p.immatriculation)}</strong> ${freshLabel}${selectedLabel}
                    <br>Chauffeur: ${escapeHtmlCarte(driver)}
                    <br>Vitesse: ${speed}
                    <br>MAJ: ${escapeHtmlCarte(p.timestamp || 'N/A')}
                </div>
            `);

            vehiclesLayer.addLayer(marker);
        });

        // Recalculer la progression après refresh des positions
        if (typeof _lastTournees !== 'undefined' && _lastTournees) {
            estimerProgression(_lastTournees);
        }
    } catch (e) {
        console.error('Erreur positions vehicules:', e);
    }
}


// ===== DISTANCE HAVERSINE =====

function haversineKm(lat1, lon1, lat2, lon2) {
    const R = 6371;
    const dLat = (lat2 - lat1) * Math.PI / 180;
    const dLon = (lon2 - lon1) * Math.PI / 180;
    const a = Math.sin(dLat / 2) ** 2 +
              Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
              Math.sin(dLon / 2) ** 2;
    return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}


// ===== ITINERAIRES OSRM =====

async function getRoute(points) {
    // points = [[lat, lon], ...] — OSRM attend lon,lat
    if (points.length < 2) return null;

    const cacheKey = points.map(p => `${p[0].toFixed(4)},${p[1].toFixed(4)}`).join('|');
    if (routeCache[cacheKey]) return routeCache[cacheKey];

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 5000);
    try {
        const coords = points.map(p => `${p[1]},${p[0]}`).join(';');
        const url = `https://router.project-osrm.org/route/v1/driving/${coords}?overview=full&geometries=geojson`;
        const resp = await fetch(url, { signal: controller.signal });
        clearTimeout(timeoutId);
        const data = await resp.json();
        if (data.code === 'Ok' && data.routes && data.routes.length > 0) {
            const route = {
                geometry: data.routes[0].geometry,
                distance: data.routes[0].distance,  // metres
                duration: data.routes[0].duration,   // secondes
            };
            routeCache[cacheKey] = route;
            return route;
        }
    } catch (e) {
        clearTimeout(timeoutId);
        console.warn('OSRM fallback polyline:', e.message);
    }
    return null;
}

function formatDuration(seconds) {
    const h = Math.floor(seconds / 3600);
    const m = Math.round((seconds % 3600) / 60);
    if (h > 0) return `${h}h${m.toString().padStart(2, '0')}`;
    return `${m} min`;
}

function formatDistance(meters) {
    return (meters / 1000).toFixed(0) + ' km';
}


// ===== ESTIMATION DE PROGRESSION =====

let _lastTournees = null;
let progressionData = {};  // { tourneeId: { done: N, total: N, currentIdx: N } }

function estimerProgression(tournees) {
    progressionData = {};
    if (!vehiclePositions || vehiclePositions.length === 0) return;

    tournees.forEach(t => {
        if (!t.vehicule_id || !t.enlevements || t.enlevements.length === 0) return;

        // Trouver la position du véhicule de cette tournée
        const vPos = vehiclePositions.find(v =>
            v.vehicule_id === t.vehicule_id || v.immatriculation === t.vehicule_immat
        );
        if (!vPos || vPos.lat == null || vPos.lon == null) return;
        if (!vPos.isFresh) return; // Véhicule hors ligne → pas d'estimation

        const enls = t.enlevements.filter(e => e.lat && e.lon);
        if (enls.length === 0) return;

        // Calculer la distance du véhicule à chaque enlèvement
        let minDist = Infinity;
        let closestIdx = 0;
        enls.forEach((e, idx) => {
            const d = haversineKm(vPos.lat, vPos.lon, e.lat, e.lon);
            if (d < minDist) {
                minDist = d;
                closestIdx = idx;
            }
        });

        // Seuil : si le camion est à > 50km de tous les points, pas d'estimation
        if (minDist > 50) return;

        // Tous avant closestIdx = fait, closestIdx = en cours, après = en attente
        // Si le camion est à < 2km du point, considérer ce point comme "fait" aussi
        const doneCount = minDist < 2 ? closestIdx + 1 : closestIdx;

        progressionData[t.id] = {
            done: doneCount,
            total: enls.length,
            currentIdx: closestIdx,
            minDist: minDist,
        };
    });

    // Mettre à jour les marqueurs sur la carte
    updateMarkerStyles(tournees);
    // Mettre à jour la légende
    updateLegendProgression(tournees);
}

function updateMarkerStyles(tournees) {
    if (!markersLayer) return;

    markersLayer.eachLayer(marker => {
        if (!marker._enlId) return;

        tournees.forEach(t => {
            const prog = progressionData[t.id];
            if (!prog) return;

            const enls = (t.enlevements || []).filter(e => e.lat && e.lon);
            enls.forEach((e, idx) => {
                if (e.id === marker._enlId) {
                    let statusClass = '';
                    if (idx < prog.done) statusClass = 'marker-done';
                    else if (idx === prog.currentIdx) statusClass = 'marker-current';

                    if (statusClass) {
                        const el = marker.getElement();
                        if (el) el.classList.add(statusClass);
                    }
                }
            });
        });
    });
}

function updateLegendProgression(tournees) {
    const legendEl = document.getElementById('mapLegend');
    if (!legendEl) return;

    const items = legendEl.querySelectorAll('.legend-item');
    items.forEach(item => {
        const text = item.textContent;
        tournees.forEach(t => {
            const prog = progressionData[t.id];
            if (prog && text.includes(t.nom)) {
                const existingProg = item.querySelector('.legend-progress');
                if (existingProg) existingProg.remove();
                const span = document.createElement('span');
                span.className = 'legend-progress';
                span.textContent = ` ${prog.done}/${prog.total}`;
                item.appendChild(span);
            }
        });
    });
}


// ===== MAP UPDATE =====

async function updateMap(tournees, unassigned) {
    if (!map || !markersLayer) return;

    _lastTournees = tournees;
    markersLayer.clearLayers();
    routesLayer.clearLayers();
    routeInfos = {};

    const legendHtml = [];
    const bounds = [];

    // Marqueur du dépôt Transport Brevet
    const depotIcon = L.divIcon({
        className: 'depot-marker',
        html: '<div style="background:#fff;border:3px solid #f85149;border-radius:50%;width:18px;height:18px;display:flex;align-items:center;justify-content:center;font-weight:bold;font-size:11px;color:#f85149;">D</div>',
        iconSize: [18, 18],
        iconAnchor: [9, 9],
    });
    const depotMarker = L.marker(DEPOT, { icon: depotIcon })
        .bindPopup('<strong>Dépôt Transport Brevet</strong><br>Départ / Arrivée');
    markersLayer.addLayer(depotMarker);
    bounds.push(DEPOT);

    // Enlèvements non assignés (gris)
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

    // Chaque tournée
    const routePromises = [];

    tournees.forEach((t, idx) => {
        const color = t.couleur || TOUR_COLORS[idx % TOUR_COLORS.length];
        const points = [];

        (t.enlevements || []).forEach(e => {
            if (e.lat && e.lon) {
                const marker = createMarker(e, color, t.nom);
                markersLayer.addLayer(marker);
                points.push([e.lat, e.lon]);
                bounds.push([e.lat, e.lon]);
            }
        });

        // Itinéraire OSRM (async) avec fallback polyline
        // Dépôt en départ et arrivée
        const routePoints = points.length > 0 ? [DEPOT, ...points, DEPOT] : [];
        if (routePoints.length >= 3) {
            const promise = getRoute(routePoints).then(route => {
                if (route) {
                    // GeoJSON coordinates sont [lon, lat], Leaflet les gère
                    const layer = L.geoJSON(route.geometry, {
                        style: { color, weight: 4, opacity: 0.8 },
                    });
                    routesLayer.addLayer(layer);
                    routeInfos[t.id] = {
                        distance: route.distance,
                        duration: route.duration,
                    };
                } else {
                    // Fallback polyline droite
                    const polyline = L.polyline(routePoints, {
                        color, weight: 3, opacity: 0.7, dashArray: '5, 10',
                    });
                    routesLayer.addLayer(polyline);
                }
            });
            routePromises.push(promise);
        }

        const nbEnl = (t.enlevements || []).length;
        const statut = t.statut || 'brouillon';
        const statutBadge = `<span class="legend-statut legend-statut-${statut}">${statut}</span>`;
        legendHtml.push(`<div class="legend-item" data-tournee-id="${t.id}"><span class="legend-dot" style="background:${color}"></span>${escapeHtmlCarte(t.nom)} (${nbEnl}) ${statutBadge}<span class="legend-route-info" id="routeInfo_${t.id}"></span></div>`);
    });

    // Ajuster la vue
    if (bounds.length > 0) {
        map.fitBounds(bounds, { padding: [30, 30] });
    }

    // Légende
    const legendEl = document.getElementById('mapLegend');
    if (legendEl) {
        legendEl.innerHTML = legendHtml.join('');
    }

    // Attendre les routes OSRM puis mettre à jour la légende avec distances/durées
    await Promise.all(routePromises);
    tournees.forEach(t => {
        const info = routeInfos[t.id];
        const el = document.getElementById(`routeInfo_${t.id}`);
        if (info && el) {
            el.textContent = ` — ${formatDistance(info.distance)}, ~${formatDuration(info.duration)}`;
        }
    });

    // Estimer la progression si des positions véhicules sont disponibles
    estimerProgression(tournees);
}


function createMarker(e, color, tourName) {
    const icon = L.divIcon({
        className: 'custom-marker',
        html: `<div class="marker-dot" style="background:${color}"></div>`,
        iconSize: [16, 16],
        iconAnchor: [8, 8],
    });

    const marker = L.marker([e.lat, e.lon], { icon });
    marker._enlId = e.id;

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
