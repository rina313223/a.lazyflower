// 全站共用常數（集中管理，其他模組只讀取不修改）

export const REGIONS = Object.freeze([
    '台北 Taipei', '新北 New Taipei', '桃園 Taoyuan', '苗栗 Miaoli', '台中 Taichung', '彰化 Changhua',
    '南投 Nantou', '雲林 Yunlin', '嘉義 Chiayi', '台南 Tainan', '高雄 Kaohsiung', '屏東 Pingtung',
    '宜蘭 Yilan', '花蓮 Hualien', '台東 Taitung', '日本 Japan', '開箱 Unboxing', '旅遊 Travel'
]);

// 依關鍵字判斷文章類型，用於卡片圖示與配色（由上而下比對，先符合者優先）
export const CATEGORY_RULES = Object.freeze([
    { key: 'dessert', emoji: '🍧', label: '甜點冰品', keywords: ['冰', '豆花', '仙草', '甜點', 'dessert', '鬆餅', '蛋糕', 'スイーツ'] },
    { key: 'meat',    emoji: '🥩', label: '燒肉排餐', keywords: ['燒肉', '牛排', '板腱', '翼板', '漢堡排', '焼肉', 'yakiniku', '勝牛'] },
    { key: 'noodle',  emoji: '🍜', label: '麵食湯品', keywords: ['麵', '拉麵', '雞白湯', '羹', 'ramen'] },
    { key: 'cafe',    emoji: '☕', label: '咖啡輕食', keywords: ['咖啡', 'coffee', 'cafe'] },
    { key: 'snack',   emoji: '🍢', label: '小吃', keywords: ['米糕', '香腸', '炒飯', '小吃', '滷味'] }
]);
export const DEFAULT_CATEGORY = Object.freeze({ key: 'food', emoji: '🍽️', label: '美食' });

export const SORT_OPTIONS = Object.freeze({ NEWEST: 'newest', OLDEST: 'oldest' });

export const MAP_DEFAULT_VIEW = Object.freeze({ center: [23.7, 120.95], zoom: 7 });
export const MAP_TILE_URL = 'https://tile.openstreetmap.org/{z}/{x}/{y}.png';
export const MAP_TILE_ATTRIBUTION = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors';

export const SEARCH_DEBOUNCE_MS = 180;
export const REVEAL_STAGGER_MS = 60;

export const GOATCOUNTER_TOTAL_URL = 'https://lazyflower.goatcounter.com/counter/TOTAL.json';
export const IG_EMBED_SCRIPT_URL = 'https://www.instagram.com/embed.js';
