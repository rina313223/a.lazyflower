#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Instagram 貼文資訊提取器（可連續輸入多個 URL）
執行後會提示輸入 Instagram URL，輸入 q 可離開。
"""

import requests
import re
from datetime import datetime
from bs4 import BeautifulSoup
import sys

# --- 原始函式保留 ---------------------------------------------------

def clean_instagram_url(url):
    if '?' in url:
        url = url.split('?')[0]
    if '#' in url:
        url = url.split('#')[0]
    if not url.endswith('/'):
        url += '/'
    return url

def extract_date_from_datetime(datetime_str):
    if not datetime_str:
        return datetime.now().strftime('%Y-%m-%d')
    try:
        formats = [
            '%Y-%m-%dT%H:%M:%S.%fZ', '%Y-%m-%dT%H:%M:%SZ', '%Y-%m-%dT%H:%M:%S%z',
            '%Y-%m-%dT%H:%M:%S', '%Y-%m-%d'
        ]
        for fmt in formats:
            try:
                dt_str = datetime_str.split('+')[0].split('Z')[0]
                date_obj = datetime.strptime(dt_str, fmt)
                return date_obj.strftime('%Y-%m-%d')
            except:
                continue
        m = re.search(r'(\d{4}-\d{2}-\d{2})', datetime_str)
        if m:
            return m.group(1)
    except:
        pass
    return datetime.now().strftime('%Y-%m-%d')

def extract_map_link(content):
    pattern = r'(https?://(?:maps\.google\.com|maps\.app\.goo\.gl|goo\.gl/maps)/[^\s\)]+)'
    m = re.search(pattern, content)
    return m.group(1) if m else ''

def detect_region(content):
    regions = {
        '台北 Taipei': ['台北','taipei','信義','大安','中正','松山','士林','內湖'],
        '新北 New Taipei': ['新北','板橋','中和','永和','新店','三重'],
        '桃園 Taoyuan': ['桃園','中壢'],
        '台中 Taichung': ['台中','西屯','北屯','南屯','中區','清水','北區'],
        '高雄 Kaohsiung': ['高雄','前金','新興'],
        '台南 Tainan': ['台南','安平','東區'],
        '日本 Japan': ['日本','東京','大阪','京都','沖繩']
    }
    t = content.lower()
    for r, keys in regions.items():
        for k in keys:
            if k.lower() in t:
                return r
    return '台中 Taichung'

def extract_instagram_post(url):
    headers = {
        'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
        'Accept':'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8'
    }
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        if resp.status_code != 200:
            return None
        soup = BeautifulSoup(resp.text, 'html.parser')
        # date
        date_str = ''
        for t in soup.find_all('time'):
            if t.get('datetime'):
                date_str = t.get('datetime')
                break
        # content
        content = ''
        meta = soup.find('meta', property='og:description')
        if meta:
            full_content = meta.get('content','')
            # 從 ✨️ 後面開始提取
            split_content = re.split(r'✨️', full_content)
            content = split_content[1].strip() if len(split_content) > 1 else full_content.strip()
            # 去掉最後的雙引號（如果有）
            if content.endswith('.\".'):
                content = content[:-1].strip()
        return {'date':date_str, 'content':content}
    except:
        return None

# --- 修正版 format_output（避免 f-string 與大括號問題） ------------

def format_output(permalink, content, date, map_link='', region=None):
    clean_url = clean_instagram_url(permalink)
    formatted_date = extract_date_from_datetime(date)
    region = region or detect_region(content)
    map_link = map_link or extract_map_link(content)

    template = (
"            {{\n"
"                region: '{region}',\n"
"                permalink: '{permalink}',\n"
"                date: '{date}',\n"
"                map: '{map}',\n"
"                content: `{content}`\n"
"            }} ,"
    )

    return template.format(
        region=region,
        permalink=clean_url,
        date=formatted_date,
        map=map_link,
        content=content.replace('`','\``')
    )

# --- 主程式（可連續輸入 URL） --------------------------------------

def main():
    print("Instagram 貼文資訊提取器（連續模式）")
    print("輸入 Instagram 貼文網址（輸入 q 離開）\n")

    while True:
        try:
            url = input("請輸入 IG 貼文網址: ").strip()
        except (EOFError, KeyboardInterrupt):
            print('\n已離開程式')
            break

        if url.lower() == 'q':
            print('已離開程式')
            break
        if 'instagram.com' not in url:
            print('❌ 請輸入有效的 Instagram URL\n')
            continue

        url = clean_instagram_url(url)
        print('⏳ 正在提取...')
        data = extract_instagram_post(url)

        if not data:
            print('❌ 提取失敗，可能需要登入或貼文不存在\n')
            continue

        output = format_output(url, data['content'], data['date'])
        print('\n=== 提取結果 ===')
        print(output)
        print('===============\n')

if __name__ == '__main__':
    main()
