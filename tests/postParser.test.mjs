// 執行：node --test tests/postParser.test.mjs
import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
    cleanPermalink, extractShortcode, extractTitle, extractMenuItems, extractAddress,
    extractHours, extractReview, extractHashtags, extractDistrict, detectCategory, parsePost
} from '../js/postParser.js';
import { applyFilters, countByRegion } from '../js/filters.js';
import { escapeHtml, formatPriceRange } from '../js/htmlUtils.js';

const SAMPLE_CONTENT = `✨️#雞湯桑 #Torisan

🍽東京雞白湯／$248
炙燒叉燒飯／$ 120
小菜
➡️最後有菜單

🏡地址：臺中市東區進德路600號5樓
🕑營業時間：11:00～22:00
☎️電話：04 2211 0000

✏️很豐富的一碗拉麵🍜
吃得到雞湯香

#懶懶花吃台中 #台中美食 #台中美食`;

test('cleanPermalink 去掉 query 並補斜線', () => {
    assert.equal(cleanPermalink('https://www.instagram.com/p/ABC?img_index=1'), 'https://www.instagram.com/p/ABC/');
    assert.equal(cleanPermalink(''), '');
});

test('extractShortcode 支援 p 與 reel', () => {
    assert.equal(extractShortcode('https://www.instagram.com/reel/DII3CyjzZ4z/'), 'DII3CyjzZ4z');
    assert.equal(extractShortcode('https://example.com/'), '');
});

test('extractTitle 取第一個店名 hashtag', () => {
    assert.equal(extractTitle(SAMPLE_CONTENT), '雞湯桑');
    assert.equal(extractTitle('\n\n沒有星星的標題'), '沒有星星的標題');
    assert.equal(extractTitle(''), '');
});

test('extractMenuItems 解析品項與價格（含空白與無價格）', () => {
    assert.deepEqual(extractMenuItems(SAMPLE_CONTENT), [
        { name: '東京雞白湯', price: 248 },
        { name: '炙燒叉燒飯', price: 120 },
        { name: '小菜', price: null }
    ]);
    assert.deepEqual(extractMenuItems('沒有菜單'), []);
});

test('地址、營業時間、電話', () => {
    assert.equal(extractAddress(SAMPLE_CONTENT), '臺中市東區進德路600號5樓');
    assert.deepEqual(extractHours(SAMPLE_CONTENT), ['11:00～22:00']);
    assert.deepEqual(extractHours('🕑營業時間：\n週一｜10:00\n週二｜11:00\n☎️電話：1'), ['週一｜10:00', '週二｜11:00']);
    assert.deepEqual(extractHours('無'), []);
});

test('extractReview 擷取心得、不含 hashtag 行', () => {
    assert.equal(extractReview(SAMPLE_CONTENT), '很豐富的一碗拉麵🍜\n吃得到雞湯香');
    assert.equal(extractReview('無心得'), '');
});

test('extractHashtags 去重', () => {
    assert.deepEqual(extractHashtags(SAMPLE_CONTENT), ['懶懶花吃台中', '台中美食']);
});

test('extractDistrict', () => {
    assert.equal(extractDistrict('台中市清水區鰲峰路257之7號'), '清水區');
    assert.equal(extractDistrict('彰化縣和美鎮仁美路159號'), '和美鎮');
    assert.equal(extractDistrict(''), '');
});

test('detectCategory 依優先序判斷，店名優先於全文', () => {
    assert.equal(detectCategory(['京都勝牛', '炸牛排', '最後送冰淇淋']).key, 'meat');
    assert.equal(detectCategory(['某店', '', '', '好吃的豆花']).key, 'dessert');
    assert.equal(detectCategory(['某店']).key, 'food');
});

test('parsePost 座標選填，缺少時為 null', () => {
    const withoutCoordinates = parsePost({ region: '台中 Taichung', permalink: 'https://www.instagram.com/p/X1/', date: '2025-01-01', map: '', content: SAMPLE_CONTENT });
    assert.equal(withoutCoordinates.coordinates, null);
    assert.equal(withoutCoordinates.id, 'X1');
    assert.deepEqual(withoutCoordinates.priceRange, { min: 120, max: 248 });

    const withCoordinates = parsePost({ region: '台中 Taichung', permalink: 'https://www.instagram.com/p/X2/', date: '2025-01-01', map: '', lat: 24.1, lng: 120.6, content: '' });
    assert.deepEqual([...withCoordinates.coordinates], [24.1, 120.6]);
});

test('applyFilters：地區、多關鍵字 AND、排序', () => {
    const posts = [
        parsePost({ region: '台中 Taichung', permalink: 'https://www.instagram.com/p/A/', date: '2025-01-01', content: '✨️#牛肉麵\n🏡地址：台中市清水區' }),
        parsePost({ region: '台中 Taichung', permalink: 'https://www.instagram.com/p/B/', date: '2025-03-01', content: '✨️#豆花\n🏡地址：台中市北區' }),
        parsePost({ region: '台北 Taipei', permalink: 'https://www.instagram.com/p/C/', date: '2025-02-01', content: '✨️#雪花冰\n🏡地址：台北市萬華區' })
    ];
    assert.deepEqual(applyFilters(posts).map(post => post.id), ['B', 'C', 'A']);
    assert.deepEqual(applyFilters(posts, { sort: 'oldest' }).map(post => post.id), ['A', 'C', 'B']);
    assert.deepEqual(applyFilters(posts, { region: '台北 Taipei' }).map(post => post.id), ['C']);
    assert.deepEqual(applyFilters(posts, { query: '清水 牛肉' }).map(post => post.id), ['A']);
    assert.deepEqual(applyFilters(posts, { query: '不存在' }), []);
    assert.deepEqual(countByRegion(posts), { '台中 Taichung': 2, '台北 Taipei': 1 });
});

test('escapeHtml 與 formatPriceRange', () => {
    assert.equal(escapeHtml('<b>"x"</b>'), '&lt;b&gt;&quot;x&quot;&lt;/b&gt;');
    assert.equal(formatPriceRange(null), '');
    assert.equal(formatPriceRange({ min: 50, max: 50 }), '$50');
    assert.equal(formatPriceRange({ min: 30, max: 150 }), '$30–150');
});
