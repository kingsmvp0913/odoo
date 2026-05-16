# CLAUDE.md (V7)

## 0. Core Principles
- Challenge proposals that violate Odoo best practices, security, or performance.
- Surface 2–3 interpretations for ambiguous requests. Never guess intent.
- State one core assumption before executing complex tasks.

## 1. Knowledge Retrieval

| 工具 | 用途 | 使用時機 |
|------|------|---------|
| **Context7** | Odoo core API（Model/Field/Method/decorator 正確寫法） | 分析或實作前，確認 Odoo 版本的 API |
| **Graphify** | 自訂模組結構與既有邏輯的知識圖譜 | 實作前讀 `graphify-out/wiki/index.md`；編輯後執行 `/graphify . --update` |
| **Serena** | 即時精確 symbol 定位（定義、呼叫鏈） | Graphify wiki 快照不足，或需要確認當前代碼的確切位置時 |

- Graphify wiki 路徑：`<online_addons_root>/graphify-out/wiki/index.md`（依版本對應目錄）

## 2. Dev Workflow
- `senior-software-engineer` must read specification from `analysis.yaml`. Do not guess intent.
- Develop strictly per spec. Do not add fields, models, or logic beyond `analysis.yaml`.
- On any ambiguity or blocker discovered during coding, immediately write the query to a new file named `blocker.txt` inside the task root directory, then STOP execution immediately.

## 3. Edit Protocol
- Store task plans/logs in `.claude/kingsmvpsplan/`.
- Match existing code style exactly. Zero drive-by refactoring.
- Strict `[Step] → [Verify]` flow. Pass before proceeding.

## 4. Odoo Constraints
- Custom modules in `custom_addons/` only. Never modify core files.
- Models: `_inherit`. Views: `inherit_id` + `xpath`. Controllers: `super()`.
- Cannot achieve via standard extension → escalate as Hard Blocker immediately via blocker.txt.

## 5. Output
- Think in English. Output Traditional Chinese (Taiwan).
- No preambles. Start with solution or challenge.
- Use: 專案/資料庫/佈署/變數/函式/模組. Keep English: Variable/Function/Hook/Class/Field/Model.
- Commit: `[Module]: Why (not what)`. File edit: `@Path | Anchor | Action`.

## 6. Pipeline 自動調度

### 觸發條件（任一）
- 使用者輸入「開工」→ Hook 自動執行 `_pipeline_run.ps1`，輸出注入 context
- `C:\odoo\.claude\kingsmvpsplan\_PIPELINE_WAITING` 存在（PS1 手動執行後）

### 處理循環（全程不得請求手動確認）
1. 掃描所有 `pending_prompt.txt`（confirm → analysis → coding 順序）
2. 對每個檔案，**完整讀取並執行**其中所有指示
3. 每個任務完成後：刪除 `pending_prompt.txt` 和 `.pending_*`，寫入對應完成標記
4. 全部處理完後執行 `pwsh -NoProfile -File "C:\odoo\.claude\_pipeline_run.ps1"` 推進 Pipeline
5. 若有新的 `pending_prompt.txt` 出現，回到步驟 1
6. 直到 `_pipeline_run.ps1` 輸出「無待處理任務」為止，刪除 `_PIPELINE_WAITING`

### 重要規則
- 遇到 `blocker.txt`：立即停止並向使用者報告，但是不要顯示內容
- 每個 `pending_prompt.txt` 必須完整執行，不得摘要或跳過任何步驟
