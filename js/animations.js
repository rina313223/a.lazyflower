// 動畫工具：進場淡入、FLIP 重排、數字遞增。皆尊重 prefers-reduced-motion。

import { REVEAL_STAGGER_MS } from './config.js';

const FLIP_DURATION_MS = 420;
const FLIP_EASING = 'cubic-bezier(.2,.8,.2,1)';

export function prefersReducedMotion() {
    return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
}

// 元素進入視窗時加上 .is-visible；同一批進場的元素依序延遲
export function createRevealObserver() {
    if (prefersReducedMotion() || !('IntersectionObserver' in window)) {
        return { observe: elements => elements.forEach(element => element.classList.add('is-visible')) };
    }

    const observer = new IntersectionObserver(entries => {
        const entering = entries.filter(entry => entry.isIntersecting);
        entering.forEach((entry, order) => {
            entry.target.style.setProperty('--reveal-delay', `${order * REVEAL_STAGGER_MS}ms`);
            entry.target.classList.add('is-visible');
            observer.unobserve(entry.target);
        });
    }, { rootMargin: '0px 0px -40px 0px', threshold: 0.05 });

    return { observe: elements => elements.forEach(element => observer.observe(element)) };
}

function captureRects(elements) {
    return new Map(elements.map(element => [element, element.getBoundingClientRect()]));
}

// FLIP：記錄位置 → 執行 DOM 變動 → 從舊位置動畫到新位置
export function flipReorder(container, applyDomChanges) {
    const before = captureRects([...container.children].filter(element => !element.hidden));
    applyDomChanges();
    if (prefersReducedMotion()) return;

    [...container.children].filter(element => !element.hidden).forEach(element => {
        const previousRect = before.get(element);
        if (!previousRect) {
            element.animate(
                [{ opacity: 0, transform: 'scale(.94)' }, { opacity: 1, transform: 'none' }],
                { duration: FLIP_DURATION_MS, easing: FLIP_EASING }
            );
            return;
        }
        const currentRect = element.getBoundingClientRect();
        const deltaX = previousRect.left - currentRect.left;
        const deltaY = previousRect.top - currentRect.top;
        if (deltaX === 0 && deltaY === 0) return;
        element.animate(
            [{ transform: `translate(${deltaX}px, ${deltaY}px)` }, { transform: 'none' }],
            { duration: FLIP_DURATION_MS, easing: FLIP_EASING }
        );
    });
}

export function countUp(element, targetValue, durationMs = 900) {
    const target = Number(targetValue);
    if (!Number.isFinite(target) || prefersReducedMotion()) {
        element.textContent = String(targetValue);
        return;
    }
    const startTime = performance.now();
    const step = now => {
        const progress = Math.min((now - startTime) / durationMs, 1);
        const eased = 1 - Math.pow(1 - progress, 3);
        element.textContent = Math.round(target * eased).toLocaleString('zh-TW');
        if (progress < 1) requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
}

export function pulse(element) {
    if (!element || prefersReducedMotion()) return;
    element.animate(
        [{ boxShadow: '0 0 0 0 rgba(244,114,182,.55)' }, { boxShadow: '0 0 0 14px rgba(244,114,182,0)' }],
        { duration: 900, easing: 'ease-out' }
    );
}
