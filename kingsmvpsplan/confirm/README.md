# confirm/ — 需求確認

## 說明

Claude 完成初始需求分析後等待確認的任務。

## 目錄結構

```
confirm/
└── task_N/
    ├── original.txt         ← 原始 Odoo 資料
    ├── analysis.yaml        ← Claude 產出（含 user_answer 欄位）
    ├── system/
    │   ├── .analysis_done   ← Claude 分析完成標記
    │   ├── .answer_done     ← 答案確認完成標記（PS1 寫入）
    │   └── pending_prompt.txt ← 等待 Claude 執行時存在
    └── log/
        └── back_reason.txt  ← 退回原因（從後段退回時才有）
```

## `analysis.yaml` 關鍵欄位

```yaml
execution_mode: MODE_A   # MODE_A = 需填 user_answer；MODE_B = 自動通過
module: my_module
odoo_version: "17.0"
project_name: MyProject
questions:
  - id: q1
    question: "..."
    user_answer: null    # MODE_A：使用者需填寫此欄位
```

## 流程

1. `system/pending_prompt.txt` 存在 → Claude 執行初始分析，產出 `analysis.yaml` + `system/.analysis_done`
2. MODE_A：等待使用者在 `analysis.yaml` 填寫 `user_answer`
3. MODE_B：PS1 自動偵測到 `execution_mode: MODE_B` 即通過
4. `analysis.ps1` STEP 3a 確認答案完整 → 寫 `system/.answer_done` → 移至 `analysis/`

## 離開條件

所有 `user_answer` 填寫完畢（或 MODE_B），且 `system/.analysis_done` 存在。
