// GoatCounter 總瀏覽次數

import { GOATCOUNTER_TOTAL_URL } from './config.js';
import { countUp } from './animations.js';

function parseCount(rawCount) {
    return Number(String(rawCount ?? '').replace(/[^\d]/g, ''));
}

export async function renderVisitCount(element) {
    if (!element) return;
    try {
        const response = await fetch(GOATCOUNTER_TOTAL_URL);
        if (!response.ok) throw new Error(`GoatCounter HTTP ${response.status}`);
        const { count } = await response.json();
        const numericCount = parseCount(count);
        if (Number.isFinite(numericCount) && numericCount > 0) countUp(element, numericCount);
        else element.textContent = count || '—';
    } catch (error) {
        console.warn('無法取得瀏覽次數', error);
        element.textContent = '—';
    }
}
