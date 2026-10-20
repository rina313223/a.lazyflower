// 只在需要時才載入 Instagram embed.js（避免首頁一次塞進大量 iframe）

import { IG_EMBED_SCRIPT_URL } from './config.js';

let scriptPromise = null;

function loadEmbedScript() {
    if (window.instgrm) return Promise.resolve();
    if (scriptPromise) return scriptPromise;

    scriptPromise = new Promise((resolve, reject) => {
        const script = document.createElement('script');
        script.src = IG_EMBED_SCRIPT_URL;
        script.async = true;
        script.onload = () => resolve();
        script.onerror = () => {
            scriptPromise = null;
            reject(new Error('Instagram embed script failed to load'));
        };
        document.head.appendChild(script);
    });
    return scriptPromise;
}

export function renderInstagramPlaceholder(permalink) {
    return `<blockquote class="instagram-media" data-instgrm-permalink="${permalink}" data-instgrm-version="14" data-instgrm-captioned></blockquote>`;
}

export async function processInstagramEmbeds() {
    await loadEmbedScript();
    window.instgrm?.Embeds.process();
}
