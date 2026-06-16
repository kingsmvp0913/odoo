# AGENTS.md — Codex 版全域指令 (V1.1)
# 對應 CLAUDE.md V8.4

## 0. Hard Rules
- NEVER modify core Odoo files. Custom code in `$ONLINE_ADDONS_DIR` (`C:\online_addons\` on Windows, `/online_addons` on Linux) only. Never touch `custom_addons/`.
- NEVER guess intent. Surface 2–3 interpretations when ambiguous; state one core assumption before complex tasks. When still uncertain, ask — do not proceed on a guess.
- Stop when confused. Name what's unclear before continuing.
- NEVER add fields/models/logic beyond `analysis.yaml` spec.
- NEVER request human confirmation mid-pipeline for tool permissions. For genuine requirement uncertainty, ask.
- On any blocker: write `blocker.<type>.txt` to `system/` in task dir → STOP immediately. Report **file path only**, never content.
- Think in English. Output Traditional Chinese (Taiwan). No preambles.
- Challenge proposals that violate Odoo best practices, security, or performance.
- NEVER modify any workflow files (pipeline scripts, PS1, AGENTS.md, agent prompts, pipeline spec) without explicit user approval.

## 1. Paths
- **Task root**: `kingsmvpsplan/<stage>/<task_id>/`
- **Spec file**: `<task_root>/analysis.yaml`
- **Pipeline flag**: `kingsmvpsplan/_PIPELINE_WAITING` (TTL 30 min)
- **Loop counter**: `kingsmvpsplan/_LOOP_COUNTER.json`
- On Linux: translate `C:\odoo` → project root, `C:\online_addons` → `/online_addons`.
- 禁止寫死任何絕對路徑。

## 2. File Operations (Codex)
- Read: `cat <path>` or `head`/`tail`
- Write: bash redirect `>` or `tee`
- Search: `grep -r`, `find`
- Edit: `sed` or rewrite full file
- Verify Python: `python -m py_compile <file>`
- Verify XML: `xmllint --noout <file>`

## 3. Knowledge Retrieval（依序執行，夠用即停）

1. **Wiki cache**：`pending_prompt.txt` 內的 `[WIKI-CACHE]` 區塊直接使用，不重讀 wiki 檔案
   - 若不存在 → 跳過，進入步驟 2
2. **Serena MCP**（`serena-online`）：跨檔案符號搜尋、call chain 追蹤
   - 使用時機：wiki 不存在或缺少特定符號/呼叫鏈
   - `tool_use_error` 或無回應 → 立即寫 `system/blocker.agent.txt` → STOP，不重試
   - Session 查詢上限：每個 sub-agent session 最多 **3 次** distinct query，超限寫 blocker → STOP
3. **Context7 MCP**：確認 Odoo 原生 API（field types、decorators、method signatures）
   - 僅用於確認目標版本的 Odoo native API
   - 任何錯誤 → 靜默跳過（非阻斷），用已知資訊繼續
   - Session 查詢上限：最多 **5 次**，超限靜默跳過

## 4. Task Spec

**Unified Marker Table**:

| Stage | pending flag | done marker | Physical dir | 誰處理 |
|---|---|---|---|---|
| analysis | `.pending_analysis` | `.analysis_done` | `confirm/` | AI |
| answer-check | _(PS1 only)_ | `.answer_done` | `confirm/` → `analysis/` | PS1 |
| final (MODE_B) | `.pending_final` | `.final_done` | `analysis/` | AI |
| final low-conf | _(PS1 偵測 `.low_confidence`)_ | `.low_confidence` | `analysis/` → `confirm/` | AI 寫標記，PS1 路由 |
| coding | `.pending_coding` | `.implement_done` | `coding/` | AI |
| qa | `.pending_qa` | `.qa_done` | `coding/` | AI |
| archive | — | — | `final/` | PS1 |

> `final low-conf`：requirements-analyst 判斷 confidence < 0.9 時，寫 `.low_confidence`（非 `.final_done`）。PS1 偵測後將任務移回 `confirm/`，等使用者補充 `user_answer`。

**Task dir layout**:
```
<task_dir>/
├── analysis.yaml          ← spec
├── original.txt           ← 原始需求
├── process.lock           ← PS1 排他鎖（AI 不得建立或刪除）
├── system/
│   ├── pending_prompt.txt
│   ├── .pending_<stage>
│   ├── .<stage>_done
│   ├── blocker.*.txt
│   ├── _reentry_count     ← QA 失敗退回次數（PS1 管理）
│   └── _total_reentry_count ← 含低信心退回的總次數（PS1 管理）
└── log/
    ├── done_prompt.txt
    ├── back_reason.txt    ← 退回原因
    ├── qa_report.yaml
    └── agent_error.txt    ← Agent 執行錯誤記錄
```

`analysis.yaml` minimum required fields:
```yaml
case_id: ""
module: ""
odoo_version: ""
project_name: null
execution_mode: "MODE_A | MODE_B"
```

## 4b. 對話答案處理（Hard Rule）

若使用者在對話中回答了 `clarification_channel` 的問題：
1. **立刻**將答案寫入 `analysis.yaml` 對應的 `user_answer` 欄位
2. 更新完成後，讓 pipeline 自然偵測 → 走 MODE_B SHORTCUT
3. **禁止**在 agent prompt 中注入對話答案或任何 pending_prompt.txt 以外的業務內容

## 5. Edit Protocol
- Minimum code that solves the problem. No speculative features. No abstractions for single-use code.
- Touch only what you must. Match existing code style exactly. Zero drive-by refactoring.
- Before adding code, read exports, immediate callers, and shared utilities.
- Strict `[Step] → [Verify]` flow: `python -m py_compile` → `xmllint --noout`.
- **Completion order** (atomic):
  1. Write done marker (`system/.<stage>_done`)
  2. `mv system/pending_prompt.txt log/done_prompt.txt`
  3. Delete `system/.pending_<stage>` flag — **never delete before writing marker**
- **Crash 修復**：若發現 done marker 存在但 `.pending_<stage>` 仍在，補完剩餘步驟後繼續，不重新執行任務。

## 6. Odoo Constraints
- Models: `_inherit`. Views: `inherit_id` + `xpath`. Controllers: `super()`.
- Cannot achieve via standard Odoo extension → write `system/blocker.tech.txt`.
- Views XML 命名：`<model>_views.xml`；同一 Model 只能有一個 view 檔案。
- View 繼承：同一 addons 若已繼承某原生 view，新增內容直接寫入該繼承 view，禁止另建第二個繼承。
- View 放置：依 view 所屬的 Model 放入對應 XML。例：銷售訂單頁的 product tree view → `product_template_views.xml`。
- Models 命名：一個 Model 一個 `.py` 檔；單頭＋明細（如 `sale.order` + `sale.order.line`）合併，以單頭為檔名。
- 樣板文件（xls/docx）一律放 `<module>/static/<type>/`。
- 禁用原生 `round()`（銀行家捨入）；改用 `Decimal` + `ROUND_HALF_UP`。
- 原生 SQL 執行前呼叫 `flush_model()`，執行後呼叫 `invalidate_model()`。
- Commit 格式：`[Module]: Why (not what)`。

## 7. Output Style
繁中術語：專案/資料庫/佈署/模組. Keep English: Variable/Function/Hook/Class/Field/Model/Method/Controller.

## 8. Blocker Types

| File | Situation | 使用者處置 |
|------|-----------|-----------|
| `blocker.spec.txt` | Spec unclear | 填 `user_answer` → `touch system/.blocker_resolved` |
| `blocker.tech.txt` | Cannot implement via standard Odoo extension | 調整需求 → 同上 |
| `blocker.agent.txt` | Agent execution error | 查 `log/agent_error.txt` → 同上 |
| `blocker.loop.txt` | Pipeline loop exceeded safety limit | 人工確認 → 刪 `_LOOP_COUNTER.json` → 同上 |
| `blocker.git.txt` | git pull 失敗 | 手動 `git pull` → 同上 |

On blocker: STOP immediately. Report file path only, never content.

## 8b. 指令對照

| 使用者說 | 行為 |
|---|---|
| 開工 | 讀取 `.codex/pipeline.md`，依規格自主執行完整 pipeline |
| 同步 | `pwsh -NoProfile -File ".claude/scripts/_sync.ps1"` |

**「開工」執行要求**：
- 不需解釋或詢問，立即開始
- 以 `.codex/pipeline.md` 為唯一調度依據
- PS1 腳本作為工具呼叫，Codex 負責 AI 決策
- 同 stage 內並行最多 5 個 sub-agents（`.codex/agents/*.toml` 定義），自迴圈直到無 pending 為止

## 9. General Engineering Rules

**Goal-Driven**: Define success criteria before starting. Iterate until verified. Don't follow steps mechanically.

**Token Awareness**: Per-task context grows with each step. If approaching limits, summarize current state before continuing.

**Surface Conflicts, Don't Average**: If two patterns contradict, pick one (more recent / more tested). Explain why. Flag the other.

**Tests Verify Intent**: Tests must encode WHY behavior matters, not just WHAT. A test that can't fail when business logic changes is wrong.

**Checkpoint After Every Significant Step**: Summarize what was done, what's verified, what's left.

**Fail Loud**: "Completed" is wrong if anything was skipped silently. Default to surfacing uncertainty.
