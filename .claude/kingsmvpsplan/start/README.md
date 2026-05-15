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

---

## 人工操作說明

### 初次使用前：設定 project_version_map.json

在開始任何管線流程前，需先確認 `C:\odoo\.claude\project_version_map.json` 已設定所有相關專案：

```json
{
  "project_version_map": {
    "2508014 凌越生醫-商務管理平台": "17.0"
  }
}
```

專案名稱必須與 Odoo 任務的 `project` 欄位**完全一致**（包含空格與特殊字元）。
尚未設定的專案，執行時會顯示 `[CONFIG REQUIRED]` 並跳過。

### 觸發任務同步與分析

```powershell
cd C:\odoo
.\.claude\analysis.ps1
```

每次執行都會：
1. 從 Odoo API 拉取指派給您的任務（已存在管線中的任務自動略過）
2. 對所有 `start/` 的新任務呼叫 AI 進行初步分析
3. 對所有 `confirm/` 中已填答的案件重新驗證並嘗試推進

### 任務未出現在 start/ 時

- 確認 Odoo 平台的任務已指派給 `USER_ID = 79`（`analysis.ps1` 預設只拉取該使用者的任務）
- 確認環境變數 `ODOO_PASSWORD` 已正確設定
- 確認網路可連到 `https://odoo.ideaxpress.biz`

### 手動建立任務檔案

若需繞過 API 同步，可手動在 `start/` 建立符合格式的 `task_<id>.txt`，執行 `analysis.ps1` 後會自動處理。
