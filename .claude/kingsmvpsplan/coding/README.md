# coding/

測試骨架已就位且紅燈確認，等待 AI 實作程式碼使測試通過的案件。

## 執行流程（寫程式.ps1）

1. 讀取 `analysis.json` 與 `logs/error.log`（traceback）
2. 確認 `odoo_version` 已填寫，否則跳過
3. 呼叫 `senior-software-engineer`（Haiku），最多重試 3 次：
   - 將 traceback 附入 prompt
   - AI 輸出 `@FILE:/@FILE_END` 格式的實作程式碼
   - 寫入對應路徑
   - 執行測試
   - **綠燈** → 移至 `final/`
   - **仍紅燈** → 更新 `logs/error.log`，進行下一次重試
4. 3 次皆失敗 → 寫入 `blocker.txt` → rollback 至 `confirm/`

## 目錄結構

```
coding/
└── task_<id>/
    ├── analysis.json
    ├── logs/
    │   └── error.log      ← 最新一次測試失敗的 traceback
    └── debug/
        ├── prompt_<ts>_attempt<n>.txt    ← AI prompt 紀錄
        └── output_<ts>_attempt<n>.txt    ← AI 原始輸出紀錄
```

## 安全守衛

- 路徑含 `..`、絕對路徑（`/` 或 `C:\`）的檔案會被拒絕寫入
- `odoo_version` 為空時拒絕執行，不寫任何檔案
