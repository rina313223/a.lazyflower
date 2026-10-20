# 取得 Instagram API token（一次性設定）

`python tools/import_posts.py --from-instagram` 使用 Instagram 官方的「Instagram API with Instagram Login」讀取自己帳號的貼文。
只需設定一次；之後每次執行工具都會自動延長 token 效期。

> Meta 後台介面偶爾改版，按鈕名稱可能略有不同，以下以 2025 年的介面為準。

## 前置條件
- IG 帳號為 **創作者** 或 **商業** 帳號（a.lazyflower 已是創作者帳號 ✅）
- 一個 Facebook 帳號（用來登入 Meta for Developers）

## 步驟

1. 到 <https://developers.facebook.com/apps> 登入，按 **建立應用程式（Create App）**
2. 使用案例選 **「管理 Instagram 上的訊息和內容」**（Manage messaging & content on Instagram），名稱隨意（例如 `lazyflower-site`）
3. 建立後進入 App 後台 → **Instagram** → **API setup with Instagram login**（使用 Instagram 登入的 API 設定）
4. 在 **「產生存取權杖（Generate access tokens）」** 區塊按 **新增帳號（Add account）**，用 a.lazyflower 登入並允許權限
   - 只需要 `instagram_business_basic` 權限
5. 帳號出現後按 **產生權杖（Generate token）**，複製產生的 token（這是 60 天效期的 long-lived token）
6. 把 `tools/.env.example` 複製成 `tools/.env`，貼上：
   ```
   IG_ACCESS_TOKEN=你複製的token
   ```

App 保持「開發中（Development）」模式即可，不需要送審 —— 只有你自己的帳號會使用。

## 使用

```bash
# 先試跑：只抓最新 5 篇、不寫檔
python tools/import_posts.py --from-instagram --limit 5 --dry-run

# 正式匯入所有貼文（已存在的會自動略過）
python tools/import_posts.py --from-instagram
```

## 常見問題

| 訊息 | 原因／解法 |
|---|---|
| `找不到 IG_ACCESS_TOKEN` | 還沒建立 `tools/.env`，見步驟 6 |
| `Invalid OAuth access token` / `Session has expired` | token 過期（超過 60 天沒執行工具），重做步驟 5–6 |
| `token 未延長（...）` | token 發出未滿 24 小時無法延長，屬正常，不影響匯入 |

⚠️ token 等同於帳號的讀取權限，**不要**貼到聊天、截圖或 commit 進 git。
