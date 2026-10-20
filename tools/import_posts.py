#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
批次匯入 IG 食記到 posts.js，並自動補上地圖座標。

用法：
    python tools/import_posts.py              # 匯入 tools/inbox.txt 的所有貼文
    python tools/import_posts.py --dry-run    # 只預覽，不寫檔
    python tools/import_posts.py --backfill   # 幫 posts.js 裡缺座標的舊文章補 lat/lng
    python tools/import_posts.py --no-geocode # 不連網查座標
    python tools/import_posts.py --from-instagram           # 直接從 IG 官方 API 抓所有貼文（免貼 inbox）
    python tools/import_posts.py --from-instagram --limit 5 # 只抓最新 5 篇（試跑用）
    python tools/import_posts.py --from-instagram --since 2026-10-01  # 只匯入該日以後的貼文
    python tools/import_posts.py --report-missing [--csv]  # 列出不在地圖上的文章

inbox.txt 格式（多篇用一行 --- 分隔）：
    https://www.instagram.com/p/XXXXXXXX/
    map: https://maps.app.goo.gl/xxxx        ← 選填，強烈建議（座標最準）
    date: 2025-11-20                          ← 選填，預設由 IG 短碼推算
    region: 台中 Taichung                      ← 選填，預設由地址判斷
    ✨️#店名
    ...（直接貼上整段 IG 貼文內容）
    ---
"""

import argparse
import csv
import re
import shutil
import sys
import time
import unicodedata
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

import requests

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
from get_data import clean_instagram_url, extract_map_link, detect_region  # noqa: E402
import instagram_api  # noqa: E402  （與本檔同在 tools/，執行時已在 sys.path）

DEFAULT_POSTS_PATH = PROJECT_ROOT / 'posts.js'
DEFAULT_INBOX_PATH = Path(__file__).resolve().parent / 'inbox.txt'
INBOX_HISTORY_DIR = Path(__file__).resolve().parent / 'inbox_history'

ENTRY_SEPARATOR = re.compile(r'^\s*---+\s*$', re.MULTILINE)
HEADER_PATTERN = re.compile(r'^(map|date|region)\s*[:：]\s*(.+)$', re.IGNORECASE)
COMMENT_PREFIX = '//'
SHORTCODE_PATTERN = re.compile(r'instagram\.com/(?:[^/]+/)?(?:p|reel|tv)/([A-Za-z0-9_-]+)')
ADDRESS_PATTERN = re.compile(r'地址[：:]\s*(.+)')
GOOGLE_MAPS_SEARCH_URL = 'https://www.google.com/maps/search/?api=1&query='
POSTAL_PREFIX_PATTERN = re.compile(r'^\s*\d{3,6}')
JP_POSTAL_PATTERN = re.compile(r'(\d{3})\s*[-−ー]\s*(\d{4})')
# 縣市 + 鄉鎮市區 +（選填）村里 +（選填）鄰 + 其餘（路段門牌）
TW_ADDRESS_PATTERN = re.compile(
    r'^(?P<city>.{2}[市縣])(?P<district>.{1,3}?[區鎮鄉市])'
    r'(?:[^\d]{1,3}?[村里](?![路街道段巷]))?(?:\d+鄰)?(?P<rest>.+)$'
)
TW_ROAD_PATTERN = re.compile(r'^(.+?(?:大道|路|街|道)(?:[一二三四五六七八九十]段)?)')
JAPAN_REGION = '日本 Japan'
COORDINATE_PATTERNS = (
    re.compile(r'!3d(-?\d+\.\d+)!4d(-?\d+\.\d+)'),
    re.compile(r'@(-?\d+\.\d+),(-?\d+\.\d+)'),
    re.compile(r'[?&](?:q|ll|query)=(-?\d+\.\d+),\s*(-?\d+\.\d+)'),
)

IG_SHORTCODE_ALPHABET = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_'
IG_ID_EPOCH_MS = 1314220021721

CITY_TO_REGION = {
    '台北': '台北 Taipei', '新北': '新北 New Taipei', '桃園': '桃園 Taoyuan', '苗栗': '苗栗 Miaoli',
    '台中': '台中 Taichung', '彰化': '彰化 Changhua', '南投': '南投 Nantou', '雲林': '雲林 Yunlin',
    '嘉義': '嘉義 Chiayi', '台南': '台南 Tainan', '高雄': '高雄 Kaohsiung', '屏東': '屏東 Pingtung',
    '宜蘭': '宜蘭 Yilan', '花蓮': '花蓮 Hualien', '台東': '台東 Taitung',
}

NOMINATIM_URL = 'https://nominatim.openstreetmap.org/search'
NOMINATIM_MIN_INTERVAL_S = 1.1
HTTP_HEADERS = {'User-Agent': 'a.lazyflower-import/1.0 (personal food blog)'}
HTTP_TIMEOUT_S = 15


# ---------- 解析 inbox ----------

def extract_shortcode(url):
    match = SHORTCODE_PATTERN.search(url or '')
    return match.group(1) if match else ''


def estimate_date_from_shortcode(shortcode):
    """IG 短碼可還原 media id，id 的高位元是毫秒時間戳（以 IG 自訂 epoch 起算）。"""
    if not shortcode or any(ch not in IG_SHORTCODE_ALPHABET for ch in shortcode):
        return ''
    media_id = 0
    for ch in shortcode[:11]:
        media_id = media_id * 64 + IG_SHORTCODE_ALPHABET.index(ch)
    timestamp_ms = (media_id >> 23) + IG_ID_EPOCH_MS
    try:
        return datetime.fromtimestamp(timestamp_ms / 1000, instagram_api.TAIPEI_TZ).strftime('%Y-%m-%d')
    except (OverflowError, OSError, ValueError):
        return ''


def extract_address(content):
    match = ADDRESS_PATTERN.search(content or '')
    return match.group(1).strip() if match else ''


def normalize_taiwan_address(address):
    """去掉開頭郵遞區號與空白，統一「臺」為「台」，方便比對。"""
    return re.sub(r'\s+', '', POSTAL_PREFIX_PATTERN.sub('', address or '')).replace('臺', '台')


def region_from_address(address, content):
    normalized = normalize_taiwan_address(address)
    for city, region in CITY_TO_REGION.items():
        if normalized.startswith(city):
            return region
    return detect_region(content or '')


def build_entry(permalink, content, date='', region='', map_url=''):
    """各來源（inbox、IG API）共用的 entry 組裝；未提供的欄位由內文推導。"""
    permalink = clean_instagram_url(permalink)
    shortcode = extract_shortcode(permalink)
    address = extract_address(content)
    return {
        'permalink': permalink,
        'shortcode': shortcode,
        'date': date or estimate_date_from_shortcode(shortcode),
        'region': region or region_from_address(address, content),
        'map': map_url or extract_map_link(content),
        'address': address,
        'content': content,
    }


def parse_entry_block(block):
    lines = [line for line in block.strip('\n').split('\n') if not line.strip().startswith(COMMENT_PREFIX)]
    while lines and not lines[0].strip():
        lines.pop(0)
    if not lines or 'instagram.com' not in lines[0]:
        return None

    headers = {}
    body_start = 1
    for index in range(1, len(lines)):
        header_match = HEADER_PATTERN.match(lines[index].strip())
        if not header_match:
            body_start = index
            break
        headers[header_match.group(1).lower()] = header_match.group(2).strip()
        body_start = index + 1

    content = '\n'.join(lines[body_start:]).strip()
    return build_entry(lines[0].strip(), content, headers.get('date', ''), headers.get('region', ''), headers.get('map', ''))


def parse_inbox(text):
    entries = []
    for block in ENTRY_SEPARATOR.split(text or ''):
        entry = parse_entry_block(block)
        if entry:
            entries.append(entry)
    return entries


# ---------- 座標 ----------

def extract_coordinates_from_url(url):
    for pattern in COORDINATE_PATTERNS:
        match = pattern.search(url or '')
        if match:
            return float(match.group(1)), float(match.group(2))
    return None


def resolve_map_link(map_url, session):
    if not map_url:
        return None
    direct = extract_coordinates_from_url(map_url)
    if direct:
        return direct
    if '/maps/search/' in map_url:
        return None  # 自動產生的搜尋連結：頁面內的座標是預設視角，不可信
    try:
        response = session.get(map_url, allow_redirects=True, timeout=HTTP_TIMEOUT_S)
        return extract_coordinates_from_url(response.url) or extract_coordinates_from_url(response.text[:200000])
    except requests.RequestException:
        return None


def _unique(values):
    return list(dict.fromkeys(value for value in values if value))


def taiwan_address_candidates(address):
    """由精確到粗略：完整地址 → 去掉樓層 → 「路段, 行政區, 縣市」（OSM 慣用「臺」）。"""
    normalized = normalize_taiwan_address(address)
    if not normalized:
        return []
    candidates = [normalized, re.split(r'(?<=號)', normalized)[0]]
    parts = TW_ADDRESS_PATTERN.match(normalized)
    road = TW_ROAD_PATTERN.match(parts.group('rest')) if parts else None
    if road:
        structured = f"{road.group(1)}, {parts.group('district')}, {parts.group('city')}"
        candidates.append(structured.replace('台', '臺'))
    return _unique(candidates)


def japan_address_candidates(address):
    """日本地址格式混雜（中英日），以郵遞區號查詢最穩定（精確到町丁目）。"""
    postal = JP_POSTAL_PATTERN.search(unicodedata.normalize('NFKC', address or ''))
    return [f'{postal.group(1)}-{postal.group(2)}'] if postal else []


def address_candidates(address, country_code='tw'):
    if country_code == 'jp':
        return japan_address_candidates(address)
    return taiwan_address_candidates(address)


def country_code_for_region(region):
    return 'jp' if region == JAPAN_REGION else 'tw'


class NominatimGeocoder:
    def __init__(self, session):
        self.session = session
        self.last_request_at = 0.0

    def _wait_rate_limit(self):
        elapsed = time.monotonic() - self.last_request_at
        if elapsed < NOMINATIM_MIN_INTERVAL_S:
            time.sleep(NOMINATIM_MIN_INTERVAL_S - elapsed)
        self.last_request_at = time.monotonic()

    def geocode(self, address, country_code='tw'):
        for query in address_candidates(address, country_code):
            self._wait_rate_limit()
            try:
                response = self.session.get(
                    NOMINATIM_URL,
                    params={'q': query, 'format': 'json', 'limit': 1, 'countrycodes': country_code},
                    timeout=HTTP_TIMEOUT_S,
                )
                results = response.json() if response.ok else []
            except (requests.RequestException, ValueError):
                results = []
            if results:
                return float(results[0]['lat']), float(results[0]['lon'])
        return None


def find_coordinates(map_url, address, session, geocoder, country_code='tw'):
    coordinates = resolve_map_link(map_url, session)
    if coordinates:
        return coordinates, 'Google 地圖連結'
    coordinates = geocoder.geocode(address, country_code) if address else None
    if coordinates:
        return coordinates, 'OSM 地址查詢'
    return None, ''


# ---------- 寫入 posts.js ----------

def escape_template_literal(text):
    return (text or '').replace('\\', '\\\\').replace('`', '\\`').replace('${', '\\${')


def escape_single_quoted(text):
    return (text or '').replace('\\', '\\\\').replace("'", "\\'")


def format_post_entry(entry, coordinates=None, indent='        '):
    inner = indent + '    '
    lines = [
        f"{indent}{{",
        f"{inner}region: '{escape_single_quoted(entry['region'])}',",
        f"{inner}permalink: '{escape_single_quoted(entry['permalink'])}',",
        f"{inner}date: '{escape_single_quoted(entry['date'])}',",
        f"{inner}map: '{escape_single_quoted(entry['map'])}',",
    ]
    if coordinates:
        lines.append(f"{inner}lat: {coordinates[0]:.6f},")
        lines.append(f"{inner}lng: {coordinates[1]:.6f},")
    lines.append(f"{inner}content: `{escape_template_literal(entry['content'])}`")
    lines.append(f"{indent}}}")
    return '\n'.join(lines)


def existing_shortcodes(posts_source):
    return {extract_shortcode(url) for url in re.findall(r"permalink:\s*'([^']+)'", posts_source)}


def append_entries(posts_source, entry_blocks):
    closing = re.search(r'\}\s*\]\s*;?\s*$', posts_source)
    if not closing:
        raise ValueError('找不到 posts.js 陣列結尾，請確認檔案格式為 export const IG_POSTS = [ ... ];')
    insertion_point = closing.start() + 1
    addition = ''.join(f',\n{block}' for block in entry_blocks)
    return posts_source[:insertion_point] + addition + '\n];\n'


REGION_LINE_PATTERN = re.compile(r"region:\s*'([^']*)'")
MAP_LINE_PATTERN = re.compile(r"^(?P<indent>[ \t]*)map:\s*'(?P<url>[^']*)',[ \t]*\r?\n(?!\s*lat:)", re.MULTILINE)


def backfill_coordinates(posts_source, coordinate_finder):
    """在缺少 lat/lng 的文章 map 行後面插入座標；回傳 (新內容, 成功數, 失敗清單)。"""
    pieces = []
    cursor = 0
    filled = 0
    failures = []
    for match in MAP_LINE_PATTERN.finditer(posts_source):
        region_match = REGION_LINE_PATTERN.findall(posts_source, 0, match.start())
        region = region_match[-1] if region_match else ''
        next_content = posts_source[match.end():match.end() + 3000]
        content_end = next_content.find('`', next_content.find('`') + 1)
        address = extract_address(next_content[:content_end if content_end > 0 else None])
        coordinates, _source = coordinate_finder(match.group('url'), address, region)
        pieces.append(posts_source[cursor:match.end()])
        if coordinates:
            indent = match.group('indent')
            pieces.append(f"{indent}lat: {coordinates[0]:.6f},\n{indent}lng: {coordinates[1]:.6f},\n")
            filled += 1
        else:
            failures.append(address or match.group('url') or '(無地址)')
        cursor = match.end()
    pieces.append(posts_source[cursor:])
    return ''.join(pieces), filled, failures


def detect_newline(path):
    return '\r\n' if b'\r\n' in path.read_bytes() else '\n'


def write_preserving_newline(path, text, newline):
    path.write_text(text, encoding='utf-8', newline=newline)


def backup_file(path):
    backup_path = path.with_suffix(path.suffix + '.bak')
    shutil.copyfile(path, backup_path)
    return backup_path


def archive_inbox(inbox_path):
    INBOX_HISTORY_DIR.mkdir(exist_ok=True)
    archived = INBOX_HISTORY_DIR / f"inbox-{datetime.now().strftime('%Y%m%d-%H%M%S')}.txt"
    shutil.copyfile(inbox_path, archived)
    inbox_path.write_text(INBOX_TEMPLATE, encoding='utf-8')
    return archived


INBOX_TEMPLATE = """// 在下面貼上 IG 貼文，多篇用一行 --- 分隔。以 // 開頭的行會被忽略。
// 第一行放 IG 網址；接著可選填 map: / date: / region:；之後直接貼上整段貼文內容。
// 範例：
// https://www.instagram.com/p/XXXXXXXX/
// map: https://maps.app.goo.gl/xxxx
// ✨️#店名
// 🍽品項／$100
// 🏡地址：台中市西屯區…
// ---

"""


# ---------- 指令 ----------

def build_coordinate_finder(enable_geocode):
    session = requests.Session()
    session.headers.update(HTTP_HEADERS)
    geocoder = NominatimGeocoder(session)

    def finder(map_url, address, region=''):
        if not enable_geocode:
            return None, ''
        return find_coordinates(map_url, address, session, geocoder, country_code_for_region(region))
    return finder


def extract_title(content):
    # 對應前端 js/postParser.js 的 extractTitle()，規則修改時請兩邊同步
    first_line = next((line.strip() for line in (content or '').splitlines() if line.strip()), '')
    names = [part.strip() for part in first_line.lstrip('✨️ ').split('#') if part.strip()]
    return names[0] if names else first_line


def build_map_search_url(content, address):
    """沒有 Google 地圖分享連結時，用「店名 地址」產生搜尋連結，仍可導航。"""
    if not address:
        return ''
    query = f'{extract_title(content)} {address}'.strip()
    return GOOGLE_MAPS_SEARCH_URL + quote(query)


def import_entries(posts_path, entries, dry_run, enable_geocode, generate_map_search=False):
    """把 entries 中尚未存在的文章寫進 posts.js；回傳實際寫入篇數（dry-run 為 0）。"""
    posts_source = posts_path.read_text(encoding='utf-8')
    known = existing_shortcodes(posts_source)
    finder = build_coordinate_finder(enable_geocode)
    blocks = []

    for entry in entries:
        label = f"[{entry['shortcode']}]"
        if entry['shortcode'] in known:
            print(f'⏭  {label} 已存在，略過')
            continue
        known.add(entry['shortcode'])
        coordinates, source = finder(entry['map'], entry['address'], entry['region'])
        if generate_map_search and not entry['map']:
            entry = {**entry, 'map': build_map_search_url(entry['content'], entry['address'])}
        status = f'📍 {coordinates[0]:.5f}, {coordinates[1]:.5f}（{source}）' if coordinates else '⚠️ 無座標（不會出現在地圖上）'
        first_line = entry['content'].splitlines()[0] if entry['content'] else '(無內文)'
        print(f"✅ {label} {entry['date']}｜{entry['region']}｜{first_line}｜{status}")
        if not entry['map']:
            print('   ↳ 提醒：沒有地圖連結，詳情頁不會有「Google 導航」按鈕')
        blocks.append(format_post_entry(entry, coordinates))

    if not blocks:
        print('沒有新文章需要寫入。')
        return 0
    if dry_run:
        print('\n--- dry-run 預覽 ---\n' + '\n'.join(blocks))
        return 0

    newline = detect_newline(posts_path)
    backup_path = backup_file(posts_path)
    write_preserving_newline(posts_path, append_entries(posts_source, blocks), newline)
    print(f'\n🎉 已新增 {len(blocks)} 篇到 {posts_path.name}（備份：{backup_path.name}）')
    return len(blocks)


def run_import(posts_path, inbox_path, dry_run, enable_geocode):
    if not inbox_path.exists():
        inbox_path.write_text(INBOX_TEMPLATE, encoding='utf-8')
        print(f'已建立 {inbox_path}，請貼上貼文後再執行一次。')
        return 0

    entries = parse_inbox(inbox_path.read_text(encoding='utf-8'))
    if not entries:
        print('inbox.txt 裡沒有可匯入的貼文（第一行需要是 IG 網址）。')
        return 0

    written = import_entries(posts_path, entries, dry_run, enable_geocode)
    if written:
        archived = archive_inbox(inbox_path)
        print(f'inbox 已封存到 {archived.name}')
    return 0


def entry_from_media(media):
    """把 IG API 的一筆 media 轉成與 inbox 解析結果相同的 entry 格式。"""
    content = (media.get('caption') or '').strip()
    return build_entry(media['permalink'], content, instagram_api.timestamp_to_date(media.get('timestamp')))


def refresh_token_if_possible(token, session, env_path):
    try:
        new_token, expires_in = instagram_api.refresh_and_store_token(token, session, env_path)
    except instagram_api.InstagramApiError as error:
        print(f'ℹ️  token 未延長（{error}），沿用目前的 token')
        return token
    if new_token != token:
        print(f'🔑 token 已延長，約 {expires_in // 86400} 天後到期')
    return new_token


def run_from_instagram(posts_path, dry_run, enable_geocode, limit, env_path=instagram_api.DEFAULT_ENV_PATH, since=None):
    session = requests.Session()
    try:
        token = instagram_api.load_access_token(env_path)
        token = refresh_token_if_possible(token, session, env_path)
        media_list = instagram_api.fetch_all_media(token, session, limit, since)
    except instagram_api.InstagramApiError as error:
        print(f'❌ {error}')
        return 1

    since_note = f'（{since} 以後）' if since else ''
    print(f'從 Instagram 取得 {len(media_list)} 篇貼文{since_note}')
    entries = [entry_from_media(media) for media in media_list if media.get('permalink')]
    entries.sort(key=lambda entry: entry['date'])
    import_entries(posts_path, entries, dry_run, enable_geocode, generate_map_search=True)
    return 0


def run_backfill(posts_path, dry_run):
    posts_source = posts_path.read_text(encoding='utf-8')
    finder = build_coordinate_finder(enable_geocode=True)
    updated_source, filled, failures = backfill_coordinates(posts_source, finder)
    print(f'補上座標：{filled} 篇；失敗：{len(failures)} 篇')
    for failure in failures:
        print(f'   ⚠️ {failure}')
    if dry_run or filled == 0:
        return 0
    newline = detect_newline(posts_path)
    backup_path = backup_file(posts_path)
    write_preserving_newline(posts_path, updated_source, newline)
    print(f'已寫入 {posts_path.name}（備份：{backup_path.name}）')
    return 0


# ---------- 缺座標報表 ----------

POST_OBJECT_PATTERN = re.compile(
    r"region:\s*'(?P<region>[^']*)',\s*"
    r"permalink:\s*'(?P<permalink>[^']*)',\s*"
    r"date:\s*'(?P<date>[^']*)',\s*"
    r"map:\s*'(?P<map>[^']*)',\s*"
    r"(?:lat:\s*(?P<lat>-?[\d.]+),\s*lng:\s*-?[\d.]+,\s*)?"
    r"content:\s*`(?P<content>(?:\\.|[^`\\])*)`"
)
REASON_NOT_FOUND = '查不到座標'
REASON_NO_ADDRESS = '無地址'
REASON_PRIORITY = {REASON_NOT_FOUND: 0, REASON_NO_ADDRESS: 1}
REPORT_CSV_PATH = Path(__file__).resolve().parent / 'missing_coordinates.csv'


def parse_posts_source(posts_source):
    """從 posts.js 文字取出每篇文章的欄位（只讀，不執行 JS）。"""
    return [
        {
            'region': match.group('region'),
            'permalink': match.group('permalink'),
            'date': match.group('date'),
            'map': match.group('map'),
            'has_coordinates': match.group('lat') is not None,
            'content': match.group('content'),
        }
        for match in POST_OBJECT_PATTERN.finditer(posts_source)
    ]


def missing_coordinate_rows(posts):
    """不會出現在地圖上的文章：先列「查不到座標」（多為食記），再列「無地址」；同類由新到舊。"""
    rows = []
    for post in posts:
        if post['has_coordinates']:
            continue
        address = extract_address(post['content'])
        rows.append({
            'reason': REASON_NOT_FOUND if address else REASON_NO_ADDRESS,
            'date': post['date'],
            'title': extract_title(post['content']) or '(無內文)',
            'region': post['region'],
            'permalink': post['permalink'],
            'address': address,
        })
    rows.sort(key=lambda row: row['date'], reverse=True)
    rows.sort(key=lambda row: REASON_PRIORITY[row['reason']])
    return rows


def format_report_row(row):
    line = f"[{row['reason']}] {row['date']}  {row['title'][:24]}  {row['region'].split(' ')[0]}  {row['permalink']}"
    return f"{line}\n    地址：{row['address']}" if row['address'] else line


def write_report_csv(rows, csv_path):
    fieldnames = ['reason', 'date', 'title', 'region', 'permalink', 'address']
    with csv_path.open('w', encoding='utf-8-sig', newline='') as csv_file:  # utf-8-sig：Excel 開啟不亂碼
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def run_report_missing(posts_path, write_csv):
    posts = parse_posts_source(posts_path.read_text(encoding='utf-8'))
    rows = missing_coordinate_rows(posts)
    for row in rows:
        print(format_report_row(row))
    not_found = sum(row['reason'] == REASON_NOT_FOUND for row in rows)
    print(f'\n共 {len(posts)} 篇，{len(rows)} 篇不在地圖上（{REASON_NOT_FOUND} {not_found}、{REASON_NO_ADDRESS} {len(rows) - not_found}）')
    print('補法：把該篇的 map: 換成 Google 地圖「分享」連結（maps.app.goo.gl），再執行 --backfill')
    if write_csv:
        write_report_csv(rows, REPORT_CSV_PATH)
        print(f'已輸出 {REPORT_CSV_PATH}')
    return 0


def parse_since_date(value):
    """argparse 用：驗證 YYYY-MM-DD，回傳正規化字串（例如 2026-10-01）。"""
    try:
        return datetime.strptime(value, '%Y-%m-%d').strftime('%Y-%m-%d')
    except ValueError:
        raise argparse.ArgumentTypeError(f'日期格式需為 YYYY-MM-DD（例如 2026-10-01），收到：{value}')


def main(argv=None):
    parser = argparse.ArgumentParser(description='批次匯入 IG 食記到 posts.js')
    parser.add_argument('--posts', type=Path, default=DEFAULT_POSTS_PATH, help='posts.js 路徑')
    parser.add_argument('--inbox', type=Path, default=DEFAULT_INBOX_PATH, help='待匯入貼文的文字檔')
    parser.add_argument('--dry-run', action='store_true', help='只預覽，不寫入檔案')
    parser.add_argument('--backfill', action='store_true', help='幫既有文章補上 lat/lng')
    parser.add_argument('--no-geocode', action='store_true', help='不連網查詢座標')
    parser.add_argument('--from-instagram', action='store_true', help='從 IG 官方 API 抓取自己帳號的所有貼文')
    parser.add_argument('--limit', type=int, default=None, help='搭配 --from-instagram：最多抓幾篇（新到舊）')
    parser.add_argument('--since', type=parse_since_date, default=None, metavar='YYYY-MM-DD',
                        help='搭配 --from-instagram：只匯入該日（含）以後的貼文，台灣時間')
    parser.add_argument('--report-missing', action='store_true', help='列出不會出現在地圖上的文章（只讀）')
    parser.add_argument('--csv', action='store_true', help='搭配 --report-missing：另存 tools/missing_coordinates.csv')
    args = parser.parse_args(argv)

    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    if args.report_missing:
        return run_report_missing(args.posts, args.csv)
    if args.backfill:
        return run_backfill(args.posts, args.dry_run)
    if args.from_instagram:
        return run_from_instagram(args.posts, args.dry_run, not args.no_geocode, args.limit, since=args.since)
    return run_import(args.posts, args.inbox, args.dry_run, not args.no_geocode)


if __name__ == '__main__':
    sys.exit(main())
