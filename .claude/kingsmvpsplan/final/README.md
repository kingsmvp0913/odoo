# final/ — 完成任務

## 說明

通過 QA 審查的任務，實作已部署至模組目錄。

## 目錄結構

```
final/
└── task_N/
    ├── original.txt         ← 原始 Odoo 資料
    ├── analysis.yaml        ← 完整規格（含 technical_specification）
    ├── qa_report.yaml       ← QA 報告（status: PASSED）
    ├── .analysis_done
    ├── .answer_done
    ├── .final_done
    ├── .implement_done
    └── .qa_done
```

## `qa_report.yaml` 格式

```yaml
status: PASSED
summary: "所有檢查項目通過"
checks:
  - item: "Model 結構符合規格"
    result: PASS
  - item: "View XML 語法正確"
    result: PASS
```

## 到達此目錄後

- 模組程式碼已寫入 `C:\online_addons\{project_name}\{module_name}\`
- Odoo 任務已收到 Pipeline 完成通知（`Send-OdooTaskMessage`）
- 任務不再被 pipeline 重複處理（`skipIds` 機制）
