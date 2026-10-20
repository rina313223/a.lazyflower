// 沿用舊版的防右鍵／防複製快捷鍵（未經同意勿轉載圖文）

const BLOCKED_CTRL_KEYS = new Set(['c', 'a', 'u']);

export function enableContentProtection() {
    document.addEventListener('contextmenu', event => event.preventDefault());
    document.addEventListener('keydown', event => {
        const key = event.key.toLowerCase();
        const isBlockedShortcut = (event.ctrlKey && BLOCKED_CTRL_KEYS.has(key)) || (event.ctrlKey && event.shiftKey && key === 'i');
        const isTypingInInput = event.target.matches?.('input, textarea');
        if (isBlockedShortcut && !isTypingInInput) event.preventDefault();
    });
}
