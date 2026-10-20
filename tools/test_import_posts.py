# 執行：python -m pytest tools/
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import import_posts as ip  # noqa: E402

POSTS_SOURCE = """export const IG_POSTS = [
    {
        region: '台中 Taichung',
        permalink: 'https://www.instagram.com/p/AAA/',
        date: '2025-01-01',
        map: 'https://maps.app.goo.gl/x',
        content: `✨️#舊店
🏡地址：台中市北區榮華街156號`
    } ,
    {
        region: '台中 Taichung',
        permalink: 'https://www.instagram.com/p/BBB/',
        date: '2025-01-02',
        map: '',
        lat: 24.1,
        lng: 120.6,
        content: `✨️#已有座標`
    }
];
"""

INBOX = """// 註解會被忽略
https://www.instagram.com/p/DO8d-m_k0Fd/?img_index=1
map: https://www.google.com/maps/place/x/@24.2672295,120.5587781,17z/data=!3d24.2672246!4d120.561353
✨️#浯江御麵館
🍽紅燒牛肉麵／$150
🏡地址：臺中市清水區鰲峰路257之7號
#懶懶花吃台中
---
https://www.instagram.com/reel/DII3CyjzZ4z/
date: 2025-04-07
region: 日本 Japan
內容有 `反引號` 與 ${x}
---
這段沒有網址會被略過
"""


def test_parse_inbox_reads_headers_and_body():
    entries = ip.parse_inbox(INBOX)
    assert len(entries) == 2
    first, second = entries
    assert first['permalink'] == 'https://www.instagram.com/p/DO8d-m_k0Fd/'
    assert first['shortcode'] == 'DO8d-m_k0Fd'
    assert first['region'] == '台中 Taichung'
    assert first['address'] == '臺中市清水區鰲峰路257之7號'
    assert first['content'].startswith('✨️#浯江御麵館')
    assert first['content'].endswith('#懶懶花吃台中')
    assert second['date'] == '2025-04-07'
    assert second['region'] == '日本 Japan'


def test_estimate_date_from_shortcode():
    assert ip.estimate_date_from_shortcode('DJWLcqkTgPY') == '2025-05-07'
    assert ip.estimate_date_from_shortcode('') == ''
    assert ip.estimate_date_from_shortcode('壞掉的') == ''


def test_region_from_address_handles_traditional_tai():
    assert ip.region_from_address('臺北市萬華區漢中街34-2號', '') == '台北 Taipei'
    assert ip.region_from_address('彰化縣和美鎮', '') == '彰化 Changhua'


def test_extract_coordinates_prefers_place_pin():
    url = 'https://www.google.com/maps/place/x/@24.2672295,120.5587781,17z/data=!3d24.2672246!4d120.561353'
    assert ip.extract_coordinates_from_url(url) == (24.2672246, 120.561353)
    assert ip.extract_coordinates_from_url('https://maps.google.com/?q=25.0,121.5') == (25.0, 121.5)
    assert ip.extract_coordinates_from_url('https://maps.app.goo.gl/abc') is None


def test_address_candidates_go_from_precise_to_coarse():
    assert ip.address_candidates('臺中市東區進德路600號5樓') == ['台中市東區進德路600號5樓', '台中市東區進德路600號', '台中市東區進德路']
    assert ip.address_candidates('') == []


def test_format_post_entry_escapes_template_literal():
    entry = ip.parse_inbox(INBOX)[1]
    block = ip.format_post_entry(entry, (35.0, 135.0))
    assert 'lat: 35.000000,' in block
    assert '\\`反引號\\`' in block
    assert '\\${x}' in block


def test_existing_shortcodes_and_append():
    assert ip.existing_shortcodes(POSTS_SOURCE) == {'AAA', 'BBB'}
    updated = ip.append_entries(POSTS_SOURCE, ['        {\n            region: \'x\'\n        }'])
    assert updated.rstrip().endswith('];')
    assert updated.count('region:') == 3


def test_append_entries_rejects_unknown_format():
    try:
        ip.append_entries('const x = 1;', ['{}'])
    except ValueError:
        return
    raise AssertionError('應該拋出 ValueError')


def test_backfill_only_touches_posts_without_coordinates():
    calls = []

    def fake_finder(map_url, address):
        calls.append((map_url, address))
        return (24.5, 120.7), 'fake'

    updated, filled, failures = ip.backfill_coordinates(POSTS_SOURCE, fake_finder)
    assert filled == 1 and failures == []
    assert calls == [('https://maps.app.goo.gl/x', '台中市北區榮華街156號')]
    assert updated.count('lat:') == 2
    assert "map: 'https://maps.app.goo.gl/x',\n        lat: 24.500000,\n        lng: 120.700000,\n" in updated


def test_backfill_reports_failures():
    _, filled, failures = ip.backfill_coordinates(POSTS_SOURCE, lambda url, address: (None, ''))
    assert filled == 0
    assert failures == ['台中市北區榮華街156號']


def test_write_preserving_newline_keeps_crlf(tmp_path):
    target = tmp_path / 'posts.js'
    target.write_bytes(b'a\r\nb\r\n')
    newline = ip.detect_newline(target)
    ip.write_preserving_newline(target, 'a\nb\nc\n', newline)
    assert target.read_bytes() == b'a\r\nb\r\nc\r\n'
