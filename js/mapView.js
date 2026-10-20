// 文章地圖（Leaflet）。所有狀態封裝在 createMapView 的 closure 內。

import { MAP_DEFAULT_VIEW, MAP_TILE_URL, MAP_TILE_ATTRIBUTION } from './config.js';
import { escapeHtml, formatPriceRange } from './htmlUtils.js';
import { prefersReducedMotion } from './animations.js';

const DUPLICATE_OFFSET_DEGREES = 0.00018;
const FOCUS_ZOOM = 16;

function coordinateKey([lat, lng]) {
    return `${lat.toFixed(5)},${lng.toFixed(5)}`;
}

// 同一地點（例如同棟百貨）的多篇文章，繞圓稍微錯開避免 marker 重疊
export function spreadDuplicateCoordinates(posts) {
    const groups = new Map();
    posts.forEach(post => {
        const key = coordinateKey(post.coordinates);
        if (!groups.has(key)) groups.set(key, []);
        groups.get(key).push(post);
    });

    const positions = new Map();
    groups.forEach(groupPosts => {
        groupPosts.forEach((post, index) => {
            if (groupPosts.length === 1) {
                positions.set(post.id, post.coordinates);
                return;
            }
            const angle = (2 * Math.PI * index) / groupPosts.length;
            positions.set(post.id, [
                post.coordinates[0] + DUPLICATE_OFFSET_DEGREES * Math.sin(angle),
                post.coordinates[1] + DUPLICATE_OFFSET_DEGREES * Math.cos(angle)
            ]);
        });
    });
    return positions;
}

function createPinIcon(post) {
    return window.L.divIcon({
        className: 'map-pin-wrapper',
        html: `<div class="map-pin" data-category="${post.category.key}"><span>${post.category.emoji}</span></div>`,
        iconSize: [38, 44],
        iconAnchor: [19, 42],
        popupAnchor: [0, -38]
    });
}

function renderPopup(post) {
    const priceText = formatPriceRange(post.priceRange);
    return `
        <div class="map-popup">
            <strong>${escapeHtml(post.title)}</strong>
            <span class="map-popup-meta">${escapeHtml([post.regionShort, post.district].filter(Boolean).join('・'))}${priceText ? `・${priceText}` : ''}</span>
            <div class="map-popup-actions">
                <button type="button" class="btn btn-primary btn-sm" data-open-post="${escapeHtml(post.id)}">看詳情</button>
                ${post.mapUrl ? `<a class="btn btn-ghost btn-sm" href="${escapeHtml(post.mapUrl)}" target="_blank" rel="noopener">導航</a>` : ''}
            </div>
        </div>`;
}

export function createMapView(container, { onMarkerSelect, onOpenPost }) {
    if (!window.L) {
        container.innerHTML = '<p class="map-fallback">地圖載入失敗，請稍後再試 🙏</p>';
        return createNoopMapView();
    }

    const map = window.L.map(container, { zoomControl: false, scrollWheelZoom: true })
        .setView(MAP_DEFAULT_VIEW.center, MAP_DEFAULT_VIEW.zoom);
    window.L.control.zoom({ position: 'bottomright' }).addTo(map);
    window.L.tileLayer(MAP_TILE_URL, { attribution: MAP_TILE_ATTRIBUTION, maxZoom: 19 }).addTo(map);

    const markersById = new Map();
    const markerLayer = window.L.layerGroup().addTo(map);
    const animate = !prefersReducedMotion();

    container.addEventListener('click', event => {
        const openButton = event.target.closest('[data-open-post]');
        if (openButton) onOpenPost(openButton.dataset.openPost);
    });

    function setPosts(posts) {
        markerLayer.clearLayers();
        markersById.clear();
        const mappablePosts = posts.filter(post => post.coordinates);
        const positions = spreadDuplicateCoordinates(mappablePosts);

        mappablePosts.forEach(post => {
            const marker = window.L.marker(positions.get(post.id), { icon: createPinIcon(post), riseOnHover: true, title: post.title })
                .bindPopup(renderPopup(post), { closeButton: false, className: 'lf-popup' })
                .on('click', () => onMarkerSelect(post.id));
            marker.addTo(markerLayer);
            markersById.set(post.id, marker);
        });
        return mappablePosts.length;
    }

    // 地圖被隱藏時（手機列表模式）尺寸為 0，此時移動視角會算出 NaN
    function isRendered() {
        const size = map.getSize();
        return size.x > 0 && size.y > 0;
    }

    function fitToVisible() {
        if (!isRendered()) return;
        const latLngs = [...markersById.values()].map(marker => marker.getLatLng());
        if (latLngs.length === 0) {
            map.flyTo(MAP_DEFAULT_VIEW.center, MAP_DEFAULT_VIEW.zoom, { animate });
            return;
        }
        if (latLngs.length === 1) {
            map.flyTo(latLngs[0], 15, { animate, duration: 0.8 });
            return;
        }
        map.flyToBounds(window.L.latLngBounds(latLngs), { padding: [48, 48], maxZoom: 15, animate, duration: 0.9 });
    }

    function setHighlighted(postId, isHighlighted) {
        const marker = markersById.get(postId);
        const pinElement = marker?.getElement()?.querySelector('.map-pin');
        if (!pinElement) return;
        pinElement.classList.toggle('is-active', isHighlighted);
        marker.setZIndexOffset(isHighlighted ? 1000 : 0);
    }

    function focusPost(postId) {
        const marker = markersById.get(postId);
        if (!marker || !isRendered()) return false;
        map.flyTo(marker.getLatLng(), Math.max(map.getZoom(), FOCUS_ZOOM), { animate, duration: 0.8 });
        marker.openPopup();
        return true;
    }

    return {
        setPosts,
        fitToVisible,
        focusPost,
        highlight: postId => setHighlighted(postId, true),
        unhighlight: postId => setHighlighted(postId, false),
        refreshSize: () => map.invalidateSize()
    };
}

function createNoopMapView() {
    const noop = () => {};
    return { setPosts: () => 0, fitToVisible: noop, focusPost: () => false, highlight: noop, unhighlight: noop, refreshSize: noop };
}
