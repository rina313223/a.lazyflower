// 篩選與排序（純函式，輸入文章陣列與條件，回傳新陣列）

import { SORT_OPTIONS } from './config.js';

function toTimestamp(dateString) {
    const [year, month, day] = String(dateString || '').split('-').map(Number);
    return new Date(year || 0, (month || 1) - 1, day || 1).getTime();
}

function buildSearchText(post) {
    return [
        post.title, post.region, post.address, post.district, post.content,
        post.menuItems.map(menuItem => menuItem.name).join(' '),
        post.hashtags.join(' ')
    ].join(' ').toLowerCase();
}

export function matchesQuery(post, query) {
    const keywords = String(query || '').trim().toLowerCase().split(/\s+/).filter(Boolean);
    if (keywords.length === 0) return true;
    const searchText = buildSearchText(post);
    return keywords.every(keyword => searchText.includes(keyword));
}

export function matchesRegion(post, region) {
    return !region || post.region === region;
}

export function sortPosts(posts, sortOption) {
    const direction = sortOption === SORT_OPTIONS.OLDEST ? 1 : -1;
    return [...posts].sort((a, b) => direction * (toTimestamp(a.date) - toTimestamp(b.date)));
}

export function applyFilters(posts, { query = '', region = '', sort = SORT_OPTIONS.NEWEST } = {}) {
    const matched = posts.filter(post => matchesRegion(post, region) && matchesQuery(post, query));
    return sortPosts(matched, sort);
}

export function countByRegion(posts) {
    return posts.reduce((counts, post) => {
        counts[post.region] = (counts[post.region] || 0) + 1;
        return counts;
    }, {});
}
