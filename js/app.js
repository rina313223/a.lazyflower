// 進入點：組合各模組、管理畫面狀態（狀態僅存在此模組內）

import { IG_POSTS } from '../posts.js';
import { REGIONS, SORT_OPTIONS, SEARCH_DEBOUNCE_MS } from './config.js';
import { parsePosts } from './postParser.js';
import { applyFilters, countByRegion } from './filters.js';
import { renderPostCard } from './postCard.js';
import { createMapView } from './mapView.js';
import { createDetailDrawer } from './detailDrawer.js';
import { createRevealObserver, flipReorder, countUp, pulse } from './animations.js';
import { renderVisitCount } from './visitCounter.js';
import { enableContentProtection } from './contentProtection.js';
import { debounce, escapeHtml, toRegionAnchor } from './htmlUtils.js';

const POST_HASH_PREFIX = '#post=';
const DESKTOP_QUERY = window.matchMedia('(min-width: 1024px)');

const posts = parsePosts(IG_POSTS);
const postsById = new Map(posts.map(post => [post.id, post]));
const filterState = { query: '', region: '', sort: SORT_OPTIONS.NEWEST };

const elements = {
    grid: document.getElementById('post-grid'),
    chips: document.getElementById('region-chips'),
    search: document.getElementById('search-input'),
    searchClear: document.getElementById('search-clear'),
    sort: document.getElementById('sort-select'),
    resultCount: document.getElementById('result-count'),
    emptyState: document.getElementById('empty-state'),
    emptyQuery: document.getElementById('empty-query'),
    resetButton: document.getElementById('reset-filters'),
    viewToggle: document.getElementById('view-toggle'),
    backToTop: document.getElementById('back-to-top'),
    stickyBar: document.getElementById('sticky-bar')
};

const revealObserver = createRevealObserver();
const mapView = createMapView(document.getElementById('map'), {
    onMarkerSelect: postId => focusCard(postId),
    onOpenPost: postId => openPost(postId)
});
const drawer = createDetailDrawer(document.getElementById('detail-drawer'), {
    onClose: () => history.replaceState(null, '', location.pathname + location.search)
});

// ---------- 渲染 ----------

function renderAllCards() {
    elements.grid.innerHTML = posts.map(renderPostCard).join('');
    revealObserver.observe([...elements.grid.children]);
}

function renderRegionChips() {
    const counts = countByRegion(posts);
    const regionsWithPosts = REGIONS.filter(region => counts[region]);
    const chipButtons = [{ value: '', label: '全部', count: posts.length }]
        .concat(regionsWithPosts.map(region => ({ value: region, label: region.split(' ')[0], count: counts[region] })));

    elements.chips.innerHTML = chipButtons.map(chip => `
        <button type="button" class="chip" role="tab" data-region="${escapeHtml(chip.value)}" aria-selected="${chip.value === filterState.region}">
            ${escapeHtml(chip.label)}<span class="chip-count">${chip.count}</span>
        </button>`).join('');
}

function updateChipSelection() {
    elements.chips.querySelectorAll('.chip').forEach(chip => {
        chip.setAttribute('aria-selected', String(chip.dataset.region === filterState.region));
    });
}

function cardElement(postId) {
    return elements.grid.querySelector(`[data-post-id="${CSS.escape(postId)}"]`);
}

function updateResultSummary(visiblePosts) {
    const mappedCount = visiblePosts.filter(post => post.coordinates).length;
    elements.resultCount.textContent = `${visiblePosts.length} 篇食記・${mappedCount} 個地點`;
    const isEmpty = visiblePosts.length === 0;
    elements.emptyState.hidden = !isEmpty;
    elements.emptyQuery.textContent = filterState.query || filterState.region.split(' ')[0];
}

function applyCurrentFilters() {
    const visiblePosts = applyFilters(posts, filterState);
    const visibleIds = new Set(visiblePosts.map(post => post.id));

    flipReorder(elements.grid, () => {
        [...elements.grid.children].forEach(card => { card.hidden = !visibleIds.has(card.dataset.postId); });
        visiblePosts.forEach(post => elements.grid.appendChild(cardElement(post.id)));
    });
    visiblePosts.forEach(post => cardElement(post.id).classList.add('is-visible'));

    mapView.setPosts(visiblePosts);
    mapView.fitToVisible();
    updateResultSummary(visiblePosts);
}

// ---------- 互動 ----------

function setRegion(region) {
    filterState.region = region;
    updateChipSelection();
    applyCurrentFilters();
    const anchor = region ? `#${toRegionAnchor(region)}` : '';
    history.replaceState(null, '', location.pathname + location.search + anchor);
}

function focusCard(postId) {
    const card = cardElement(postId);
    if (!card || card.hidden) return;
    elements.grid.querySelectorAll('.post-card.is-selected').forEach(selected => selected.classList.remove('is-selected'));
    card.classList.add('is-selected');
    if (isMapOnlyView()) return;
    card.scrollIntoView({ behavior: 'smooth', block: 'center' });
    pulse(card);
}

function openPost(postId) {
    const post = postsById.get(postId);
    if (!post) return;
    drawer.open(post);
    if (!isMapOnlyView()) mapView.focusPost(postId);
    history.replaceState(null, '', `${location.pathname}${location.search}${POST_HASH_PREFIX}${encodeURIComponent(postId)}`);
}

function isMapOnlyView() {
    return !DESKTOP_QUERY.matches && document.body.dataset.view === 'map';
}

function setMobileView(view) {
    document.body.dataset.view = view;
    elements.viewToggle.setAttribute('aria-pressed', String(view === 'map'));
    elements.viewToggle.querySelector('.view-toggle-label').textContent = view === 'map' ? '列表' : '地圖';
    elements.viewToggle.querySelector('.view-toggle-icon').textContent = view === 'map' ? '☰' : '🗺️';
    requestAnimationFrame(() => {
        mapView.refreshSize();
        mapView.fitToVisible();
    });
}

function bindCardEvents() {
    elements.grid.addEventListener('click', event => {
        const card = event.target.closest('.post-card');
        if (card) openPost(card.dataset.postId);
    });
    elements.grid.addEventListener('keydown', event => {
        const card = event.target.closest('.post-card');
        if (card && (event.key === 'Enter' || event.key === ' ')) {
            event.preventDefault();
            openPost(card.dataset.postId);
        }
    });
    elements.grid.addEventListener('pointerover', event => {
        const card = event.target.closest('.post-card');
        if (card && !card.contains(event.relatedTarget)) mapView.highlight(card.dataset.postId);
    });
    elements.grid.addEventListener('pointerout', event => {
        const card = event.target.closest('.post-card');
        if (card && !card.contains(event.relatedTarget)) mapView.unhighlight(card.dataset.postId);
    });
}

function bindToolbarEvents() {
    elements.chips.addEventListener('click', event => {
        const chip = event.target.closest('.chip');
        if (chip) setRegion(chip.dataset.region);
    });

    const runSearch = debounce(() => applyCurrentFilters(), SEARCH_DEBOUNCE_MS);
    elements.search.addEventListener('input', () => {
        filterState.query = elements.search.value.trim();
        elements.searchClear.hidden = !filterState.query;
        runSearch();
    });
    elements.searchClear.addEventListener('click', () => {
        elements.search.value = '';
        filterState.query = '';
        elements.searchClear.hidden = true;
        elements.search.focus();
        applyCurrentFilters();
    });
    elements.sort.addEventListener('change', () => {
        filterState.sort = elements.sort.value;
        applyCurrentFilters();
    });
    elements.resetButton.addEventListener('click', () => {
        elements.search.value = '';
        filterState.query = '';
        elements.searchClear.hidden = true;
        setRegion('');
    });
    elements.viewToggle.addEventListener('click', () => {
        setMobileView(document.body.dataset.view === 'map' ? 'list' : 'map');
    });
    DESKTOP_QUERY.addEventListener('change', () => requestAnimationFrame(() => mapView.refreshSize()));
}

function bindScrollEffects() {
    let ticking = false;
    window.addEventListener('scroll', () => {
        if (ticking) return;
        ticking = true;
        requestAnimationFrame(() => {
            const scrolled = window.scrollY > 120;
            document.body.classList.toggle('is-scrolled', scrolled);
            elements.backToTop.classList.toggle('is-shown', window.scrollY > 600);
            ticking = false;
        });
    }, { passive: true });
    elements.backToTop.addEventListener('click', () => window.scrollTo({ top: 0, behavior: 'smooth' }));

    // 讓地圖欄的 sticky 位置跟著頂部工具列高度
    const syncStickyOffset = () => document.documentElement.style.setProperty('--sticky-offset', `${elements.stickyBar.offsetHeight}px`);
    new ResizeObserver(syncStickyOffset).observe(elements.stickyBar);
}

// 相容舊版錨點（#台中-Taichung）與新版文章連結（#post=ID）
function restoreFromHash() {
    const hash = decodeURIComponent(location.hash);
    if (hash.startsWith(POST_HASH_PREFIX)) {
        const postId = hash.slice(POST_HASH_PREFIX.length);
        if (postsById.has(postId)) setTimeout(() => openPost(postId), 400);
        return;
    }
    const region = REGIONS.find(candidate => `#${toRegionAnchor(candidate)}` === hash);
    if (region) filterState.region = region;
}

function renderStats() {
    const counts = countByRegion(posts);
    countUp(document.getElementById('stat-posts'), posts.length);
    countUp(document.getElementById('stat-regions'), Object.keys(counts).length);
    renderVisitCount(document.getElementById('stat-visits'));
}

function init() {
    restoreFromHash();
    renderRegionChips();
    renderAllCards();
    bindCardEvents();
    bindToolbarEvents();
    bindScrollEffects();
    enableContentProtection();
    setMobileView('list');
    applyCurrentFilters();
    renderStats();
    document.body.classList.add('is-ready');
}

init();
