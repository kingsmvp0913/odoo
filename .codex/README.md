# Codex Pipeline (V1.0)

Claude Code 的備援版本。當 Claude Code 不可用時，改由 OpenAI Codex 執行 AI 階段，兩套系統共用同一份任務狀態目錄（`kingsmvpsplan/`）。

---

## 觸發方式

| 方式 | 情境 |
|------|------|
| Codex 對話輸入「**開工**」 | 主要使用方式，Codex 讀 `AGENTS.md` 後直接執行 PS1 |
| Claude Code 對話輸入「**codex開工**」 | Claude Code 運作中，但想改用 Codex 執行 AI 任務 |
| `pwsh -NoProfile -File ".codex/scripts/_pipeline_run_codex.ps1"` | 腳本直接呼叫 |

> Codex 需在 `C:\odoo` 目錄下開啟，才能正確讀取根目錄的 `AGENTS.md`

---

## 與 Claude 版差異

| 項目 | Claude 版 | Codex 版 |
|------|-----------|---------|
| AI 呼叫方式 | Claude Code spawn sub-agents | `codex exec` 每個 task 各自執行 |
| agent 定義 | `.claude/agents/*.md`（frontmatter + prompt） | `.codex/agents/*.toml`（`[codex]` + `[prompt]`） |
| 全域指令 | `.claude/CLAUDE.md` | `AGENTS.md`（根目錄）+ `.codex/AGENTS.md` |
| 觸發指令 | 「開工」 | 「codex開工」 |
| MCP 工具 | Serena、Context7 | 無（改用 bash grep/find） |
| 並行執行 | Claude 原生並行 | 目前序列（逐任務） |
| Pipeline 迴圈 | Claude 手動呼叫 PS1 | PS1 自動自迴圈 |

**共用**：`kingsmvpsplan/`、`_common.ps1`、`analysis.ps1`、`coding.ps1`、`qa.ps1`

---

## 安裝

### 前置需求

- PowerShell 7+（`pwsh`）
- Python 3.x
- OpenAI Codex（已登入）：`npm install -g @openai/codex`

### 環境變數

```powershell
[System.Environment]::SetEnvironmentVariable("ODOO_PASSWORD", "你的密碼", "User")
[System.Environment]::SetEnvironmentVariable("ODOO_SERVICE_PASSWORD", "你的密碼", "User")
```

### 選填

| 環境變數 | 預設值 | 說明 |
|---------|--------|------|
| `CODEX_MODEL` | （由 `.toml` 決定） | 覆蓋全部 agent 的 model |
| `PIPELINE_MAX_LOOPS` | 20 | 防死循環上限 |
| `PIPELINE_MAX_REENTRIES` | 2 | 單一任務 QA 失敗退回上限 |

---

## Agent 設定（`.codex/agents/*.toml`）

每個 `.toml` 包含兩個區塊：

```toml
[codex]
model = "gpt-5.5"                    # 使用的 AI 模型
model_reasoning_effort = "high"      # 推理強度：low / medium / high

[agent]
name = "requirements-analyst"
stage = ["analysis", "final"]

[prompt]
content = """
... agent 的完整提示指令 ...
"""
```

| Agent | 檔案 | Stage | reasoning_effort |
|-------|------|-------|-----------------|
| 需求分析師 | `requirements-analyst.toml` | analysis / final | high |
| 資深工程師 | `senior-software-engineer.toml` | coding | high |
| QA 分析師 | `qa-analyst.toml` | qa | low |

---

## Pipeline 流程

```
使用者觸發「codex開工」
    │
    ├── analysis.ps1（PS1 機械工作：同步 Odoo、準備任務）
    ├── codex exec requirements-analyst（analysis stage）
    ├── codex exec requirements-analyst（final stage）
    │
    ├── coding.ps1（PS1：移動任務到 coding/）
    ├── codex exec senior-software-engineer（coding stage）
    │
    ├── qa.ps1（PS1：準備 QA）
    ├── codex exec qa-analyst（qa stage）
    │
    └── 有新 pending？→ 自動進入下一輪（最多 20 輪）
        例：QA 失敗 → 退回 analysis → 下一輪重跑
```

---

## 目錄結構

```
.codex/
├── AGENTS.md                          全域 Codex 指令（自動載入）
├── README.md                          本文件
├── agents/
│   ├── requirements-analyst.toml      需求分析 + Final 規格 agent
│   ├── senior-software-engineer.toml  實作 agent
│   └── qa-analyst.toml               QA agent
└── scripts/
    └── _pipeline_run_codex.ps1        Pipeline 主入口
```

---

## 遇到問題

| 狀況 | 處置 |
|------|------|
| `codex exec` 無法執行 | 確認 `codex --version` 正常；重新 `codex login` |
| Agent 沒有輸出 AGENT-RESULT | 查看 `kingsmvpsplan/<stage>/task_N/log/agent_error.txt` |
| 任務卡在 blocker | `find kingsmvpsplan -name "blocker.*.txt"` 查看；修復後 `touch system/.blocker_resolved` 再觸發 |
| 想調整某 agent 的模型 | 直接編輯 `.codex/agents/<name>.toml` 的 `[codex]` 區塊 |
| 想切換回 Claude | 輸入「開工」即可，共用同一個 `kingsmvpsplan/` |
