// 將 posts.js 的原始貼文轉成畫面需要的結構（純函式，不碰 DOM，方便測試）

import { CATEGORY_RULES, DEFAULT_CATEGORY } from './config.js';

const TITLE_PATTERN = /^\s*✨️?\s*(.+)$/u;
const PRICE_PATTERN = /[／/]\s*\$\s*([\d,]+)/u;
const HASHTAG_PATTERN = /#([^\s#]+)/gu;
const DISTRICT_PATTERN = /[市縣](.{1,3}?[區鎮鄉市])/u;
const LABEL_PREFIX_PATTERN = /^[^：:]*[：:]\s*/u;

function valueAfterLabel(line) {
    return line.replace(LABEL_PREFIX_PATTERN, '').trim();
}

export function cleanPermalink(permalink) {
    let cleaned = String(permalink || '').split('?')[0].split('#')[0];
    if (cleaned && !cleaned.endsWith('/')) cleaned += '/';
    return cleaned;
}

export function extractShortcode(permalink) {
    const match = cleanPermalink(permalink).match(/\/(?:p|reel|tv)\/([^/]+)\//);
    return match ? match[1] : '';
}

function contentLines(content) {
    return String(content || '').split('\n').map(line => line.trim());
}

export function extractTitle(content) {
    const firstLine = contentLines(content).find(line => line.length > 0) || '';
    const match = firstLine.match(TITLE_PATTERN);
    const rawTitle = match ? match[1] : firstLine;
    const names = rawTitle.split('#').map(part => part.trim()).filter(Boolean);
    return names.length > 0 ? names[0] : rawTitle.trim();
}

export function extractMenuItems(content) {
    const lines = contentLines(content);
    const startIndex = lines.findIndex(line => line.startsWith('🍽'));
    if (startIndex === -1) return [];

    const menuItems = [];
    for (let i = startIndex; i < lines.length; i++) {
        const line = lines[i].replace(/^🍽\s*/u, '');
        if (!line || line.startsWith('➡') || line.startsWith('🏡')) break;
        const priceMatch = line.match(PRICE_PATTERN);
        const name = line.split(/[／/]/u)[0].trim();
        menuItems.push({ name, price: priceMatch ? Number(priceMatch[1].replace(/,/g, '')) : null });
    }
    return menuItems;
}

function extractLabeledValue(content, label) {
    const line = contentLines(content).find(text => text.includes(`${label}：`) || text.includes(`${label}:`));
    if (!line) return '';
    return valueAfterLabel(line);
}

export function extractAddress(content) {
    return extractLabeledValue(content, '地址');
}

export function extractPhone(content) {
    return extractLabeledValue(content, '電話');
}

// 營業時間可能寫在同一行，也可能在下一行起以「週X｜」列出
export function extractHours(content) {
    const lines = contentLines(content);
    const index = lines.findIndex(line => line.includes('營業時間'));
    if (index === -1) return [];

    const inline = valueAfterLabel(lines[index]);
    if (inline) return [inline];

    const hours = [];
    for (let i = index + 1; i < lines.length && lines[i] && !/^[☎✏🏡📍]/u.test(lines[i]); i++) {
        hours.push(lines[i]);
    }
    return hours;
}

export function extractReview(content) {
    const lines = String(content || '').split('\n');
    const startIndex = lines.findIndex(line => line.trim().startsWith('✏'));
    if (startIndex === -1) return '';

    const reviewLines = [];
    for (let i = startIndex; i < lines.length; i++) {
        if (/^\s*#/u.test(lines[i])) break;
        reviewLines.push(lines[i]);
    }
    return reviewLines.join('\n').replace(/^\s*✏️?/u, '').trim();
}

export function extractHashtags(content) {
    const lines = contentLines(content).filter(line => line.startsWith('#'));
    const tags = [];
    lines.forEach(line => {
        for (const match of line.matchAll(HASHTAG_PATTERN)) tags.push(match[1]);
    });
    return [...new Set(tags)];
}

export function extractDistrict(address) {
    const match = String(address || '').match(DISTRICT_PATTERN);
    return match ? match[1] : '';
}

function findCategoryRule(text) {
    const lowered = String(text || '').toLowerCase();
    return CATEGORY_RULES.find(candidate => candidate.keywords.some(keyword => lowered.includes(keyword.toLowerCase())));
}

// 依序比對多段文字（越前面越具代表性），第一段命中即採用
export function detectCategory(textsByPriority) {
    const texts = Array.isArray(textsByPriority) ? textsByPriority : [textsByPriority];
    for (const text of texts) {
        const rule = findCategoryRule(text);
        if (rule) return { key: rule.key, emoji: rule.emoji, label: rule.label };
    }
    return { ...DEFAULT_CATEGORY };
}

export function computePriceRange(menuItems) {
    const prices = menuItems.map(menuItem => menuItem.price).filter(price => Number.isFinite(price));
    if (prices.length === 0) return null;
    return { min: Math.min(...prices), max: Math.max(...prices) };
}

function hasCoordinates(rawPost) {
    return Number.isFinite(rawPost.lat) && Number.isFinite(rawPost.lng);
}

export function parsePost(rawPost) {
    const content = rawPost.content || '';
    const title = extractTitle(content);
    const menuItems = extractMenuItems(content);
    const address = extractAddress(content);
    const shortcode = extractShortcode(rawPost.permalink);

    return Object.freeze({
        id: shortcode || `${rawPost.date}-${title}`,
        region: rawPost.region || '',
        regionShort: String(rawPost.region || '').split(' ')[0],
        permalink: cleanPermalink(rawPost.permalink),
        date: rawPost.date || '',
        mapUrl: rawPost.map || '',
        coordinates: hasCoordinates(rawPost) ? Object.freeze([rawPost.lat, rawPost.lng]) : null,
        content,
        title,
        menuItems: Object.freeze(menuItems),
        priceRange: computePriceRange(menuItems),
        address,
        district: extractDistrict(address),
        phone: extractPhone(content),
        hours: Object.freeze(extractHours(content)),
        review: extractReview(content),
        hashtags: Object.freeze(extractHashtags(content)),
        category: detectCategory([
            title,
            menuItems[0]?.name,
            menuItems.map(menuItem => menuItem.name).join(' '),
            content
        ])
    });
}

export function parsePosts(rawPosts) {
    return (rawPosts || []).map(parsePost);
}
