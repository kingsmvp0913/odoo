# analysis/ — 規格確認

## 說明

答案確認完成、等待 Claude 產出 MODE_B 完整技術規格的任務。

## 目錄結構

```
analysis/
└── task_N/
    ├── original.txt         ← 原始 Odoo 資料
    ├── analysis.yaml        ← 含使用者答案，Claude 將更新為完整規格
    ├── .analysis_done       ← 初始分析完成
    ├── .answer_done         ← 答案確認完成
    ├── .final_done          ← 最終規格完成（Claude 寫入後離開本目錄）
    └── pending_prompt.txt   ← 等待 Claude 產出完整規格時存在
```

## `analysis.yaml` 完整規格結構（.final_done 後）

```yaml
execution_mode: MODE_B
module: my_module
odoo_version: "17.0"
project_name: MyProject
technical_specification:
  models: [...]
  views: [...]
  fields: [...]
  business_logic: "..."
```

## 流程

1. `analysis.ps1` STEP 3b 偵測到 `.answer_done` 存在但 `.final_done` 不存在
2. 寫入 `pending_prompt.txt` 要求 Claude 產出完整 `technical_specification`
3. Claude 更新 `analysis.yaml` 並寫入 `.final_done`
4. `coding.ps1` STEP 4 偵測到 `.final_done` → 移至 `coding/`

## 離開條件

`.final_done` 存在（Claude 完成最終規格產出）。
