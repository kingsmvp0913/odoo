# Kingsmvps Pipeline (V8)

輸入「**開工**」，Claude 自動完成需求分析 → 實作 → QA，無需手動確認。

---

## 怎麼用

1. 在 Odoo 建立任務
2. 在 Claude 輸入「**開工**」
3. 等待完成（任務出現在 `final/` 即代表通過 QA）

有 `user_answer` 需要填寫時（MODE_A），Claude 會暫停等你在 `analysis.yaml` 填完後再繼續。

---

## 任務流向

```
Odoo 任務
   ↓ 自動同步
start/       新任務
   ↓ Claude 需求分析
confirm/     等待 user_answer（MODE_A）或自動通過（MODE_B）
   ↓ 答案完整後
analysis/    Claude 產出完整技術規格（MODE_B）
   ↓ Claude 實作
coding/      實作中，完成後 Claude 自動執行 QA
   ↓ QA 通過
final/       ✓ 完成
```

QA 失敗會自動退回 `confirm/` 重跑。

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
| Claude 停下來說有 blocker | 查看對應任務目錄的 blocker 檔路徑，手動決策後刪除它再繼續 |
| MODE_A 等待填寫 | 打開 `confirm/task_N/analysis.yaml`，填寫所有 `user_answer` 欄位 |
| QA 一直失敗 | 查看 `coding/task_N/qa_report.yaml` 的 issues 說明 |
| Pipeline 沒有自動觸發 | 確認 `_PIPELINE_WAITING` flag 是否存在且未超過 30 分鐘 |
