# Kingsmvps Pipeline

自動化 Odoo 開發流水線。輸入「開工」由 Claude 全自動驅動，無需手動確認。

## 流程總覽

```
Odoo 任務
   ↓ analysis.ps1 (STEP 1)
start/task_N/          → 同步自 Odoo，含 original.txt
   ↓ analysis.ps1 (STEP 2)  ← Claude: 需求分析 → analysis.yaml
confirm/task_N/        → 等待使用者填寫 user_answer（MODE_A）或自動通過（MODE_B）
   ↓ analysis.ps1 (STEP 3a/3b) ← Claude: 生成 MODE_B 完整規格
analysis/task_N/       → 規格確認完成，含完整 analysis.yaml
   ↓ coding.ps1 (STEP 4)  ← Claude: 依規格實作模組
coding/task_N/         → 實作中 / 實作完成
   ↓ qa.ps1 (STEP 5-6)  ← Claude: QA 審查
final/task_N/          → 通過 QA，任務完成
```

## 觸發方式

| 方式 | 說明 |
|------|------|
| 輸入「開工」 | Hook 自動執行 `_pipeline_run.ps1`，Claude 接手所有 AI 任務 |
| 手動執行 PS1 | `pwsh -File analysis.ps1 / coding.ps1 / qa.ps1` |

## 關鍵檔案

| 檔案 | 用途 |
|------|------|
| `_pipeline_run.ps1` | 串接三個 PS1，hook 觸發入口 |
| `analysis.ps1` | STEP 1–3，同步 Odoo + 需求分析 |
| `coding.ps1` | STEP 4，實作分派 |
| `qa.ps1` | STEP 5–6，QA 檢查與結果處理 |
| `_common.ps1` | 共用函數庫（鎖、YAML、路徑）|
| `_PIPELINE_WAITING` | Claude 尚有 pending 任務的訊號標記 |

## 標記檔說明

| 標記 | 意義 |
|------|------|
| `pending_prompt.txt` | 待 Claude 執行的完整 prompt |
| `.pending_{stage}` | 對應階段正在等待 Claude |
| `.analysis_done` | Claude 初始分析完成 |
| `.answer_done` | user_answer 填寫完成，可進入 analysis/ |
| `.final_done` | MODE_B 最終規格完成，可進入 coding/ |
| `.implement_done` | 實作完成，可進入 QA |
| `.qa_done` | QA 完成 |
| `blocker.txt` | 發現阻礙，Claude 立即停止並報告 |
