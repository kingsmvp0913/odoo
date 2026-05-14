# final/

測試全數通過，開發完成的案件。

## 後續動作（手動）

1. 確認 `odoo-{version}/custom_addons/{module}/` 下的程式碼符合預期
2. 安裝模組至測試環境驗證功能
3. 建立 git commit：`[{module}]: <說明為何，而非做了什麼>`
4. 在 Odoo 平台將對應任務標記為完成

## 目錄結構

```
final/
└── task_<id>/
    ├── analysis.json      ← 最終規格
    ├── task_<id>.txt      ← 原始需求
    └── logs/
        └── error.log      ← 最後一次（通過前）的測試紀錄
```
