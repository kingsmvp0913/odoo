# Odoo 開發環境

多版本 Odoo 本地開發環境，支援 v13 / v14 / v17 / v18 / v19。

---

## 目錄結構

```
C:\odoo\                        ← 本倉庫根目錄
├── odoo-13.0\                  ← Odoo 13 原始碼（含 auto_upgrade.py、odoo.conf）
├── odoo-14.0\
├── odoo-17.0\
├── odoo-18.0\
├── odoo-19.0\
├── venv_odoo13\                ← Python 虛擬環境（對應版本）
├── venv_odoo14\
├── venv_odoo17\
├── venv_odoo18\
├── venv_odoo19\
├── odoo_sample\                ← 樣板檔案（odoo.conf、auto_upgrade.py 範本）
├── 14cust_addons\              ← v14 舊有客製模組（歷史備存）
├── docs\                       ← 文件
└── .vscode\launch.json         ← VS Code 多版本啟動設定

C:\online_addons\               ← 所有版本的客製模組（開發主目錄）
├── 13\                         ← 版本專屬模組
├── 14\
├── 17\
├── 18\
├── 19\
├── e_service\                  ← 專案：e_service
├── odoo14_HRM\                 ← 專案：HRM（v14）
├── odoo14_IDX_addons\          ← 專案：IDX addons（v14）
├── odoo17_hungjou\             ← 專案：鴻久（v17）
└── odoo17_lingyue\             ← 專案：凌悅（v17）
```

> **規則**：所有客製程式碼只能寫在 `C:\online_addons\`，禁止修改 `odoo-XX.0\` 內的 Odoo 核心檔案。

---

## 安裝新版本（以 v17 為例）

### 1. 解壓縮 Odoo 原始碼

將 Odoo 原始碼解壓縮至 `C:\odoo\odoo-17.0\`。

### 2. 建立 Python 虛擬環境

各版本對應的 Python：

| Odoo 版本 | Python 版本 |
|-----------|-------------|
| 13        | 3.7         |
| 14        | 3.8         |
| 17        | 3.10        |
| 18        | 3.12        |
| 19        | 3.12        |

```powershell
py -3.10 -m venv C:\odoo\venv_odoo17
```

### 3. 啟動虛擬環境並安裝套件

```powershell
C:\odoo\venv_odoo17\Scripts\Activate.ps1
pip install -r C:\odoo\odoo-17.0\requirements.txt
```

### 4. 建立設定檔

複製 `odoo_sample\odoo.conf` 到 `odoo-17.0\odoo.conf`，依需求修改：

```ini
[options]
db_host     = localhost
db_port     = 5432
db_user     = odoo
db_password = 你的密碼
addons_path = addons, custom_addons, C:/online_addons/17, C:/online_addons/odoo17_hungjou
http_port   = 8069
timezone    = Asia/Taipei
```

`addons_path` 中填入 `C:\online_addons\` 下對應的資料夾，讓 Odoo 能掃到客製模組。

### 5. 建立 custom_addons 資料夾

```powershell
mkdir C:\odoo\odoo-17.0\custom_addons
```

### 6. 複製 auto_upgrade.py

複製 `odoo_sample\auto_upgrade.py` 到 `odoo-17.0\auto_upgrade.py`，修改頂部三個路徑常數：

```python
PYTHON   = "C:/odoo/venv_odoo17/Scripts/python.exe"
ODOO_BIN = "C:/odoo/odoo-17.0/odoo-bin"
ODOO_CONF = "C:/odoo/odoo-17.0/odoo.conf"
```

### 7. 設定 VS Code 啟動

在 `.vscode\launch.json` 的 `configurations` 陣列新增一個區塊（參考其他版本格式），指向對應版本的 `venv` 與 `auto_upgrade.py`。

---

## 日常啟動

在 VS Code 按 `F5` → 選對應版本（例如 **Run Odoo 17**）即可啟動。

`auto_upgrade.py` 會自動偵測 `C:\online_addons\` 下近 60 秒內有異動的模組，啟動時一併 `-u` 升級，不需手動指定模組名稱。

瀏覽器開啟：`http://localhost:8069`

---

## 使用注意

1. **auto_upgrade.py 僅限開發環境**，絕對不可用於正式或測試主機。
2. **客製程式碼只寫 `C:\online_addons\`**，不動 `odoo-XX.0\` 核心。
3. 修改 `.py` 或 schema XML 需重啟；純 View XML 按 F5 瀏覽器重整即可。
4. 建立新的測試資料庫後，記得安裝 **Web Environment Ribbon** 模組以防誤用。
5. 從正式環境複製資料庫到測試環境後，需關閉排程及所有可能產生費用的功能（如 Line 通知）。
6. Python 原生 `round()` 是銀行家捨入（30.5 → 30），台灣四捨五入請改用 `decimal.Decimal` + `ROUND_HALF_UP`。
7. 執行原生 SQL 前後須呼叫 `flush_model()` / `invalidate_model()` 避免 ORM cache 導致畫面不同步。

---

## 前置需求

- Windows 10/11
- PostgreSQL（帳號 `odoo`，密碼設定於 `odoo.conf`）
- 各版本對應的 Python（透過 `py` launcher 管理）
- Visual Studio Code + Python extension
