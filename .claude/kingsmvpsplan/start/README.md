# start/ — 任務入口

## 說明

從 Odoo 同步過來的原始任務，每個子目錄對應一個 Odoo project.task。

## 由誰建立

`analysis.ps1` STEP 1 呼叫 `curl.py` 自動建立。

## 目錄結構

```
start/
└── task_N/
    └── original.txt     ← Odoo 任務原始資料
```

## `original.txt` 格式

```
---id---
<task_id>
---title---
<任務標題>
---project---
<Odoo 專案名稱>
---stage---
<Odoo 階段名稱>
---description---
<任務描述 HTML>
---message---
<訊息歷史>
```

## 離開條件

`analysis.ps1` STEP 2 讀取 `original.txt` 後寫入 `pending_prompt.txt`，移至 `confirm/`。
