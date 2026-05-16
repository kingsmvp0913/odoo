# CLAUDE.md (V7)

## 0. Core Principles
- Challenge proposals that violate Odoo best practices, security, or performance.
- Surface 2–3 interpretations for ambiguous requests. Never guess intent.
- State one core assumption before executing complex tasks.

## 1. Knowledge Retrieval
- Use Skill tool: `graphify query/path/explain`. Wiki: `graphify-out/wiki/index.md`.
- After edits: run `/graphify . --update`.

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
1. 掃描所有 `pending_prompt.txt`，依 stage 分組（confirm → analysis → coding 順序；coding 含 qa）
2. 同一 stage 的任務**以 Agent tool 並行 spawn**，不等單一任務完成再啟動下一個
   - **confirm / analysis stage**：直接並行，無限制
   - **coding stage（含 qa）**：先讀取各任務 `analysis.yaml` 的 `module` 欄位；
     相同 module 的任務**序列執行**，不同 module 的任務**並行執行**
3. 等待同一 stage 所有 Agent 完成後，再掃描下一 stage
4. 每個任務完成後：刪除 `pending_prompt.txt` 和 `.pending_*`，寫入對應完成標記
5. 全部處理完後執行 `pwsh -NoProfile -File "C:\odoo\.claude\_pipeline_run.ps1"` 推進 Pipeline
6. 若有新的 `pending_prompt.txt` 出現，回到步驟 1
7. 直到 `_pipeline_run.ps1` 輸出「無待處理任務」為止，刪除 `_PIPELINE_WAITING`

### 重要規則
- 遇到 `blocker.txt`：立即停止並向使用者報告，但是不要顯示內容
- 每個 `pending_prompt.txt` 必須完整執行，不得摘要或跳過任何步驟
- coding stage 相同 module 衝突保護：序列執行，前一個完成後才啟動下一個
