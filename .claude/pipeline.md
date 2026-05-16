# Pipeline 自動調度詳細規格 (V8)

## 安全上限（防死循環）
- 同一 pipeline run 最多 **20 次** loop
- 同一 task_id 在同一 run 最多重入 **2 次**
- 超限 → 寫 `blocker.loop.txt` 至該任務 task dir → 停止整個 pipeline，向使用者報告路徑

## 處理循環（全程不得請求手動確認）

1. **掃描**：收集所有 `.claude/kingsmvpsplan/*/pending_prompt.txt`
2. **讀 stage**：每個任務目錄內找 `.pending_<stage>` flag 檔，stage = 檔名去掉 `.pending_` 前綴
3. **分批**：依 `confirm → analysis → final → coding → qa` 順序；qa 屬 coding 子階段
4. **並行 spawn**（同 stage 內）：
   - `confirm` / `analysis` / `final`：最多 **5** 個並行；超過分批
   - `coding` / `qa`：**主調度**負責按 module 排隊（見下方「Module 序列鎖」）
5. **Agent 失敗處理**：
   - 任一 Agent 返回 `status: error` 或拋出例外 → 寫 `<task_root>/agent_error.txt`
   - 該任務視為 blocker，不中斷其餘任務
   - 當前 stage 所有 Agent 完成後，統一向使用者報告失敗清單
6. **完成標記順序**（原子保證）：
   - 先寫 `.<stage>_done` marker
   - 再執行 `mv pending_prompt.txt done_prompt.txt`
   - 絕對不先刪後寫（防止崩潰後狀態遺失）
7. **推進**：全 stage 完成後執行 `pwsh -NoProfile -File ".claude/_pipeline_run.ps1"`（Linux 上若無 pwsh，僅記錄「需在 Windows 端手動執行」）
8. **繼續**：若步驟 7 執行後出現新 `pending_prompt.txt` → 回步驟 1，loop 計數 +1
9. **結束**：無新 pending 任務 → 刪除 `.claude/kingsmvpsplan/_PIPELINE_WAITING`

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

每個 sub-Agent 的最終回傳必須以此格式結尾（最多 20 行）：

```
---AGENT-RESULT---
status: ok | blocker | error
task_id: task_<N>
stage: <stage>
files_written:
  - <relative_path>
message: <最多 1 行說明>
---END-RESULT---
```

主調度只解析此區塊。需要細節時直接讀對應檔案，不從回傳文字解析。

## _PIPELINE_WAITING TTL 檢查

在觸發循環前先確認 flag 有效性：
```python
import os, time
flag = '.claude/kingsmvpsplan/_PIPELINE_WAITING'
if os.path.exists(flag):
    age = time.time() - os.path.getmtime(flag)
    if age > 1800:  # 30 分鐘
        os.remove(flag)
        # 不觸發 pipeline
```

## 知識快取策略

主調度在啟動子 Agent 前：
1. 讀取 `<online_addons_root>/graphify-out/wiki/index.md` 一次
2. 擷取相關模組段落（最多 200 行）
3. 將摘要注入每個子 Agent 的 prompt（標記為 `[WIKI-CACHE]`）

子 Agent 收到 `[WIKI-CACHE]` 後：
- 直接使用，不再呼叫 Graphify
- 若 wiki 內容不足，向主調度回傳 `wiki_insufficient: true`，主調度補注 Serena 結果後重 spawn

## QA 失敗退回流程

QA status = FAILED：
1. 讀 `qa_report.yaml` 的第一個 error description
2. 呼叫 PS1 `BackToConfirm`（或直接操作目錄）退回 `confirm/<task_id>/`
3. 清除所有 `.done` 標記與 pending 檔案
4. 寫 `BACK_REASON.txt` 說明退回原因
5. 通知 Odoo 任務（若 task_id 符合 `task_\d+` 格式）

## 路徑翻譯（Linux 執行環境）

當 `pending_prompt.txt` 內含 Windows 絕對路徑時：

| Windows | Linux |
|---------|-------|
| `C:\odoo` | 專案根目錄（`/home/user/odoo` 或 `$PWD`）|
| `C:\online_addons` | `/online_addons` 或相對路徑 `../online_addons` |
| `C:\odoo\.claude` | `.claude/` |
