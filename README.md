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

### 網站結構
| 路徑 | 用途 |
|---|---|
| `index.html` | 首頁（卡片列表＋地圖＋詳情抽屜） |
| `posts.js` | 所有文章資料（`region`、`permalink`、`date`、`map`、選填 `lat`/`lng`、`content`） |
| `css/style.css` | 樣式 |
| `js/` | 前端模組（解析、篩選、卡片、地圖、抽屜、動畫） |
| `tools/import_posts.py` | 匯入文章、補座標、缺座標報表 |
| `tools/instagram_api.py` | Instagram 官方 API 存取 |
| `tests/`、`tools/test_*.py` | 測試 |

本機預覽（需透過 http 開啟，直接雙擊 html 無法載入模組）：

```
python -m http.server 8000
```

再開啟 <http://localhost:8000/>

### 日常更新流程
```
python tools/import_posts.py --from-instagram --since 2026-10-01 --dry-run   
# 1. 預覽
python tools/import_posts.py --from-instagram --since 2026-10-01             
# 2. 匯入
python tools/import_posts.py --report-missing --csv                          
# 3. 檢查哪些沒上地圖
git add posts.js                        
python tools/import_posts.py --backfill #轉成座標                                     
# 4. 上線（PowerShell 不支援 &&，請分行執行）
git add -A
git commit -m "更新文章"
git push
```

### 地圖座標
- 補座標：`python tools/import_posts.py --backfill`（只處理還沒有 `lat`/`lng` 的文章）
- 找出不在地圖上的文章：`python tools/import_posts.py --report-missing`，加 `--csv` 另存 `tools/missing_coordinates.csv`（可用 Excel 開）
  - 「查不到座標」：有地址但查不到，多為食記，建議補
  - 「無地址」：多為開箱、生活類，可不補
- 手動補法：Google 地圖找到店家 →「分享」複製 `maps.app.goo.gl` 連結 → 貼到 posts.js 該篇的 `map: '...'` → 執行 `--backfill`（取得精確座標）
- 地區標錯時（例如日本的店被標成台中），直接修改該篇 `region`，例如 `'日本 Japan'`

查詢規則：Google 地圖分享連結最準；台灣地址會去掉郵遞區號與村里後以「路段, 行政區, 縣市」查詢（精確到路段）；日本地址以郵遞區號查詢（精確到町丁目）。

### 從 Instagram 自動匯入（推薦）
第一次使用請先依 [tools/INSTAGRAM_API_SETUP.md](tools/INSTAGRAM_API_SETUP.md) 取得 token 並存到 `tools/.env`。

```
python tools/import_posts.py --from-instagram                     # 抓全部貼文
python tools/import_posts.py --from-instagram --since 2026-10-01  # 只匯入 2026-10-01（含）以後的貼文
python tools/import_posts.py --from-instagram --limit 5           # 只抓最新 5 篇
```

- 已存在的文章（以 IG 短碼判斷）會自動略過，重複執行不會產生重複文章
- `--since` 以台灣時間判斷，當天的貼文會包含在內；遇到更舊的貼文就停止翻頁，速度較快
- 日期取自 IG 發文時間；地區由地址判斷；座標由地址自動查詢；有地址的食記會自動產生 Google 導航連結
- 每次執行會自動延長 token 效期（60 天），超過 60 天沒執行需重新取得 token

### 手動貼上匯入（備用）
1. 第一次執行 `python tools/import_posts.py` 會自動建立 `tools/inbox.txt`
2. 在 inbox.txt 貼上：第一行 IG 網址、`map: Google 地圖分享連結`（選填但建議）、接著整段貼文內容；多篇用 `---` 分隔
3. 先 `python tools/import_posts.py --dry-run` 預覽，再不加參數執行寫入（會自動封存 inbox）

日期會由 IG 短碼自動推算（可用 `date:` 覆寫）、地區由地址判斷（可用 `region:` 覆寫）、座標由地圖連結或地址自動取得。

### 所有參數
| 參數 | 說明 |
|---|---|
| （無） | 匯入 `tools/inbox.txt` |
| `--from-instagram` | 從 IG 官方 API 匯入 |
| `--since YYYY-MM-DD` | 搭配 `--from-instagram`：只匯入該日（含）以後的貼文 |
| `--limit N` | 搭配 `--from-instagram`：最多抓 N 篇（新到舊） |
| `--dry-run` | 只預覽，不寫檔 |
| `--no-geocode` | 不查座標（較快，之後可用 `--backfill` 補） |
| `--backfill` | 幫缺座標的文章補 `lat`/`lng` |
| `--report-missing` | 列出不在地圖上的文章（只讀） |
| `--csv` | 搭配 `--report-missing`：另存 CSV |

寫入 posts.js 前會自動備份成 `posts.js.bak`。

### 不會被 commit 的檔案
`tools/.env`（IG token，請勿外流）、`posts.js.bak`、`tools/inbox.txt`、`tools/inbox_history/`、`tools/missing_coordinates.csv`

### 測試
```
node --test tests/postParser.test.mjs
python -m pytest tools/
```
