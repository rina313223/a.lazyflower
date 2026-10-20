# -*- coding: utf-8 -*-
"""
Instagram 官方 API（Instagram API with Instagram Login）存取：
讀取自己帳號的所有貼文、延長 long-lived token。
設定步驟見 tools/INSTAGRAM_API_SETUP.md。
"""

import os
from datetime import datetime, timezone, timedelta
from pathlib import Path

import requests

GRAPH_BASE_URL = 'https://graph.instagram.com'
MEDIA_FIELDS = 'id,caption,permalink,timestamp,media_type'
PAGE_SIZE = 50
HTTP_TIMEOUT_S = 20
TOKEN_ENV_KEY = 'IG_ACCESS_TOKEN'
DEFAULT_ENV_PATH = Path(__file__).resolve().parent / '.env'
TAIPEI_TZ = timezone(timedelta(hours=8))


class InstagramApiError(RuntimeError):
    pass


# ---------- token 設定檔 ----------

def read_env_file(env_path):
    values = {}
    if not env_path.exists():
        return values
    for line in env_path.read_text(encoding='utf-8').splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith('#') or '=' not in stripped:
            continue
        key, value = stripped.split('=', 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def load_access_token(env_path=DEFAULT_ENV_PATH):
    token = os.environ.get(TOKEN_ENV_KEY) or read_env_file(env_path).get(TOKEN_ENV_KEY, '')
    if not token:
        raise InstagramApiError(
            f'找不到 {TOKEN_ENV_KEY}。請依 tools/INSTAGRAM_API_SETUP.md 取得 token，'
            f'並寫進 {env_path.name}（可複製 .env.example）'
        )
    return token


def save_access_token(token, env_path=DEFAULT_ENV_PATH):
    lines = env_path.read_text(encoding='utf-8').splitlines() if env_path.exists() else []
    replaced = False
    for index, line in enumerate(lines):
        if line.strip().startswith(f'{TOKEN_ENV_KEY}='):
            lines[index] = f'{TOKEN_ENV_KEY}={token}'
            replaced = True
    if not replaced:
        lines.append(f'{TOKEN_ENV_KEY}={token}')
    env_path.write_text('\n'.join(lines) + '\n', encoding='utf-8')


# ---------- API 呼叫 ----------

def _get_json(session, url, params=None):
    try:
        response = session.get(url, params=params, timeout=HTTP_TIMEOUT_S)
    except requests.RequestException as error:
        raise InstagramApiError(f'連線 Instagram API 失敗：{error}') from error
    try:
        payload = response.json()
    except ValueError as error:
        raise InstagramApiError(f'Instagram API 回傳非 JSON（HTTP {response.status_code}）') from error
    if not response.ok or 'error' in payload:
        message = payload.get('error', {}).get('message', f'HTTP {response.status_code}')
        raise InstagramApiError(f'Instagram API 錯誤：{message}')
    return payload


def fetch_all_media(token, session, limit=None):
    """依分頁取回所有貼文（新到舊）。limit 可限制最多取幾篇。"""
    media_list = []
    url = f'{GRAPH_BASE_URL}/me/media'
    params = {'fields': MEDIA_FIELDS, 'limit': PAGE_SIZE, 'access_token': token}
    while url:
        payload = _get_json(session, url, params)
        media_list.extend(payload.get('data', []))
        if limit and len(media_list) >= limit:
            return media_list[:limit]
        url = payload.get('paging', {}).get('next')
        params = None  # next 連結已包含所有參數
    return media_list


def refresh_access_token(token, session):
    """延長 long-lived token 效期（60 天）。token 需發出超過 24 小時才能延長。"""
    payload = _get_json(session, f'{GRAPH_BASE_URL}/refresh_access_token',
                        {'grant_type': 'ig_refresh_token', 'access_token': token})
    return payload.get('access_token', ''), payload.get('expires_in', 0)


def refresh_and_store_token(token, session, env_path=DEFAULT_ENV_PATH):
    """延長 token；若 token 來自 .env（非環境變數）則寫回 .env。回傳 (目前有效 token, 剩餘秒數)。"""
    new_token, expires_in = refresh_access_token(token, session)
    if not new_token:
        return token, 0
    if not os.environ.get(TOKEN_ENV_KEY):
        save_access_token(new_token, env_path)
    return new_token, expires_in


# ---------- 資料轉換 ----------

def timestamp_to_date(timestamp):
    """'2025-10-02T04:30:00+0000' → 台灣時間的 '2025-10-02'。"""
    try:
        moment = datetime.strptime(timestamp, '%Y-%m-%dT%H:%M:%S%z')
    except (TypeError, ValueError):
        return ''
    return moment.astimezone(TAIPEI_TZ).strftime('%Y-%m-%d')
