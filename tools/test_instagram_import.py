# 執行：python -m pytest tools/
# 以假的 session 模擬 Instagram API，不會真的連線
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import import_posts as ip  # noqa: E402
import instagram_api as api  # noqa: E402


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code
        self.ok = status_code < 400

    def json(self):
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


class FakeSession:
    def __init__(self, responses_by_url):
        self.responses_by_url = responses_by_url
        self.calls = []
        self.headers = {}

    def get(self, url, params=None, timeout=None):
        self.calls.append((url, params))
        return self.responses_by_url[url]


FOOD_CAPTION = """✨️#浯江御麵館

🍽紅燒牛肉麵／$150
🏡地址：台中市清水區鰲峰路257之7號

#懶懶花吃台中"""

PAGE_1 = {
    'data': [{'id': '1', 'caption': FOOD_CAPTION, 'permalink': 'https://www.instagram.com/p/NEW1/', 'timestamp': '2025-10-01T17:30:00+0000', 'media_type': 'IMAGE'}],
    'paging': {'next': 'https://graph.instagram.com/next-page'}
}
PAGE_2 = {
    'data': [
        {'id': '2', 'caption': '今天開箱新耳機🎧', 'permalink': 'https://www.instagram.com/reel/NEW2/', 'timestamp': '2025-09-01T03:00:00+0000', 'media_type': 'VIDEO'},
        {'id': '3', 'permalink': 'https://www.instagram.com/p/NEW3/', 'timestamp': '2025-08-01T03:00:00+0000', 'media_type': 'IMAGE'}
    ],
    'paging': {}
}


def media_session():
    return FakeSession({
        'https://graph.instagram.com/me/media': FakeResponse(PAGE_1),
        'https://graph.instagram.com/next-page': FakeResponse(PAGE_2),
    })


def test_fetch_all_media_follows_paging():
    session = media_session()
    media_list = api.fetch_all_media('TOKEN', session)
    assert [media['id'] for media in media_list] == ['1', '2', '3']
    assert session.calls[0][1]['access_token'] == 'TOKEN'
    assert session.calls[1][1] is None


def test_fetch_all_media_respects_limit():
    session = media_session()
    assert len(api.fetch_all_media('TOKEN', session, limit=1)) == 1
    assert len(session.calls) == 1


def test_api_error_is_raised_with_message():
    session = FakeSession({'https://graph.instagram.com/me/media': FakeResponse({'error': {'message': 'Invalid OAuth access token'}}, 400)})
    with pytest.raises(api.InstagramApiError, match='Invalid OAuth'):
        api.fetch_all_media('BAD', session)


def test_non_json_response_is_reported():
    session = FakeSession({'https://graph.instagram.com/me/media': FakeResponse(ValueError('x'), 502)})
    with pytest.raises(api.InstagramApiError, match='502'):
        api.fetch_all_media('TOKEN', session)


def test_timestamp_to_date_uses_taipei_time():
    assert api.timestamp_to_date('2025-10-01T17:30:00+0000') == '2025-10-02'
    assert api.timestamp_to_date('bad') == ''
    assert api.timestamp_to_date(None) == ''


def test_entry_from_media_food_post():
    entry = ip.entry_from_media(PAGE_1['data'][0])
    assert entry['shortcode'] == 'NEW1'
    assert entry['date'] == '2025-10-02'
    assert entry['region'] == '台中 Taichung'
    assert entry['address'] == '台中市清水區鰲峰路257之7號'


def test_entry_from_media_without_caption():
    entry = ip.entry_from_media(PAGE_2['data'][1])
    assert entry['content'] == ''
    assert entry['address'] == ''
    assert entry['permalink'] == 'https://www.instagram.com/p/NEW3/'


def test_build_map_search_url():
    url = ip.build_map_search_url(FOOD_CAPTION, '台中市清水區鰲峰路257之7號')
    assert url.startswith('https://www.google.com/maps/search/?api=1&query=')
    assert '%E6%B5%AF%E6%B1%9F' in url  # 浯江
    assert ip.build_map_search_url('沒有地址', '') == ''


def test_extract_title():
    assert ip.extract_title('✨️#雞湯桑 #Torisan\n內容') == '雞湯桑'
    assert ip.extract_title('今天開箱') == '今天開箱'
    assert ip.extract_title('') == ''


def test_env_token_roundtrip(tmp_path, monkeypatch):
    monkeypatch.delenv(api.TOKEN_ENV_KEY, raising=False)
    env_path = tmp_path / '.env'
    with pytest.raises(api.InstagramApiError):
        api.load_access_token(env_path)
    env_path.write_text('# comment\nOTHER=1\nIG_ACCESS_TOKEN="old"\n', encoding='utf-8')
    assert api.load_access_token(env_path) == 'old'
    api.save_access_token('new', env_path)
    assert api.load_access_token(env_path) == 'new'
    assert 'OTHER=1' in env_path.read_text(encoding='utf-8')


def test_refresh_failure_keeps_old_token(tmp_path):
    session = FakeSession({'https://graph.instagram.com/refresh_access_token': FakeResponse({'error': {'message': 'too new'}}, 400)})
    assert ip.refresh_token_if_possible('OLD', session, tmp_path / '.env') == 'OLD'


def test_run_from_instagram_imports_all_and_skips_existing(tmp_path, monkeypatch):
    monkeypatch.delenv(api.TOKEN_ENV_KEY, raising=False)
    env_path = tmp_path / '.env'
    env_path.write_text('IG_ACCESS_TOKEN=TOKEN\n', encoding='utf-8')
    posts_path = tmp_path / 'posts.js'
    posts_path.write_bytes(
        "export const IG_POSTS = [\r\n    {\r\n        region: '台中 Taichung',\r\n        permalink: 'https://www.instagram.com/p/NEW3/',\r\n"
        "        date: '2025-08-01',\r\n        map: '',\r\n        content: `舊的`\r\n    }\r\n];\r\n".encode('utf-8'))

    session = media_session()
    session.responses_by_url['https://graph.instagram.com/refresh_access_token'] = FakeResponse({'access_token': 'TOKEN2', 'expires_in': 5184000})
    monkeypatch.setattr(ip.requests, 'Session', lambda: session)

    assert ip.run_from_instagram(posts_path, dry_run=False, enable_geocode=False, limit=None, env_path=env_path) == 0

    source = posts_path.read_bytes().decode('utf-8')
    assert source.count('permalink:') == 3  # NEW3 已存在被略過，新增 NEW1、NEW2
    assert source.index('NEW2') < source.index('NEW1')  # 依日期由舊到新寫入
    assert 'https://www.google.com/maps/search/?api=1&query=' in source  # 食記自動產生導航連結
    assert '\r\n' in source and '\n' not in source.replace('\r\n', '')
    assert api.load_access_token(env_path) == 'TOKEN2'
    assert (tmp_path / 'posts.js.bak').exists()


def test_run_from_instagram_reports_missing_token(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv(api.TOKEN_ENV_KEY, raising=False)
    assert ip.run_from_instagram(tmp_path / 'posts.js', True, False, None, env_path=tmp_path / '.env') == 1
    assert 'IG_ACCESS_TOKEN' in capsys.readouterr().out


def test_fetch_since_keeps_boundary_day_and_stops_paging():
    session = media_session()
    # PAGE_1 的 NEW1 是台灣時間 2025-10-02；since 當天要包含
    media_list = api.fetch_all_media('TOKEN', session, since='2025-10-02')
    assert [media['id'] for media in media_list] == ['1']
    # 第 2 頁全部早於 since → 抓完第 2 頁就停止（不會再要下一頁）
    assert len(session.calls) == 2


def test_fetch_since_stops_after_first_fully_older_page():
    session = media_session()
    assert api.fetch_all_media('TOKEN', session, since='2025-12-01') == []
    assert len(session.calls) == 1


def test_fetch_since_filters_inside_mixed_page():
    session = media_session()
    media_list = api.fetch_all_media('TOKEN', session, since='2025-08-15')
    assert [media['id'] for media in media_list] == ['1', '2']


def test_parse_since_date_validates_format():
    assert ip.parse_since_date('2026-10-01') == '2026-10-01'
    for bad_value in ['2026/10/01', '2026-13-01', 'yesterday']:
        with pytest.raises(ip.argparse.ArgumentTypeError):
            ip.parse_since_date(bad_value)


def test_cli_rejects_bad_since(capsys):
    with pytest.raises(SystemExit):
        ip.main(['--from-instagram', '--since', '2026/10/1'])
    assert 'YYYY-MM-DD' in capsys.readouterr().err
