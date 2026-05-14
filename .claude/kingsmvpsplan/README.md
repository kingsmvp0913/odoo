# AI 開發管線 (V2)

## 架構總覽

```
Odoo Task API
     │
     ▼
┌─────────┐   分析.ps1    ┌─────────┐   分析.ps1    ┌────────────┐
│  start/ │ ────────────► │ confirm/ │ ────────────► │ testcoding/ │
└─────────┘               └─────────┘               └────────────┘
                          (等待填答)                       │ 寫測試.ps1
                                                           ▼
                          ┌─────────┐   寫程式.ps1  ┌─────────┐
                          │  final/ │ ◄──────────── │ coding/ │
                          └─────────┘               └─────────┘
```

## 腳本說明

| 腳本 | 觸發時機 | 功能 |
|------|----------|------|
| `分析.ps1` | 手動執行 | 從 Odoo 抓任務 → start/；呼叫 requirements-analyst → confirm/；確認 MODE_B 後推進 testcoding/ |
| `寫測試.ps1` | 手動執行 | 呼叫 test-agent 生成測試骨架；驗證紅燈後推進 coding/ |
| `寫程式.ps1` | 手動執行 | 呼叫 senior-software-engineer 實作；綠燈後推進 final/ |

## 共用函式庫

`_common.ps1` — 三支腳本皆 dot-source，包含：
- `Acquire-Lock` / `Release-Lock` — 檔案鎖，防並發衝突
- `Convert-MultiFileTags` — 解析 AI `@FILE:/@FILE_END` 輸出
- `Write-PipelineFile` — 管線內部日誌原子寫入
- `Out-AtomicFile` — AI 產出檔案原子寫入（含路徑白名單與 odoo_version 守衛）
- `Run-TestProcess` — 執行測試並回傳結構化結果

## 管線規則

- **Odoo 專案必須填寫 `odoo_version`**，否則 requirements-analyst 停留 MODE_A，後續腳本拒絕執行
- 檔案一律寫入 `odoo-{odoo_version}/custom_addons/{module}/`，無 fallback
- TDD 嚴格執行：testcoding → coding 必須確認紅燈；coding → final 必須確認綠燈
- 任何階段失敗 → 寫入 `blocker.txt` → rollback 至 confirm/
- Claude Timeout：300 秒；重試：最多 3 次，指數退避

## Agents

| Agent | 模型 | 用途 |
|-------|------|------|
| `requirements-analyst.md` | Sonnet | 需求轉 JSON spec（MODE_A/B） |
| `test-agent.md` | Sonnet | 依 analysis.json 生成測試骨架 |
| `senior-software-engineer.md` | Haiku | 依測試失敗 traceback 寫實作程式碼 |
