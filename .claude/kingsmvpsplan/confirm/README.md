# confirm/

需求分析中、等待人工確認或補充資料的案件。

## 目錄結構

```
confirm/
└── task_<id>/
    ├── analysis.json      ← AI 產出的規格（MODE_A 或 MODE_B）
    ├── task_<id>.txt      ← 原始任務（從 start/ 搬來）
    ├── patches/           ← 預留
    ├── process.lock       ← 執行期間鎖
    └── analysis.json.bak  ← 重新分析前的備份（存在時）
```

## 人工操作說明

### 當 `execution_mode == "MODE_A"` 時

開啟 `analysis.json`，找到 `clarification_channel` 陣列，在對應問題的 `user_answer` 欄位填入答案：

```json
{
  "id": 1,
  "category": "odoo_version",
  "question": "請確認目標 Odoo 版本？",
  "user_answer": "17.0"   ← 填入此欄
}
```

填完存檔後，再次執行 `分析.ps1`，AI 將驗證答案並嘗試升級至 MODE_B。

### Odoo 版本為必填項目

`inferred_target.odoo_version` 必須有值，否則案件無法晉升 testcoding/。

### 當 `execution_mode == "MODE_B"` 且 `is_complete == true` 時

`分析.ps1` 自動將案件移至 `testcoding/`，無需手動操作。

## 失敗回滾

`寫測試.ps1` 或 `寫程式.ps1` 執行失敗時，案件會帶著 `blocker.txt` 回滾至此目錄。
