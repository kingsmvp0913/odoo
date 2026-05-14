# AI 開發管線 (V3 · Windows)

## 架構總覽

```
Odoo Task API
     │ curl.py (analysis.ps1 呼叫)
     ▼
┌─────────┐   analysis.ps1    ┌──────────┐   analysis.ps1    ┌─────────────┐
│  start/ │ ──────────────► │ confirm/ │ ──────────────►  │ testcoding/ │
└─────────┘  (START→CONFIRM) └──────────┘ (CONFIRM→TESTCODING) └─────────────┘
                              (等待填答)                        │ test_coding.ps1
                              MODE_A ↺                         │ (紅燈驗證)
                                                               ▼
                           ┌──────────┐   coding.ps1    ┌──────────┐
                           │  final/  │ ◄────────────── │ coding/  │
                           └──────────┘  (綠燈後推進)   └──────────┘
                                                         (單次執行，RED → 人工重試)

失敗時：testcoding/ → blocker.txt → rollback → confirm/
        coding/ RED → error.log 更新 → 人工重跑 coding.ps1
```

---

## 腳本說明

| 腳本 | Agent 模型 | 功能 |
|------|-----------|------|
| `analysis.ps1` | Sonnet | ① Odoo API 同步任務至 start/；② 呼叫 requirements-analyst → confirm/；③ 使用者填答後重新呼叫 → 驗證 MODE_B → 推進 testcoding/ |
| `test_coding.ps1` | Sonnet | 呼叫 test-agent 生成測試骨架；嚴格紅燈驗證後推進 coding/ |
| `coding.ps1` | Haiku | 呼叫 senior-software-engineer 實作；綠燈後推進 final/；RED 時更新 error.log 等待人工重跑 |

### analysis.ps1 — 兩階段流程

**階段一：START → CONFIRM**
1. 讀取 `project_version_map.json`，自動對應任務專案名稱至 `odoo_version`
2. 注入 `versionHint` 到 Prompt，強制 Agent 跳過 odoo_version 提問（`DO NOT QUESTION`）
3. 呼叫 requirements-analyst，解析 `---BEGIN_JSON---/---END_JSON---` 輸出標記
4. 驗證 `execution_mode` 及 `state_summary` 欄位存在
5. 原子寫入 `analysis.json`；移動 task 檔案至 `confirm/<case>/`

**階段二：CONFIRM → TESTCODING**
1. 掃描 confirm/ 下所有案件的 `analysis.json`
2. 若 `clarification_channel` 有未填答的 active 問題 → `[WAIT]`
3. 有填答 → 呼叫 Agent 重新分析（`re-check`）
4. 重分析前建立 `analysis.json.bak`；失敗時自動還原（backup/restore 機制）
5. MODE_B + `is_complete=true` + `has_blocking_unknowns=false` + `odoo_version` 非空 → 推進 testcoding/

### coding.ps1 — 單次執行模式（Windows 分支）

- 使用 `slim_spec.py` 壓縮 `analysis.json` 後再送 Agent（減少 token 用量）
- 單次呼叫 Haiku；**無自動重試迴圈**
- 測試 RED → 更新 `logs/error.log` → 人工確認後重新執行 `coding.ps1`
- 測試 GREEN → 移至 `final/`

---

## 共用函式庫 (`_common.ps1`)

| Function | 說明 |
|----------|------|
| `Acquire-Lock` | 建立 JSON 格式鎖檔（含 PID/Host/TTL）；偵測已死 Process 或過期鎖並自動清理 |
| `Release-Lock` | 僅允許持有鎖的同一 PID+Host 釋放 |
| `Get-IniVal` | 從 ini 格式文字中讀取指定 key 值 |
| `Get-OdooConf` | 讀取 `odoo-{ver}/odoo.conf`（含 `test_db_name`）；三個候選路徑依序搜尋 |
| `Convert-MultiFileTags` | 解析 AI 的 `@FILE:path` / `@FILE_END` 格式輸出；格式錯誤時儲存 `ai_raw_output_*.txt` 並標示 `[FATAL]` |
| `Write-PipelineFile` | 管線日誌原子寫入（tmp → Move）；自動建立父目錄 |
| `Out-AtomicFile` | AI 產出程式碼原子寫入；路徑白名單守衛 + `GetFullPath` 逃逸檢查；寫入位置依 `odoo_version` 決定為 `odoo-{ver}/` |
| `Invoke-ClaudeAgentStream` | 串流顯示 Claude 輸出（不捕獲，僅即時顯示，用於互動式 agent 模式）|
| `Invoke-ClaudeStream` | 串流 + 捕獲；Async stderr 防死鎖；最多 3 次指數退避重試；回傳完整輸出字串 |
| `Run-TestProcess` | 無 shell 執行測試；Async stdout/stderr 防死鎖；60 秒 timeout；回傳 `{ExitCode, Output}` |

### `Invoke-ClaudeStream` vs `Invoke-ClaudeAgentStream`

| | `Invoke-ClaudeStream` | `Invoke-ClaudeAgentStream` |
|---|---|---|
| 模式 | `-p`（Print，非互動）| 無 `-p`（Agent SDK 模式）|
| 輸出 | 串流顯示 + 回傳字串 | 僅串流顯示，不回傳 |
| 重試 | 最多 3 次指數退避 | 無重試 |
| 用途 | test_coding.ps1 / coding.ps1 | 互動式 agent 呼叫 |

---

## Agents

| Agent | 模型 | 用途 |
|-------|------|------|
| `requirements-analyst.md` | Sonnet | 需求轉 JSON spec（MODE_A/B）；輸出包在 `---BEGIN_JSON---/---END_JSON---` 標記內 |
| `test-agent.md` | Sonnet | 依 analysis.json 生成測試骨架；輸出 `@FILE:/@FILE_END` 格式；Odoo 最多 10 檔 |
| `senior-software-engineer.md` | Haiku | 依 traceback 實作程式碼；僅可寫 `custom_addons/<module>/`；遇規格矛盾立即寫 `blocker.txt` |

### requirements-analyst 模式規則

- **MODE_A**：有 blocking unknowns 或 user_answer 未填 → 持續輸出 clarification_channel，技術欄位標 `PENDING_CLARIFICATION`
- **MODE_B**：所有 active 問題（category ≠ "obsolete"）均有有效填答 → 完整填寫 `technical_specification`
- `odoo_version` 由 `project_version_map.json` 自動注入，Agent 視為確定事實，不得產生對應澄清問題

---

## 管線規則

### 鎖機制（雙層）

```
global_analysis.lock    ← analysis.ps1 第一階段（START→CONFIRM）
global_recheck.lock     ← analysis.ps1 第二階段（CONFIRM→TESTCODING）
global_testcoding.lock  ← test_coding.ps1
global_coding.lock      ← coding.ps1
    └─ 每個案件另有 process.lock（案件層級鎖）
```

- 鎖檔格式：`{ pid, host, created, ttlSeconds }`；過期（>TTL）或 Process 已死則自動清除

### TDD 強制流程

```
testcoding/ (紅燈驗證)                 coding/ (綠燈驗證)
    ├─ isExitCodeFail == true              ├─ ExitCode == 0
    ├─ isLogContainsFailure == true        ├─ Output 含 "Ran X tests"
    ├─ hasTestRun == true ("Ran X tests")  └─ Output 無 FAIL/ERROR/Traceback
    └─ isZeroTestsRun == false
```

- 測試跑 0 個 → BLOCKER：`Ran 0 tests`
- 意外綠燈 → BLOCKER：`測試意外通過（綠燈）`

### 路徑安全守衛（雙重）

1. **白名單前置檢查**（`Out-AtomicFile`）：Odoo 路徑必須以 `custom_addons/<module>/` 開頭；Generic 路徑必須在 `tests/` 或 `src/`
2. **逃逸防護**（Windows 分支新增）：`GetFullPath` 解析後驗證最終路徑仍在 `$baseDir` 範圍內
3. **呼叫端檢查**（`coding.ps1`）：拒絕含 `..`、以 `/` 開頭、或以磁碟代號 `[A-Za-z]:\` 開頭的路徑

---

## 組態需求

### `project_version_map.json`（必要）

```json
{
  "project_version_map": {
    "專案名稱（與 Odoo task project 欄位完全一致）": "17.0"
  }
}
```

路徑：`C:\odoo\.claude\project_version_map.json`

### `odoo-{ver}/odoo.conf`（Odoo 專案必要）

| 設定 | 用途 |
|------|------|
| `db_host` | PostgreSQL 主機 |
| `db_port` | PostgreSQL 連接埠 |
| `db_user` | 資料庫使用者 |
| `db_password` | 資料庫密碼 |
| `test_db_name` | **測試專用資料庫名稱**（缺少此項 → 拒絕執行）|

`Get-OdooConf` 搜尋順序：
1. `odoo-{ver}/odoo.conf`
2. `odoo-{ver}/debian/odoo.conf`
3. `odoo-{ver}/server/odoo.conf`

### 環境變數

```powershell
[Environment]::SetEnvironmentVariable("ODOO_PASSWORD", "您的密碼", "User")
```

未設定 → analysis.ps1 立即 `exit 1`

---

## 目錄結構

```
.claude/kingsmvpsplan/
├── start/                  # Odoo API 同步的原始任務檔（task_<id>.txt）
├── confirm/
│   └── task_<id>/
│       ├── analysis.json         # 需求分析 JSON（MODE_A 等待填答）
│       ├── analysis.json.bak     # 重新分析前備份（失敗自動還原）
│       ├── task_<id>.txt         # 原始任務文字
│       ├── patches/              # 預留
│       └── process.lock
├── testcoding/
│   └── task_<id>/
│       ├── analysis.json
│       ├── custom_addons/        # AI 生成的測試骨架（寫至 odoo-{ver}/）
│       ├── logs/error.log        # 紅燈測試錯誤詳情（傳入 coding 階段）
│       └── process.lock
├── coding/
│   └── task_<id>/
│       ├── analysis.json
│       ├── logs/error.log        # 最新一次失敗 traceback
│       ├── debug/
│       │   ├── prompt_<ts>_attempt1.txt    # 傳入 Agent 的完整 Prompt
│       │   └── output_<ts>_attempt1.txt    # Agent 原始輸出
│       └── process.lock
├── final/
│   └── task_<id>/                # 通過綠燈，等待人工驗證與佈署
└── global_*.lock                 # 全域鎖
```

---

## 快速排查

| 現象 | 可能原因 | 解法 |
|------|----------|------|
| `[CONFIG REQUIRED]` | 專案名稱不在 `project_version_map.json` | 新增對應記錄後重跑 |
| `[WAIT]` 停在 confirm/ | `clarification_channel` 有未填的 `user_answer` | 編輯 `analysis.json` 填入答案後重跑 analysis.ps1 |
| `[BLOCKER] Ran 0 tests` | 測試 class 未繼承 `TransactionCase`，或 module tag 錯誤 | 手動刪除 testcoding/task_id/ 後重跑 |
| `[BLOCKER] 測試意外通過` | 骨架實作了實際邏輯，違反 TDD | 確認 test-agent 的 models.py 為純骨架 |
| `[RED] 測試未通過` | coding.ps1 單次執行未成功 | 確認 `logs/error.log` 後重新執行 `coding.ps1` |
| `slim_spec.py failed` | `slim_spec.py` 不存在或 Python 環境問題 | 確認 `C:\odoo\.claude\slim_spec.py` 存在 |
| `analysis.json.bak` 殘留 | 重分析失敗（已有自動還原機制）| 確認 `analysis.json` 正確後刪除 .bak |
