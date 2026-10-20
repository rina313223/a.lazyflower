#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
批次匯入 IG 食記到 posts.js，並自動補上地圖座標。

用法：
    python tools/import_posts.py              # 匯入 tools/inbox.txt 的所有貼文
    python tools/import_posts.py --dry-run    # 只預覽，不寫檔
    python tools/import_posts.py --backfill   # 幫 posts.js 裡缺座標的舊文章補 lat/lng
    python tools/import_posts.py --no-geocode # 不連網查座標

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
import re
import shutil
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

import requests

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
from get_data import clean_instagram_url, extract_map_link, detect_region  # noqa: E402

DEFAULT_POSTS_PATH = PROJECT_ROOT / 'posts.js'
DEFAULT_INBOX_PATH = Path(__file__).resolve().parent / 'inbox.txt'
INBOX_HISTORY_DIR = Path(__file__).resolve().parent / 'inbox_history'

ENTRY_SEPARATOR = re.compile(r'^\s*---+\s*$', re.MULTILINE)
HEADER_PATTERN = re.compile(r'^(map|date|region)\s*[:：]\s*(.+)$', re.IGNORECASE)
COMMENT_PREFIX = '//'
SHORTCODE_PATTERN = re.compile(r'instagram\.com/(?:[^/]+/)?(?:p|reel|tv)/([A-Za-z0-9_-]+)')
ADDRESS_PATTERN = re.compile(r'地址[：:]\s*(.+)')
COORDINATE_PATTERNS = (
    re.compile(r'!3d(-?\d+\.\d+)!4d(-?\d+\.\d+)'),
    re.compile(r'@(-?\d+\.\d+),(-?\d+\.\d+)'),
    re.compile(r'[?&](?:q|ll|query)=(-?\d+\.\d+),\s*(-?\d+\.\d+)'),
)

IG_SHORTCODE_ALPHABET = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_'
IG_ID_EPOCH_MS = 1314220021721
TAIPEI_TZ = timezone(timedelta(hours=8))

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
        return datetime.fromtimestamp(timestamp_ms / 1000, TAIPEI_TZ).strftime('%Y-%m-%d')
    except (OverflowError, OSError, ValueError):
        return ''


def extract_address(content):
    match = ADDRESS_PATTERN.search(content or '')
    return match.group(1).strip() if match else ''


def region_from_address(address, content):
    normalized = (address or '').replace('臺', '台')
    for city, region in CITY_TO_REGION.items():
        if normalized.startswith(city):
            return region
    return detect_region(content or '')


def parse_entry_block(block):
    lines = [line for line in block.strip('\n').split('\n') if not line.strip().startswith(COMMENT_PREFIX)]
    while lines and not lines[0].strip():
        lines.pop(0)
    if not lines or 'instagram.com' not in lines[0]:
        return None

    permalink = clean_instagram_url(lines[0].strip())
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
    address = extract_address(content)
    return {
        'permalink': permalink,
        'shortcode': extract_shortcode(permalink),
        'date': headers.get('date') or estimate_date_from_shortcode(extract_shortcode(permalink)),
        'region': headers.get('region') or region_from_address(address, content),
        'map': headers.get('map') or extract_map_link(content),
        'address': address,
        'content': content,
    }


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
    try:
        response = session.get(map_url, allow_redirects=True, timeout=HTTP_TIMEOUT_S)
        return extract_coordinates_from_url(response.url) or extract_coordinates_from_url(response.text[:200000])
    except requests.RequestException:
        return None


def address_candidates(address):
    """由精確到粗略：完整地址 → 去掉樓層 → 只到路段。"""
    normalized = (address or '').replace('臺', '台').strip()
    if not normalized:
        return []
    candidates = [normalized]
    up_to_number = re.split(r'(?<=號)', normalized)[0]
    if up_to_number not in candidates:
        candidates.append(up_to_number)
    road_match = re.match(r'(.+?[路街道](?:[一二三四五六七八九十]段)?)', normalized)
    if road_match and road_match.group(1) not in candidates:
        candidates.append(road_match.group(1))
    return candidates


class NominatimGeocoder:
    def __init__(self, session):
        self.session = session
        self.last_request_at = 0.0

    def _wait_rate_limit(self):
        elapsed = time.monotonic() - self.last_request_at
        if elapsed < NOMINATIM_MIN_INTERVAL_S:
            time.sleep(NOMINATIM_MIN_INTERVAL_S - elapsed)
        self.last_request_at = time.monotonic()

    def geocode(self, address):
        for query in address_candidates(address):
            self._wait_rate_limit()
            try:
                response = self.session.get(
                    NOMINATIM_URL,
                    params={'q': query, 'format': 'json', 'limit': 1, 'countrycodes': 'tw'},
                    timeout=HTTP_TIMEOUT_S,
                )
                results = response.json() if response.ok else []
            except (requests.RequestException, ValueError):
                results = []
            if results:
                return float(results[0]['lat']), float(results[0]['lon'])
        return None


def find_coordinates(map_url, address, session, geocoder):
    coordinates = resolve_map_link(map_url, session)
    if coordinates:
        return coordinates, 'Google 地圖連結'
    coordinates = geocoder.geocode(address) if address else None
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


MAP_LINE_PATTERN = re.compile(r"^(?P<indent>[ \t]*)map:\s*'(?P<url>[^']*)',[ \t]*\r?\n(?!\s*lat:)", re.MULTILINE)


def backfill_coordinates(posts_source, coordinate_finder):
    """在缺少 lat/lng 的文章 map 行後面插入座標；回傳 (新內容, 成功數, 失敗清單)。"""
    pieces = []
    cursor = 0
    filled = 0
    failures = []
    for match in MAP_LINE_PATTERN.finditer(posts_source):
        next_content = posts_source[match.end():match.end() + 3000]
        content_end = next_content.find('`', next_content.find('`') + 1)
        address = extract_address(next_content[:content_end if content_end > 0 else None])
        coordinates, _source = coordinate_finder(match.group('url'), address)
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

    def finder(map_url, address):
        if not enable_geocode:
            return None, ''
        return find_coordinates(map_url, address, session, geocoder)
    return finder


def run_import(posts_path, inbox_path, dry_run, enable_geocode):
    if not inbox_path.exists():
        inbox_path.write_text(INBOX_TEMPLATE, encoding='utf-8')
        print(f'已建立 {inbox_path}，請貼上貼文後再執行一次。')
        return 0

    entries = parse_inbox(inbox_path.read_text(encoding='utf-8'))
    if not entries:
        print('inbox.txt 裡沒有可匯入的貼文（第一行需要是 IG 網址）。')
        return 0

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
        coordinates, source = finder(entry['map'], entry['address'])
        status = f'📍 {coordinates[0]:.5f}, {coordinates[1]:.5f}（{source}）' if coordinates else '⚠️ 無座標（不會出現在地圖上）'
        print(f"✅ {label} {entry['date']}｜{entry['region']}｜{entry['content'].splitlines()[0] if entry['content'] else '(無內文)'}｜{status}")
        if not entry['map']:
            print('   ↳ 提醒：沒有 map: 連結，詳情頁不會有「Google 導航」按鈕')
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
    archived = archive_inbox(inbox_path)
    print(f'\n🎉 已新增 {len(blocks)} 篇到 {posts_path.name}（備份：{backup_path.name}；inbox 已封存到 {archived.name}）')
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


def main(argv=None):
    parser = argparse.ArgumentParser(description='批次匯入 IG 食記到 posts.js')
    parser.add_argument('--posts', type=Path, default=DEFAULT_POSTS_PATH, help='posts.js 路徑')
    parser.add_argument('--inbox', type=Path, default=DEFAULT_INBOX_PATH, help='待匯入貼文的文字檔')
    parser.add_argument('--dry-run', action='store_true', help='只預覽，不寫入檔案')
    parser.add_argument('--backfill', action='store_true', help='幫既有文章補上 lat/lng')
    parser.add_argument('--no-geocode', action='store_true', help='不連網查詢座標')
    args = parser.parse_args(argv)

    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    if args.backfill:
        return run_backfill(args.posts, args.dry_run)
    return run_import(args.posts, args.inbox, args.dry_run, not args.no_geocode)


if __name__ == '__main__':
    sys.exit(main())
