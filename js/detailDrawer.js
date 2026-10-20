// 文章詳情抽屜：桌機由右側滑入、手機為底部面板。IG 內嵌只在這裡載入。

import { escapeHtml, formatDate, formatPriceRange } from './htmlUtils.js';
import { renderInstagramPlaceholder, processInstagramEmbeds } from './instagramEmbed.js';

function renderInfoRow(icon, label, valueHtml) {
    if (!valueHtml) return '';
    return `<div class="info-row"><dt><span aria-hidden="true">${icon}</span>${label}</dt><dd>${valueHtml}</dd></div>`;
}

function renderMenuList(menuItems) {
    if (menuItems.length === 0) return '';
    return `
        <section class="drawer-section">
            <h3>點了什麼</h3>
            <ul class="menu-list">
                ${menuItems.map(menuItem => menuItem.price !== null
                    ? `<li><span>${escapeHtml(menuItem.name)}</span><i></i><b>$${menuItem.price}</b></li>`
                    : `<li class="menu-note"><span>${escapeHtml(menuItem.name)}</span></li>`).join('')}
            </ul>
        </section>`;
}

function renderDrawerContent(post) {
    const priceText = formatPriceRange(post.priceRange);
    const phoneHtml = post.phone ? `<a href="tel:${escapeHtml(post.phone.replace(/\s+/g, ''))}">${escapeHtml(post.phone)}</a>` : '';
    const addressHtml = post.address
        ? `${escapeHtml(post.address)} <button type="button" class="link-btn" data-copy-text="${escapeHtml(post.address)}">複製</button>`
        : '';

    return `
        <header class="drawer-hero" data-category="${post.category.key}">
            <span class="drawer-emoji" aria-hidden="true">${post.category.emoji}</span>
            <div>
                <p class="drawer-kicker">${escapeHtml(post.region)}${post.district ? `・${escapeHtml(post.district)}` : ''}</p>
                <h2 id="drawer-title">${escapeHtml(post.title)}</h2>
                <p class="drawer-sub">${formatDate(post.date)}${priceText ? `　${priceText}` : ''}　${escapeHtml(post.category.label)}</p>
            </div>
        </header>

        <div class="drawer-actions">
            ${post.mapUrl ? `<a class="btn btn-primary" href="${escapeHtml(post.mapUrl)}" target="_blank" rel="noopener">📍 Google 導航</a>` : ''}
            <a class="btn btn-ghost" href="${escapeHtml(post.permalink)}" target="_blank" rel="noopener">📸 IG 原文</a>
        </div>

        <dl class="info-list">
            ${renderInfoRow('🏡', '地址', addressHtml)}
            ${renderInfoRow('🕑', '營業時間', post.hours.map(escapeHtml).join('<br>'))}
            ${renderInfoRow('☎️', '電話', phoneHtml)}
        </dl>

        ${renderMenuList(post.menuItems)}

        ${post.review ? `<section class="drawer-section"><h3>懶懶花心得</h3><p class="review-text">${escapeHtml(post.review)}</p></section>` : ''}

        ${post.hashtags.length ? `<div class="tag-list">${post.hashtags.slice(0, 12).map(tag => `<span>#${escapeHtml(tag)}</span>`).join('')}</div>` : ''}

        <section class="drawer-section">
            <h3>Instagram 貼文</h3>
            <div class="ig-slot">
                <div class="skeleton" aria-hidden="true"><span></span><span></span><span></span></div>
                ${renderInstagramPlaceholder(escapeHtml(post.permalink))}
            </div>
        </section>`;
}

async function copyText(button) {
    try {
        await navigator.clipboard.writeText(button.dataset.copyText);
        button.textContent = '已複製 ✓';
    } catch {
        button.textContent = '複製失敗';
    }
    setTimeout(() => { button.textContent = '複製'; }, 1600);
}

export function createDetailDrawer(rootElement, { onClose }) {
    const panel = rootElement.querySelector('.drawer-panel');
    const body = rootElement.querySelector('.drawer-body');
    const closeButton = rootElement.querySelector('.drawer-close');
    let returnFocusTo = null;

    function close() {
        if (!rootElement.classList.contains('is-open')) return;
        rootElement.classList.remove('is-open');
        rootElement.setAttribute('aria-hidden', 'true');
        document.body.classList.remove('drawer-open');
        returnFocusTo?.focus({ preventScroll: true });
        onClose();
    }

    function open(post) {
        returnFocusTo = document.activeElement;
        body.innerHTML = renderDrawerContent(post);
        body.scrollTop = 0;
        rootElement.classList.add('is-open');
        rootElement.setAttribute('aria-hidden', 'false');
        document.body.classList.add('drawer-open');
        closeButton.focus({ preventScroll: true });
        processInstagramEmbeds().catch(() => {
            body.querySelector('.ig-slot').innerHTML = `<p class="muted">Instagram 內嵌載入失敗，<a href="${escapeHtml(post.permalink)}" target="_blank" rel="noopener">直接前往貼文</a></p>`;
        });
    }

    closeButton.addEventListener('click', close);
    rootElement.querySelector('.drawer-backdrop').addEventListener('click', close);
    document.addEventListener('keydown', event => {
        if (event.key === 'Escape') close();
    });
    panel.addEventListener('click', event => {
        const copyButton = event.target.closest('[data-copy-text]');
        if (copyButton) copyText(copyButton);
    });

    return { open, close };
}
