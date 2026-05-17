# Pipeline 自動調度詳細規格 (V8.1)

## Blocker 類型
| 檔名 | 情境 |
|------|------|
| `blocker.spec.txt` | 規格不清，需使用者澄清 |
| `blocker.tech.txt` | 技術上無法以標準 Odoo 擴展實現 |
| `blocker.agent.txt` | Agent 執行錯誤（已升級） |
| `blocker.loop.txt` | Pipeline 循環超出安全上限 |

遇到任何 blocker：立即 STOP，向使用者報告**檔案路徑**（不顯示內容）。

## Loop 安全上限（防死循環）

持久化計數器：`.claude/kingsmvpsplan/_LOOP_COUNTER.json`
```json
{
  "run_started_at": "2026-01-01T00:00:00",
  "loop_count": 0,
  "task_reentries": { "task_3919": 1 }
}
```

規則：
- 同一 pipeline run：`loop_count` 最多 **20**；超限寫 `blocker.loop.txt`
- 同一 `task_id`：`task_reentries[id]` 最多 **2**；超限將該任務改判 blocker
- run 正常結束時刪除 `_LOOP_COUNTER.json`

## 處理循環（全程不得請求手動確認）

每次進入循環前讀取並更新 `_LOOP_COUNTER.json`。

1. **掃描**：收集所有 `.claude/kingsmvpsplan/*/pending_prompt.txt`
2. **讀 stage**：每個任務目錄內找 `.pending_<stage>` flag 檔；stage = 去掉 `.pending_` 前綴。
   有效 Claude-facing stage：`analysis` / `final` / `coding` / `qa`
3. **分批**：依 `analysis → final → coding → qa` 順序。
   `final/` 目錄為 QA 通過歸檔，不是 stage。
4. **WIKI 快取注入**（spawn 前，每 stage 執行一次）：
   - 讀 `<online_addons_root>/graphify-out/wiki/index.md`
   - Grep 目標 module 相關行（最多 200 行）
   - Prepend 到各子 Agent prompt：
     ```
     [WIKI-CACHE]
     <extracted lines>
     [/WIKI-CACHE]
     ```
   - wiki 不存在 → 跳過注入，子 Agent 自行讀取
5. **並行 spawn**（同 stage 內）：
   - `analysis` / `final`：最多 **5** 個並行；超過分批
   - `coding` / `qa`：**主調度**負責按 module 排隊（見下方「Module 序列鎖」）
6. **Agent 失敗處理**：
   - 任一 Agent 返回 `status: error` → 寫 `<task_root>/agent_error.txt`（用 `.claude/templates/agent_error.txt` 格式）
   - `retry_count < 1`：主調度自動重試一次，`retry_count` +1
   - `retry_count >= 1`：升級為 `blocker.agent.txt`，不中斷其餘任務
   - 當前 stage 所有 Agent 完成後，統一向使用者報告失敗清單
7. **完成標記順序**（原子保證）：
   - 先寫 done marker（對照 Unified Marker Table）
   - 再 `mv pending_prompt.txt done_prompt.txt`
   - 再刪除 `.pending_<stage>` flag
   - 絕對不先刪後寫
8. **推進**：全 stage 完成後執行 `pwsh -NoProfile -File ".claude/_pipeline_run.ps1"`
   （Linux 上若無 pwsh：記錄「需在 Windows 端手動執行」）
9. **繼續**：若步驟 8 執行後出現新 `pending_prompt.txt` → 回步驟 1，`loop_count` +1
10. **結束**：無新 pending 任務 → 刪除 `_PIPELINE_WAITING` 和 `_LOOP_COUNTER.json`

## Module 序列鎖（主調度全權負責）

```
收集 coding/qa pending 任務
  ↓
讀各任務 analysis.yaml 的 module 欄位
  ↓
按 module 分群
  ↓
同 module 群：逐一 spawn（等前一個 Agent 完成後再啟動下一個）
不同 module 群：可並行（仍受 5 個並行上限）
```

子 Agent **不需自鎖**。鎖的責任完全在主調度。

## Sub-Agent 回傳格式（強制）

每個 sub-Agent 的最終回傳必須以此區塊結尾（總共最多 20 行）：

```
---AGENT-RESULT---
status: ok | blocker | error
task_id: task_<N>
stage: <stage>
files_written:
  - <relative_path>   # 僅列新建或修改的檔案；done_prompt.txt 和 .pending_* 不列入
message: <最多 1 行說明>
---END-RESULT---
```

主調度只解析此區塊。需要細節時直接讀對應檔案。

## _PIPELINE_WAITING TTL 檢查

flag 檔內容為建立時的 ISO 8601 時間戳（由 `_pipeline_run.ps1` 與 `Open-ClaudeTerminal` 寫入）。

觸發前檢查：
```python
import os
from datetime import datetime, timezone

flag = '.claude/kingsmvpsplan/_PIPELINE_WAITING'
if os.path.exists(flag):
    content = open(flag).read().strip()
    try:
        created = datetime.fromisoformat(content)
        age = (datetime.now(timezone.utc) - created).total_seconds()
    except ValueError:
        import time
        age = time.time() - os.path.getmtime(flag)
    if age > 1800:  # 30 分鐘
        os.remove(flag)
        # 不觸發 pipeline
```

## QA 失敗退回流程

QA `status = FAILED`：
1. 讀 `qa_report.yaml` 的第一個 error description
2. 將任務目錄移回 `confirm/<task_id>/`
3. 清除以下所有檔案（BackToConfirm 清單）：
   ```
   .analysis_done  .answer_done  .final_done  .implement_done  .qa_done
   .pending_analysis  .pending_final  .pending_coding  .pending_qa
   pending_prompt.txt  done_prompt.txt
   blocker.spec.txt  blocker.tech.txt  blocker.agent.txt  blocker.loop.txt
   agent_error.txt
   ```
4. 寫 `BACK_REASON.txt` 說明退回原因
5. 若 task_id 符合 `^task_(\d+)$` → 通知 Odoo 任務

## 路徑翻譯（Linux 執行環境）

PS1 腳本現已使用 `$PSScriptRoot` 自動適應平台，不再寫死路徑。
若 `pending_prompt.txt` 內仍含舊版 Windows 絕對路徑：

| Windows | Linux |
|---------|-------|
| `C:\odoo` | 專案根目錄（git root / `$PWD`）|
| `C:\online_addons` | `/online_addons` 或 `$ONLINE_ADDONS_DIR` |
| `C:\odoo\.claude` | `.claude/` |
