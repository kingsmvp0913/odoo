# Kingsmvps Pipeline (V8.2)

輸入「**開工**」，Claude 自動完成需求分析 → 實作 → QA

---

## 安裝

### 前置需求

- PowerShell 7+（`pwsh`）
- Python 3.x
- Claude Code CLI（已登入）

### 設定步驟

1. **設定環境變數**（在 PowerShell profile 或 Claude terminal 執行）

   ```powershell
   $env:ODOO_PASSWORD = "your_password"     # 必要
   $env:ODOO_USER_ID  = "79"                # 可選，預設 79
   $env:ONLINE_ADDONS_DIR = "C:\online_addons"  # 可選，預設 C:\online_addons
   ```
2. **確認 `project_version_map.json` 已填寫**（`.claude/project_version_map.json`，專案與 Odoo 版本對照）


---

## 怎麼用

1. 在 Odoo 建立任務
2. 在 Claude 輸入「**開工**」
3. 需要填寫確認問題或是低信心度的時候，Claude 會暫停等你在 `analysis.yaml` 填完後再繼續。
4. 等待完成（任務出現在 `final/` 即代表通過 QA）

> **低信心度**：即使所有問題都已答覆，若生成規格的信心度低於 0.9，Claude 會補提新問題並退回 `confirm/` 等待補充，不會強行進入實作階段。

---

## 任務流向

```
Odoo 任務
   │ 自動同步 (tools/curl.py)
   ↓ 
start/       新任務
   │ 分析agent初步分析，產生問題確認檔
   ↓ 
confirm/     待確認
   │ 填寫問題，答案全部填寫且為有效答案後往下一步
   ↓ 
analysis/    分析agent使用ultra think產出完整技術規格SD
   │  │
   │  ├─ confidence >= 0.9 → 往下一步開始實作
   │  └─ confidence < 0.9  → 退回confirm 補充問題
   ↓ 
coding/      由工程師agent實作中，完成後 Claude 自動執行 品管agent
   │ QA 通過，不通過的話回到confirm 確認
   ↓ 
final/       ✓ 完成（已歸檔）
```

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