# Kingsmvps Pipeline (V8.2)

輸入「**開工**」，Claude 自動完成需求分析 → 實作 → QA，無需手動確認。

---

## 安裝

### 前置需求

- PowerShell 7+（`pwsh`）
- Python 3.x
- Claude Code CLI（已登入）
- Odoo 實例（任務來源）

### 設定步驟

1. **設定環境變數**（在 PowerShell profile 或 Claude terminal 執行）

   ```powershell
   $env:ODOO_PASSWORD = "your_password"     # 必要
   $env:ODOO_USER_ID  = "79"                # 可選，預設 79
   $env:ONLINE_ADDONS_DIR = "C:\online_addons"  # 可選，預設 C:\online_addons
   ```

2. **確認 `settings.json` hook 已啟用**（`.claude/settings.json` 已包含，無需手動操作）

3. **確認 `project_version_map.json` 已填寫**（`.claude/project_version_map.json`，專案與 Odoo 版本對照）

> `ODOO_PASSWORD` 未設定時 `_pipeline_run.ps1` 立即中止。

---

## 怎麼用

1. 在 Odoo 建立任務
2. 在 Claude 輸入「**開工**」
3. 等待完成（任務出現在 `final/` 即代表通過 QA）

有 `user_answer` 需要填寫時（MODE_A 或 MODE_B 低信心度），Claude 會暫停等你在 `analysis.yaml` 填完後再繼續。

> **MODE_B 低信心度**：即使所有問題都已答覆，若生成規格的信心度低於 0.9，Claude 會補提新問題並退回 `confirm/` 等待補充，不會強行進入實作階段。

---

## 任務流向

```
Odoo 任務
   ↓ 自動同步 (tools/curl.py)
start/       新任務
   ↓ Claude 需求分析 (requirements-analyst)
confirm/     等待 user_answer（MODE_A）或自動通過（MODE_B）
   ↓ 答案完整後 → .answer_done
analysis/    Claude 產出完整技術規格（MODE_B）
   │  ├─ confidence >= 0.9 → .final_done → 進入 coding
   │  └─ confidence < 0.9  → .low_confidence → 退回 confirm/（補提問題）
   ↓ Claude 實作 (senior-software-engineer)
coding/      實作中 (.implement_done)，完成後 Claude 自動執行 QA
   ↓ QA 通過 (.qa_done)
final/       ✓ 完成（已歸檔）
```

QA 失敗智慧退回：
- 若 `analysis.yaml` 已含 `technical_specification` → 保留 `.analysis_done` + `.answer_done`，退回 `analysis/` 重新實作（省略重跑分析）
- 否則 → 完整退回 `confirm/`，清除所有標記重跑

---

## Stage 標記一覽（Unified Marker Table）

| Stage | .pending_* flag | Done marker | 物理目錄 |
|---|---|---|---|
| analysis (初始) | `.pending_analysis` | `.analysis_done` | `confirm/` |
| answer-check | (PS1 自動，無 pending) | `.answer_done` | `confirm/` → `analysis/` |
| final (MODE_B) | `.pending_final` | `.final_done` | `analysis/` |
| final 低信心度 | (PS1 偵測 .low_confidence) | `.low_confidence` → 退回 confirm/ | `analysis/` → `confirm/` |
| coding | `.pending_coding` | `.implement_done` | `coding/` |
| qa | `.pending_qa` | `.qa_done` | `coding/` |
| archive | — | — | `final/` |

---

## 多工說明

同一階段有多個任務時，Claude 自動並行處理（最多 5 個並行）：

- **需求分析 / confirm**：最多 5 個並行
- **實作 / QA**：同模組序列，不同模組並行（避免檔案衝突）

---

## QA 檢查項目

| 類型 | 項目 |
|------|------|
| 規格合規 | Model、Field、View、Security 符合 analysis.yaml |
| 程式品質 | 不得在迴圈內查詢、不得用裸 SQL、`sudo()` 必須有說明 |
| 程式品質 | compute + store 必須有 depends、不得硬編碼 ID、不得用裸 except |

---

## Blocker 類型

| 檔案 | 情境 | 處置方式 |
|------|------|---------|
| `blocker.spec.txt` | 規格不清，需澄清 | 讀檔後填寫決策，刪除 blocker 檔，重新觸發 |
| `blocker.tech.txt` | 技術上不可行 | 調整需求或接受替代方案，刪除 blocker 檔 |
| `blocker.agent.txt` | Agent 執行錯誤 | 查看錯誤內容，修正後手動重跑 |
| `blocker.loop.txt` | 循環超過安全上限 | 查看原因，手動清理後重新執行 |

Blocker 模板在 `.claude/templates/` 目錄。

---

## 遇到問題

| 狀況 | 處置 |
|------|------|
| Claude 停下來說有 blocker | 查看對應任務目錄的 blocker 檔路徑，修復後 `touch system/.blocker_resolved`，再輸入「開工」 |
| MODE_A 等待填寫 | 打開 `confirm/task_N/analysis.yaml`，填寫所有 `user_answer` 欄位（單行純量，不可用 YAML literal block）|
| MODE_B 低信心退回 | 同上；Claude 新增的問題也在 `analysis.yaml` 的 `clarification_channel` 裡 |
| QA 一直失敗 | 查看 `coding/task_N/log/qa_report.yaml` 的 issues 說明 |
| Pipeline 沒有自動觸發 | 確認 `_PIPELINE_WAITING` flag 是否存在且未超過 30 分鐘 |
| 任務卡住診斷 | `find .claude/kingsmvpsplan -name "blocker.*.txt"` 一行查所有 blocker |
| Odoo 任務沒收到完成通知 | 設定環境變數 `ODOO_PASSWORD`；未設定時通知靜默跳過 |

---

## V8.2 主要優化

### MCP Budget 強制執行
每個 Sub-Agent prompt 注入 `[MCP-BUDGET]` block，防止 session 內無限重試：
- Serena 查詢上限：3 次 / session；`tool_use_error` → 立即寫 `blocker.agent.txt`，禁止 retry
- Context7 任何失敗 → 靜默跳過
- WIKI-CACHE 上限：60 行（由 PS1 注入，Sub-Agent 不重複讀取）

### WIKI-CACHE 注入機制
PS1 在寫入 `pending_prompt.txt` 前讀取 `graphify-out/wiki/index.md`，抽取與目標模組相關的行（上限 60 行），以 `[WIKI-CACHE]...[/WIKI-CACHE]` 格式 prepend。wiki 不存在則跳過。

### MODE_B Confidence 評分
MODE_B 完成後須評估 `confidence`（0.0–1.0）：
- `confidence >= 0.9` → 寫 `.final_done`，`state_summary.is_complete: true`，正常推進 coding
- `confidence < 0.9` → 寫 `.low_confidence`，PS1 自動退回 `confirm/`（刪除 `.answer_done`），等待使用者補充答覆

### Smart Rollback（QA 失敗智慧復原）
QA 失敗時依分析完整度決定退回深度：
- `analysis.yaml` 已含 `technical_specification` → 保留 `.analysis_done` + `.answer_done`，退回 `analysis/` 直接重跑 coding（省略重新分析）
- 否則 → 完整退回 `confirm/`，清除所有標記

### Blocker Resume 機制
解決 blocker 後只需 `touch system/.blocker_resolved`，下次執行「開工」自動清除對應的 `blocker.*.txt` 並重新入佇列。

### NO_CHANGE_NEEDED / ALREADY_IMPLEMENTED 短路
Coding 階段若 `analysis.yaml` 含此標記 → 直接寫 `.implement_done`，跳過 AI 實作，省略 coding token。

### Agent Template 去重（Token 效率）
KNOWLEDGE RETRIEVAL + Completion Protocol 已從 3 個 agent template 移除，改由 PS1 在 `pending_prompt.txt` 中統一注入，節省每次呼叫的重複 context。

### ultrathink 範圍控制
`ultrathink` prefix 僅在 STEP 3b（MODE_B 終版規格生成）注入；coding/QA 不使用。

---

## 版本歷程

### V8.2 — 2026-05-18（目錄重整 + 穩定性修正）

**目錄重整**
- `scripts/` — 所有 PS1 腳本集中管理
- `tools/` — Python 工具集中管理
- `kingsmvpsplan/README.md` → `README.md`（本文件）

**穩定性修正**（共 9 項）

| # | 問題 | 修正 |
|---|------|------|
| C1 | BackToConfirm 未寫 `_REENTRY_COUNT`，loop counter 無法偵測重入 | `_common.ps1` BackToConfirm 加遞增計數 |
| C2 | Get-WikiCache 路徑計算未走 `Get-OnlineAddonsRoot`，project 路徑有誤 | `_common.ps1` 改呼叫 `Get-OnlineAddonsRoot` |
| C3 | `pipeline.md` 硬編碼舊路徑 `_pipeline_run.ps1` | 改為 `scripts/_pipeline_run.ps1` |
| C4 | BackToConfirm Move-Item 前未釋放 lock，Windows 下可能失敗 | 加 `Release-Lock` + `Remove-Item` + try/catch |
| M1 | STEP 3a 未檢查 `pending_prompt.txt`，AI 處理中仍可被觸發 | `analysis.ps1` 加 pending_prompt 存在判斷 |
| M2 | `_pipeline_run.ps1` 使用 `$env:PIPELINE_HOOK_MODE = ""` 清空非移除 | 改為 `Remove-Item env:PIPELINE_HOOK_MODE` |
| M4 | `coding.ps1` Move-Item 無 rollback，失敗後 pending 殘留 | 加 try/catch，失敗時清除 pending_prompt + flag |
| m2 | `Send-OdooTaskMessage` 無密碼保護，`ODOO_PASSWORD` 未設時仍嘗試呼叫 | 加 `if (-not $env:ODOO_PASSWORD) { return }` |
| m3 | `module` regex 未去引號，與 `odoo_version` 行為不一致 | 改為與 `odoo_version` 相同的去引號 pattern |

---

### V8.1 — 2026-05-17（Opus ultrathink 全面驗證後修正）

由 Opus ultrathink 驗證發現 2 CRITICAL / 7 MAJOR / 6 MINOR 共 18 項問題，本版本已全數修正：

| # | 問題 | 修正位置 |
|---|------|---------|
| C1 | Loop Counter 未實作 | `_pipeline_run.ps1` 新增完整計數器邏輯 |
| C2 | `send_message.py` 缺失 | 新建 `.claude/send_message.py` |
| C3 | `odoo_version` 單引號解析含引號 | `_common.ps1` ConvertFrom-Yaml regex 修正 |
| M1 | `project_name: null` 解析為字串 | `_common.ps1` 加 null-string → $null 轉換 |
| M2 | `module` regex 要求前導空白 | `_common.ps1` `\s+` → `\s*` |
| M3 | `coding.ps1` / `qa.ps1` 缺 `ultrathink` | 兩檔案 prompt 前補 `ultrathink\n\n` |
| M4 | Module 序列鎖未實作 | `coding.ps1` / `qa.ps1` 加 activeModules 檢查 |
| M5 | WIKI-CACHE 注入未實作 | `_common.ps1` 加 `Get-WikiCache`，三個 PS1 呼叫 |
| M6 | `requirements-analyst.md` stage 寫死 | 改為依 done marker 類型動態填入 |
| M7 | `analysis.ps1` STEP 2 Move 無 rollback | 加 try/catch，失敗時清除 pending_prompt |
| M8 | QA reason regex 抓錯區塊 | `qa.ps1` 改從 `issues:` 區塊後抓 description |
| m1 | `_pipeline_run.ps1` / `_common.ps1` 硬編碼 `C:\odoo` | 改用 `Split-Path -Parent $PSScriptRoot` |
| m2 | `coding.ps1` / `qa.ps1` mv 指令描述不完整 | prompt 改為三步驟原子協議說明 |
| m3 | STEP 3b 未說明不搬移原因 | 加說明注解 |
| m4 | CLAUDE.md 第二觸發條件無說明 | §7 補充「任何訊息都先檢查 _PIPELINE_WAITING」|
| m5 | pipeline.md Module 序列鎖責任不清 | 更新說明改為 PS1 負責 |
| m6 | pipeline.md WIKI-CACHE 注入責任不清 | 更新說明改為 PS1 負責 |
| m7 | `analysis.ps1` STEP 3b 缺 WIKI-CACHE | 加 Get-WikiCache 呼叫 |

---

## 目錄結構

```
.claude/
├── scripts/
│   ├── _common.ps1         共用函數庫
│   ├── _pipeline_run.ps1   「開工」hook 入口
│   ├── analysis.ps1        STEP 1-3
│   ├── coding.ps1          STEP 4
│   └── qa.ps1              STEP 5-6
├── tools/
│   ├── curl.py             Odoo 任務同步
│   └── send_message.py     Odoo 訊息發送
├── agents/
│   ├── requirements-analyst.md
│   ├── senior-software-engineer.md
│   └── qa-analyst.md
├── templates/              Blocker 模板
├── kingsmvpsplan/
│   ├── start/              新任務暫存（curl.py 同步後）
│   ├── confirm/            初始分析完成，等待 user_answer
│   ├── analysis/           答案完整，等待 MODE_B 規格生成
│   ├── coding/             實作與 QA 進行中
│   └── final/              QA 通過歸檔（唯讀）
├── CLAUDE.md               Claude AI 指令
├── pipeline.md             Pipeline 完整規格
├── README.md               本文件
├── project_version_map.json  專案版本對照表
└── settings.json           Claude hooks 與權限設定
```
