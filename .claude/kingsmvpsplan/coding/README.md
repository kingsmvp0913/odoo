# coding/

測試骨架已就位且紅燈確認，等待 AI 實作程式碼使測試通過的案件。

## 執行流程（coding.ps1）

1. 讀取 `analysis.json`，確認 `odoo_version` 已填寫，否則跳過
2. 呼叫 `Get-OdooConf` 讀取 `odoo.conf`，取得 `test_db_name`
3. 用 `slim_spec.py` 壓縮 `analysis.json`（降低 token 用量）
4. 讀取 `logs/error.log`（traceback），組合 Prompt
5. 呼叫 `senior-software-engineer`（Haiku）**單次執行**：
   - AI 輸出 `@FILE:/@FILE_END` 格式的實作程式碼
   - 寫入對應路徑（含路徑安全守衛）
   - 執行測試（含 `-c odoo.conf` 與 `test_db_name`）
   - **綠燈** → 移至 `final/`
   - **RED** → 更新 `logs/error.log`，顯示 `[RED]`，**等待人工重新執行 coding.ps1**

> **注意**：Windows 分支為單次執行模式，**不自動重試，不 rollback 至 confirm/**。
> 測試仍失敗時，確認 `logs/error.log` 後手動再跑一次 `coding.ps1` 即可。

## 目錄結構

```
coding/
└── task_<id>/
    ├── analysis.json
    ├── logs/
    │   └── error.log      ← 最新一次測試失敗的 traceback
    └── debug/
        ├── prompt_<ts>_attempt1.txt    ← AI prompt 紀錄
        └── output_<ts>_attempt1.txt    ← AI 原始輸出紀錄
```

## 安全守衛（雙重）

- **呼叫端**：路徑含 `..`、以 `/` 或磁碟代號 `[A-Za-z]:\` 開頭的檔案直接拒絕
- **Out-AtomicFile**：`GetFullPath` 解析後確認最終路徑仍在 `baseDir` 範圍內（防逃逸）
- `odoo_version` 或 `test_db_name` 為空時拒絕執行
