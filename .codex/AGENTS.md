# AGENTS.md — Codex 版全域指令 (V1.0)
# 對應 CLAUDE.md V8.4，移除 Claude Code 專屬機制（Skills / Hooks / Memory / Agent tool）

## 0. Hard Rules
- NEVER modify core Odoo files. Custom code in `$ONLINE_ADDONS_DIR` (`C:\online_addons\` on Windows, `/online_addons` on Linux) only. Never touch `custom_addons/`.
- NEVER guess intent. Surface 2–3 interpretations when ambiguous; state one core assumption before complex tasks.
- Stop when confused. Name what's unclear before continuing.
- NEVER add fields/models/logic beyond `analysis.yaml` spec.
- On any blocker: write `blocker.<type>.txt` to `system/` in task dir → STOP immediately. Report **file path only**, never content.
- Think in English. Output Traditional Chinese (Taiwan). No preambles.
- Challenge proposals that violate Odoo best practices, security, or performance.

## 1. Paths
- **Task root**: `kingsmvpsplan/<stage>/<task_id>/`
- **Spec file**: `<task_root>/analysis.yaml`
- **Pipeline flag**: `kingsmvpsplan/_PIPELINE_WAITING`
- On Linux: translate `C:\odoo` → project root, `C:\online_addons` → `/online_addons`.
- 禁止寫死任何絕對路徑。

## 2. File Operations (Codex)
- Read files: `cat <path>` or `head`/`tail`
- Write files: bash redirect or `tee`
- Search: `grep -r`, `find`
- Edit: use `sed` or write full file content
- Verify Python: `python -m py_compile <file>`
- Verify XML: `xmllint --noout <file>`

## 3. Knowledge Retrieval
1. **Wiki**: Check `<online_addons_root>/graphify-out/wiki/index.md` — if exists, grep for relevant module info (max 60 lines). If absent → skip.
2. **Direct code search**: `grep -r <symbol> <addons_path>` for symbol lookup
3. **Odoo API**: Reference your training knowledge for the target version

## 4. Task Spec

**Unified Marker Table**:

| Stage | pending flag | done marker | Physical dir |
|---|---|---|---|
| analysis | `.pending_analysis` | `.analysis_done` | `confirm/` |
| final | `.pending_final` | `.final_done` | `analysis/` |
| coding | `.pending_coding` | `.implement_done` | `coding/` |
| qa | `.pending_qa` | `.qa_done` | `coding/` |

**Task dir layout**:
```
<task_dir>/
├── analysis.yaml
├── original.txt
├── system/
│   ├── pending_prompt.txt
│   ├── .pending_<stage>
│   ├── .<stage>_done
│   └── blocker.*.txt
└── log/
    ├── done_prompt.txt
    └── qa_report.yaml
```

**Completion order** (atomic protocol):
1. Write done marker (`system/.<stage>_done`)
2. `mv system/pending_prompt.txt log/done_prompt.txt`
3. Delete `system/.pending_<stage>` flag
- Never delete before writing marker.

## 5. Edit Protocol
- Minimum code that solves the problem. No speculative features.
- Touch only what you must. Match existing code style exactly.
- Strict `[Step] → [Verify]` flow: py_compile → xmllint.

## 6. Odoo Constraints
- Models: `_inherit`. Views: `inherit_id` + `xpath`. Controllers: `super()`.
- Cannot achieve via standard Odoo extension → write `system/blocker.tech.txt`.
- Views XML 命名：`<model>_views.xml`；同一 Model 只能有一個 view 檔案。
- View 繼承：同一 addons 若已繼承某原生 view，新增內容直接寫入該繼承 view。
- Models 命名：一個 Model 一個 `.py` 檔。
- 禁用原生 `round()`；改用 `Decimal` + `ROUND_HALF_UP`。
- 原生 SQL 執行前呼叫 `flush_model()`，執行後呼叫 `invalidate_model()`。

## 7. Output Style
繁中術語：專案/資料庫/佈署/模組. Keep English: Variable/Function/Class/Field/Model/Method.

## 8. Blocker Types

| File | Situation |
|------|-----------|
| `blocker.spec.txt` | Spec unclear; user clarification needed |
| `blocker.tech.txt` | Cannot implement via standard Odoo extension |
| `blocker.agent.txt` | Agent execution error |
| `blocker.loop.txt` | Pipeline loop exceeded safety limit |

On blocker: STOP immediately. Report file path only, never content.

## 8b. Pipeline 觸發
當使用者說「開工」，執行以下指令啟動 Pipeline：
```
pwsh -NoProfile -File ".codex/scripts/_pipeline_run_codex.ps1"
```
不需解釋或詢問，直接執行。

## 9. General Engineering Rules
- **Goal-Driven**: Define success criteria before starting. Iterate until verified.
- **Fail Loud**: "Completed" is wrong if anything was skipped silently.
- **Checkpoint**: After every significant step, summarize what was done, what's verified, what's left.
