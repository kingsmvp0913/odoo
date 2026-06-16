# Codex Pipeline 自主調度規格 (V1.1)

Codex 讀取本文件後，以 **調度者 + 執行者** 身份自主完成完整 pipeline。

---

## 執行原則

- **Sub-agent 處理**：每個任務由對應的 Skill sub-agent 處理（`$requirements-analyst`、`$senior-software-engineer`、`$qa-analyst`），各有獨立 context
- **PS1 是工具**：stage scripts 負責機械工作（同步、移動目錄、序列鎖、BackToConfirm），Codex 負責 AI 決策
- **順序**：analysis → final → coding → qa；同 stage 內逐任務序列處理
- **自迴圈**：QA 失敗/低信心退回後，偵測到新 pending 任務自動繼續下一輪

---

## Stage → Agent 對照

| Stage | pending flag | 任務目錄 | Agent | 備註 |
|---|---|---|---|---|
| analysis | `.pending_analysis` | `confirm/` | `$requirements-analyst` | |
| final | `.pending_final` | `analysis/` | `$requirements-analyst` | |
| coding | `.pending_coding` | `coding/` | `$senior-software-engineer` | 同模組序列（PS1 保證）|
| qa | `.pending_qa` | `coding/` | `$qa-analyst` | |

---

## 完整執行流程

### STEP 0：Loop 計數器

每次進入 STEP 1 前：
```bash
# 讀取或建立 _LOOP_COUNTER.json
cat kingsmvpsplan/_LOOP_COUNTER.json 2>/dev/null || echo '{"loop_count":0}'
# 確認 loop_count <= 20，超過則停止並回報
```

### STEP 1：需求分析機械工作
```powershell
pwsh -NoProfile -File ".claude/scripts/analysis.ps1"
```
包含：
- 第一輪自動對相關 repo 執行 `git pull`
- 同步 Odoo 任務到 `kingsmvpsplan/start/`
- 移動任務目錄 start → confirm
- 建立 `pending_prompt.txt`（含 `[WIKI-CACHE]` 注入）與 `.pending_analysis` flag
- 掃描 `answer_done` 完整的任務，建立 `.pending_final`

### STEP 2：處理 analysis 任務
掃描 `kingsmvpsplan/confirm/*/system/.pending_analysis`（排除 `stop/`、`final/`）：

對每個任務：
1. 確認無 `system/blocker.*.txt`（有則跳過，加入 blocker 清單）
2. 確認無 crash 殘留（done marker 存在但 pending flag 未刪 → 補完原子協議，skip 重執行）
3. 呼叫 `$requirements-analyst`，傳入 `pending_prompt.txt` 的完整路徑
4. 確認 done marker 已寫入

### STEP 3：處理 final 任務
掃描 `kingsmvpsplan/analysis/*/system/.pending_final`：

對每個任務：
1. 確認無 blocker、無 crash 殘留
2. 呼叫 `$requirements-analyst`，傳入 `pending_prompt.txt` 的完整路徑

> **低信心度（final low-conf）**：`$requirements-analyst` 若判斷 confidence < 0.9，寫 `.low_confidence` 標記（非 `.final_done`）。PS1 下一輪偵測後將任務移回 `confirm/`，等使用者補充 `user_answer`。Codex 不需處理此路由，PS1 自動完成。

### STEP 4：實作機械工作
```powershell
pwsh -NoProfile -File ".claude/scripts/coding.ps1"
```
包含：
- 移動 analysis/ → coding/ 目錄
- **模組序列鎖**：同一模組只允許一個 coding 任務並行（PS1 保證，Codex 無需額外處理）
- 建立 `.pending_coding` 與 `pending_prompt.txt`

### STEP 5：處理 coding 任務
掃描 `kingsmvpsplan/coding/*/system/.pending_coding`：

對每個任務：
1. 確認無 blocker、無 crash 殘留
2. 呼叫 `$senior-software-engineer`，傳入 `pending_prompt.txt` 的完整路徑

### STEP 6：QA 機械工作
```powershell
pwsh -NoProfile -File ".claude/scripts/qa.ps1"
```
包含：
- 建立 `.pending_qa` 與 `pending_prompt.txt`
- **QA 失敗後**：PS1 讀取 `qa_report.yaml`，若 status=FAILED，執行 BackToConfirm（Smart Rollback 或完整退回）、寫 `back_reason.txt`、更新 `_reentry_count` 與 `_total_reentry_count`

### STEP 7：處理 qa 任務
掃描 `kingsmvpsplan/coding/*/system/.pending_qa`：

對每個任務：
1. 確認無 blocker、無 crash 殘留
2. 呼叫 `$qa-analyst`，傳入 `pending_prompt.txt` 的完整路徑

### STEP 8：迴圈判斷

```powershell
# 掃描新 pending（QA 失敗退回、low-conf 退回等產生的新任務）
Get-ChildItem kingsmvpsplan -Recurse -Filter "pending_prompt.txt" |
  Where-Object { $_.FullName -notmatch "\\stop\\|\\final\\" }
```

- **有新 pending 且 loop_count < 20** → 更新 `_LOOP_COUNTER.json`，回到 STEP 1
- **無 pending** → 清除 `_PIPELINE_WAITING`、`_LOOP_COUNTER.json`，回報完成摘要
- **loop_count >= 20** → 寫 `blocker.loop.txt`，停止

### STEP 9：Pipeline Run Summary（每輪結束）

回報本輪執行摘要：
- 處理任務數（各 stage）
- Blocker 清單（若有）
- 仍在 coding/confirm/analysis 的任務狀態

---

## AGENT-RESULT 格式（強制）

每個 sub-agent 回傳必須以此區塊結尾：

```
---AGENT-RESULT---
status: ok | blocker | error
task_id: task_<N>
stage: <stage>
mcp_used:
  wiki_cache_hit: true | false
  serena_queries: 0        # 實際使用次數（超過 3 視為異常）
  context7_queries: 0
files_written:
  - <relative_path>        # 僅列新建或修改的檔案
message: <最多 1 行說明>
---END-RESULT---
```

Orchestrator 解析規則：
- `status: error` → 自動重試一次（見下方「Agent 失敗處理」）
- `serena_queries > 3` → 升級為 `blocker.agent.txt`
- 找不到 AGENT-RESULT 區塊 → 視為 `status: error`

---

## Agent 失敗處理

任一 sub-agent 完成後：

1. 解析 AGENT-RESULT：
   - `status: ok` → 繼續下一個任務
   - `status: blocker` → 記錄，繼續其他任務，最後統一回報
   - `status: error` 或找不到區塊 → 進入重試邏輯

2. 重試邏輯（`retry_count` 記憶在 orchestrator session 內）：
   - `retry_count == 0` → 自動重試一次，`retry_count = 1`
   - `retry_count >= 1` → 寫 `system/blocker.agent.txt`，不中斷其他任務

3. 本 stage 所有任務完成後，統一回報失敗清單

---

## 原子完成協議

**每個任務 AI 必須依序執行**：

```bash
# 1. 先寫 done marker
touch kingsmvpsplan/<stage-dir>/<task_id>/system/.<stage>_done

# 2. 移動 prompt 紀錄
mv kingsmvpsplan/<stage-dir>/<task_id>/system/pending_prompt.txt \
   kingsmvpsplan/<stage-dir>/<task_id>/log/done_prompt.txt

# 3. 最後刪 pending flag
rm kingsmvpsplan/<stage-dir>/<task_id>/system/.pending_<stage>
```

**禁止**：先刪 flag 後寫 marker。

---

## Loop 計數器管理

```json
{
  "run_started_at": "2026-01-01T00:00:00",
  "loop_count": 0
}
```

- 檔案路徑：`kingsmvpsplan/_LOOP_COUNTER.json`
- 每次進入 STEP 1 前 +1，正常結束後刪除

---

## Blocker 處理

發現任何 `system/blocker.*.txt`：
1. 跳過該任務
2. 記錄到本輪 blocker 清單
3. 繼續處理其他任務
4. 全部完成後統一回報

**Blocker Resume**：使用者修復後 `touch system/.blocker_resolved`，再說「開工」。PS1 自動掃描並清除 blocker：
- `blocker.loop.txt`：必須確認 `_LOOP_COUNTER.json` 已刪除或計數重置，否則 PS1 拒絕 resume
- `blocker.spec.txt`：PS1 驗證 `analysis.yaml` mtime > blocker 建立時間（確認已回填規格）
- 清除後保留 `.pending_<stage>`（原 stage 重試）

---

## 退回次數限制（PS1 管理）

| 計數器 | 路徑 | 上限 | 觸發 |
|---|---|---|---|
| `_reentry_count` | `system/_reentry_count` | 2 | QA 失敗退回 |
| `_total_reentry_count` | `system/_total_reentry_count` | 6 | QA 失敗 + 低信心合計 |

超過上限 → PS1 自動寫 `blocker.loop.txt`。Codex 下一輪掃描時跳過該任務。

---

## 任務掃描排除

- `kingsmvpsplan/stop/`
- `kingsmvpsplan/final/`
- 含 `blocker.*.txt` 的任務

---

## Crash 防護

掃描時若發現任務**同時具備** done marker 和 pending flag：
1. 補完原子協議（`mv pending_prompt.txt` + `rm .pending_*`）
2. 不重新執行任務
3. 繼續下一個

---

## Stage Prompt 內容規則

PS1 生成 `pending_prompt.txt` 時只注入該 stage 需要的部分（已由 PS1 處理，Orchestrator 參考用）：

| Stage | 包含 | 不包含 |
|-------|------|--------|
| analysis | original.txt 內容、[MCP-BUDGET] | analysis.yaml 全文 |
| final | questions + user_answer 區塊 | technical_specification |
| coding | technical_specification 區塊、[MCP-BUDGET]、[WIKI-CACHE] | 其他欄位 |
| qa | [MCP-BUDGET] | analysis.yaml 全文 |

---

## Pipeline Run Summary

每輪結束後回報（寫入 `kingsmvpsplan/log/pipeline_run_summary.yaml`）：

```yaml
run_id: '<ISO 時間戳>'
run_ended_at: '<ISO 時間戳>'
loop_count: 0
tasks_pending_ai: 0
tasks_in_pipeline:
  - task_id: 'task_N'
    stage: 'coding'
    status: 'pending_ai | blocker | idle'
```

---

## 診斷速查

```bash
find kingsmvpsplan -name "blocker.*.txt" -exec echo "==={}" \; -exec cat {} \;
```

---

## 同步（「同步」指令）

```powershell
pwsh -NoProfile -File ".claude/scripts/_sync.ps1"
```

只拉取 Odoo 任務到 `start/`，不執行 pipeline。
