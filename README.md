👋 關於我

嗨！我是一朵懶懶花🌸

喜愛發掘生活中的美好🙋‍♀️
小鳥胃●螞蟻人●挑食鬼👻 食記主觀紀錄😉
📮互惠/合作邀約歡迎私訊
⚠️未經同意勿轉載圖文

IG: a.lazyflower
https://www.instagram.com/a.lazyflower/

Threads: a.lazyflower
https://www.threads.com/@a.lazyflower
---

## 🛠 維護說明

### 從 Instagram 自動匯入（推薦）
第一次使用請先依 [tools/INSTAGRAM_API_SETUP.md](tools/INSTAGRAM_API_SETUP.md) 取得 token，之後只要：

```
python tools/import_posts.py --from-instagram
```

會抓取帳號所有貼文、略過已存在的文章、自動補日期／地區／座標與 Google 導航連結。可加 `--dry-run` 先預覽、`--limit 5` 只抓最新幾篇。

### 手動貼上匯入（備用）
1. 第一次執行 `python tools/import_posts.py` 會自動建立 `tools/inbox.txt`
2. 在 inbox.txt 貼上：第一行 IG 網址、`map: Google 地圖分享連結`（選填但建議）、接著整段貼文內容；多篇用 `---` 分隔
3. 先 `python tools/import_posts.py --dry-run` 預覽，再不加參數執行寫入（會自動備份 `posts.js.bak`、封存 inbox）

日期會由 IG 短碼自動推算（可用 `date:` 覆寫）、地區由地址判斷（可用 `region:` 覆寫）、座標由地圖連結或地址自動取得。

### 幫舊文章補座標
`python tools/import_posts.py --backfill`

### 測試
- `node --test tests/postParser.test.mjs`
- `python -m pytest tools/`
