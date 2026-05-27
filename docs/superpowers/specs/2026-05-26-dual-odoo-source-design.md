# 雙 Odoo 來源設計文件（WIP）

**狀態**：已實作（2026-05-27）

---

## 需求摘要

目前 `curl.py` 只從單一 Odoo 實例抓任務，建立 `task_{id}/` 目錄。
需求：支援兩個獨立 Odoo 實例，任務目錄依來源加前綴區分。

| 來源 | 前綴 | 範例目錄名 |
|------|------|-----------|
| 原有 Odoo（ideaxpress） | `task_odoo_` | `task_odoo_123` |
| 新 Odoo service 實例 | `task_service_` | `task_service_456` |

**注意**：現有 `task_{id}` 目錄**保留不改名**，只有新抓進來的才用新前綴。

---

## 已確認決策

1. **新來源系統類型**：完全不同的 Odoo 實例（不同 URL）
2. **認證儲存方式**：全部用環境變數
3. **現有目錄遷移**：保留舊命名，不做一次性遷移

---

## 已確認方案：方案 A — `curl.py` 加 prefix 參數

`analysis.ps1` 的 STEP 1 連續呼叫兩次 `curl.py`，各自傳不同前綴和來源設定。
任一來源失敗只會 `[WARN]`，不中斷整個 pipeline。

### 改動範圍

| 檔案 | 改動說明 |
|------|---------|
| `_common.ps1` | 新增 `$ODOO_SERVICE_URL/DB/USERNAME/USER_ID` 五個常數（從 env vars 讀） |
| `curl.py` | 新增 `prefix` 位置參數；目錄名改為 `{prefix}_{id}` |
| `analysis.ps1` | STEP 1 呼叫 `curl.py` 兩次；各自維護 prefix-specific skip list |
| `send_message.py` | 新增 `source` 參數（`odoo`/`service`）路由到對的 Odoo 實例 |
| `_pipeline_run.ps1` | task ID regex `^task_\d+$` → `^task_(odoo_\|service_\|)\d+$` |

### 環境變數規劃（待補齊）

**來源 1（odoo）** — 沿用現有，補充 URL/DB/USERNAME 改為 env var：
```
ODOO_URL         （目前寫死 https://odoo.ideaxpress.biz）
ODOO_DB          （目前寫死 odoo）
ODOO_USERNAME    （目前寫死 steven.lin@ideaxpress.biz）
ODOO_USER_ID     （已有，預設 79）
ODOO_PASSWORD    （已有）
```

**來源 2（service）** — 全新：
```
ODOO_SERVICE_URL
ODOO_SERVICE_DB
ODOO_SERVICE_USERNAME
ODOO_SERVICE_USER_ID
ODOO_SERVICE_PASSWORD
```

---

## 確認結果（2026-05-27）

- [x] 來源 1 URL/DB/USERNAME 保持寫死，只有密碼用 env var（現狀不變）；service 來源同理（`ODOO_SERVICE_PASSWORD` 為 env var）
- [x] `send_message.py` 路由：service 來源 early return（目前不發通知）；odoo 來源支援 `task_N` 和 `task_odoo_N` 兩種格式
- [x] Task ID regex 更新為 `^task_(odoo_|service_)?\d+$`
- [x] `service.question.feedback` 模型以獨立的 `curl_service.py` 處理（欄位：name_seq、subject、question_description、system、state、classification）

---

## 相關檔案

- `C:\odoo\.claude\tools\curl.py` — 任務抓取腳本
- `C:\odoo\.claude\scripts\_common.ps1` — Odoo 連線常數（L24-L28）
- `C:\odoo\.claude\scripts\analysis.ps1` — STEP 1 同步邏輯（L20-L45）
- `C:\odoo\.claude\scripts\_pipeline_run.ps1` — task ID regex（L31、L251）
- `C:\odoo\.claude\tools\send_message.py` — 訊息回傳
