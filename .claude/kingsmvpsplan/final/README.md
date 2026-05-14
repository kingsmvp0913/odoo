# final/

測試全數通過，開發完成的案件。等待人工審核、驗證與佈署。

## 目錄結構

```
final/
└── task_<id>/
    ├── analysis.json      ← 最終規格
    ├── task_<id>.txt      ← 原始需求
    └── logs/
        └── error.log      ← 最後一次（通過前）的測試紀錄
```

---

## 人工操作說明（必要步驟）

### 步驟 1：程式碼審查

開啟 `analysis.json` 確認最終規格，再逐一審查生成的檔案：

```
odoo-{ver}/custom_addons/{module}/
├── __manifest__.py          ← 版本、依賴模組是否正確
├── models/models.py         ← 欄位定義、業務邏輯是否符合需求
├── views/                   ← UI 是否正確繼承
├── security/ir.model.access.csv  ← 存取權限是否完整
└── tests/test_main.py       ← 測試案例是否完整覆蓋需求
```

**審查要點：**
- `_inherit` 是否繼承正確的 Model
- 所有 Field 是否使用正確的 `string`、`tracking`、`required`
- View 使用 `inherit_id` + `xpath` 而非直接覆寫
- 無硬編碼的 ID 或路徑

---

### 步驟 2：安裝至測試環境驗證功能

```powershell
cd C:\odoo
# 安裝 / 更新模組
python odoo-{ver}/odoo-bin -c odoo-{ver}/odoo.conf -u {module} -d {db_name} --stop-after-init

# 啟動 Odoo 服務
python odoo-{ver}/odoo-bin -c odoo-{ver}/odoo.conf
```

在瀏覽器開啟 Odoo，手動測試：
- 黃金路徑（Happy Path）是否正常運作
- 邊界條件（空值、必填欄位未填）是否有適當提示
- 權限設定（不同 Role 的使用者是否看得到 / 做得到正確的操作）

---

### 步驟 3：建立 git commit

```powershell
cd C:\odoo
git add odoo-{ver}/custom_addons/{module}/
git commit -m "[{module}]: <說明為何這樣做，而非做了什麼>"
```

Commit message 範例：
```
[sale_approval]: 加入主管審核流程以符合稽核要求
[account_extend]: 新增成本中心欄位支援多部門費用分攤
```

**不要寫**：`新增欄位`、`修改 view`、`update models.py`（這是「做了什麼」，不是「為什麼」）

---

### 步驟 4：標記 Odoo 任務完成

登入 `https://odoo.ideaxpress.biz`，找到對應任務，將狀態標記為完成（Done）。

---

### 步驟 5：清除案件目錄（選擇性）

確認程式碼已 commit 且任務已關閉後，可刪除 final/ 下的案件目錄釋放空間：

```powershell
Remove-Item "C:\odoo\.claude\kingsmvpsplan\final\task_<id>" -Recurse -Force
```

---

## 若審查後發現問題

若審查發現程式碼需要大幅修改：

**小修正**（邏輯錯誤、欄位名稱）：直接編輯檔案後重新執行測試，確認通過後 commit。

**規格需重新分析**：
```powershell
# 將案件移回 confirm/ 重新啟動管線
Move-Item "C:\odoo\.claude\kingsmvpsplan\final\task_<id>" "C:\odoo\.claude\kingsmvpsplan\confirm\" -Force
```
在 `analysis.json` 補充說明後執行 `analysis.ps1`。
