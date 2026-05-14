# start/

從 Odoo API 同步下來、尚未分析的原始任務檔案。

## 檔案格式

```
task_<task_id>.txt
```

內容結構：
```
---id---
<task_id>
---title---
<任務標題>
---project---
<Odoo 專案名稱（對應 project_version_map.json）>
---description---
<需求描述（HTML 圖片已移除）>
---message---
<Chatter 歷史訊息（由新到舊）>
```

> `---project---` 欄位缺少時，`analysis.ps1` 會跳過該任務並顯示 `[SKIP]`。

## 流程

`analysis.ps1` 讀取此目錄 → 呼叫 requirements-analyst → 移至 `confirm/<case_id>/`。

已處理的任務不會重複建立（跨所有管線目錄檢查）。
