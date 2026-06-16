# final/ — 完成任務

## 說明

通過 QA 審查的任務，實作已部署至模組目錄。

## 目錄結構

```
final/
└── task_N/
    ├── original.txt         ← 原始 Odoo 資料
    ├── analysis.yaml        ← 完整規格（含 technical_specification）
    ├── system/
    │   ├── .analysis_done
    │   ├── .answer_done
    │   ├── .final_done
    │   ├── .implement_done
    │   └── .qa_done
    └── log/
        ├── qa_report.yaml   ← QA 報告（status: PASSED）
        └── done_prompt.txt  ← 最後一次執行記錄
```

## `log/qa_report.yaml` 格式

```yaml
status: PASSED
checked_at: "2025-01-01T00:00:00"
items:
  - check: "model_exists"
    passed: true
    message: ""
  - check: "no_sql_in_loops"
    passed: true
    message: ""
issues: []
```

## 到達此目錄後

- 模組程式碼已寫入 `C:\online_addons\{project_name}\{module_name}\`
- Odoo 任務已收到 Pipeline 完成通知（`Send-OdooTaskMessage`）
- 任務不再被 pipeline 重複處理（`skipIds` 機制）
