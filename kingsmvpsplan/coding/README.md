# coding/ — 實作中

## 說明

Claude 正在依 `analysis.yaml` 規格實作 Odoo 模組的任務。

## 目錄結構

```
coding/
└── task_N/
    ├── original.txt         ← 原始 Odoo 資料
    ├── analysis.yaml        ← 完整技術規格（實作依據）
    ├── system/
    │   ├── .analysis_done
    │   ├── .answer_done
    │   ├── .final_done
    │   ├── .implement_done  ← Claude 實作完成後寫入
    │   ├── .qa_done         ← QA 通過後寫入
    │   ├── pending_prompt.txt ← 等待 Claude 實作或 QA 時存在
    │   └── blocker.*.txt    ← 發現阻礙時 Claude 寫入，立即停止
    └── log/
        ├── qa_report.yaml   ← Claude QA 產出的審查報告
        └── done_prompt.txt  ← 完成後保留的執行記錄
```

## 實作輸出位置

模組程式碼寫入 `C:\online_addons\{project_name}\{module_name}\`（由 `Get-ModulePath` 解析）。

## 流程

1. `coding.ps1` STEP 4 偵測到 `system/.final_done` → 寫 `system/pending_prompt.txt` → 移至本目錄
2. Claude 讀取 `analysis.yaml` → 實作模組 → 寫 `system/.implement_done`
3. `qa.ps1` STEP 5 偵測到 `system/.implement_done` → 寫 QA `system/pending_prompt.txt`
4. Claude 執行 QA → 產出 `log/qa_report.yaml` → 寫 `system/.qa_done`
5. `qa.ps1` STEP 6 讀取 `log/qa_report.yaml`：
   - `status: PASSED` → 移至 `final/`
   - 其他 → 退回 `confirm/`（清除所有標記）

## 離開條件

QA 通過（`log/qa_report.yaml` 中 `status: PASSED`），由 `qa.ps1` 移至 `final/`。
