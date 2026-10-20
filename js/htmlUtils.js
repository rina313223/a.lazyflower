// 共用的 HTML / 格式化小工具

const HTML_ESCAPES = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };

export function escapeHtml(text) {
    return String(text ?? '').replace(/[&<>"']/g, character => HTML_ESCAPES[character]);
}

export function formatDate(dateString) {
    const [year, month, day] = String(dateString || '').split('-');
    if (!year || !month || !day) return '';
    return `${year}.${month}.${day}`;
}

export function formatPriceRange(priceRange) {
    if (!priceRange) return '';
    if (priceRange.min === priceRange.max) return `$${priceRange.min}`;
    return `$${priceRange.min}–${priceRange.max}`;
}

export function toRegionAnchor(region) {
    return String(region || '').replace(/\s+/g, '-');
}

export function debounce(callback, waitMs) {
    let timerId = null;
    return (...args) => {
        clearTimeout(timerId);
        timerId = setTimeout(() => callback(...args), waitMs);
    };
}
