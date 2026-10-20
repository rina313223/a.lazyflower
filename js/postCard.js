// 文章卡片的 HTML 樣板（只產生字串，不綁事件）

import { escapeHtml, formatDate, formatPriceRange } from './htmlUtils.js';

const MAX_MENU_PREVIEW = 3;

function renderMenuPreview(menuItems) {
    if (menuItems.length === 0) return '';
    const previewItems = menuItems.slice(0, MAX_MENU_PREVIEW).map(menuItem => `
        <li><span class="menu-name">${escapeHtml(menuItem.name)}</span>${menuItem.price !== null ? `<span class="menu-price">$${menuItem.price}</span>` : ''}</li>`).join('');
    const moreCount = menuItems.length - MAX_MENU_PREVIEW;
    return `<ul class="card-menu">${previewItems}${moreCount > 0 ? `<li class="menu-more">+${moreCount} 道</li>` : ''}</ul>`;
}

export function renderPostCard(post) {
    const location = [post.regionShort, post.district].filter(Boolean).join('・');
    const priceText = formatPriceRange(post.priceRange);

    return `
    <article class="post-card" data-post-id="${escapeHtml(post.id)}" data-category="${post.category.key}" tabindex="0" role="button" aria-label="查看 ${escapeHtml(post.title)} 詳情">
        <div class="card-cover">
            <span class="card-emoji" aria-hidden="true">${post.category.emoji}</span>
            <span class="card-category">${escapeHtml(post.category.label)}</span>
            ${post.coordinates ? '<span class="card-pin" title="已標記在地圖上" aria-label="已標記在地圖上">📍</span>' : ''}
        </div>
        <div class="card-body">
            <h3 class="card-title">${escapeHtml(post.title)}</h3>
            <p class="card-meta">
                <span>${escapeHtml(location)}</span>
                ${priceText ? `<span class="card-price">${priceText}</span>` : ''}
            </p>
            ${renderMenuPreview(post.menuItems)}
            ${post.review ? `<p class="card-review">${escapeHtml(post.review)}</p>` : ''}
            <footer class="card-footer">
                <time datetime="${escapeHtml(post.date)}">${formatDate(post.date)}</time>
                <span class="card-more">看詳情 →</span>
            </footer>
        </div>
    </article>`;
}
