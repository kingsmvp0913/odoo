# Odoo17 CE  凌越生醫x艾創點 專案

## 專案概述

本專案為基於 Odoo 17 社群版開發的企業資源規劃系統，專為凌越生醫公司打造，整合了商務管理、Workflow ERP 同步、電商平台、OCR 辨識、物流串接等功能。

## 系統環境

- **Odoo 版本**: 17.0 (Community Edition)
- **Python 版本**: 3.10+
- **資料庫**: PostgreSQL 12+
- **作業系統**: Linux / Windows

## 專案結構

```
odoo17_lingyue/
├── idx_ebs/                   # 商務管理平台主模組
├── idx_wf_sync/          # Workflow ERP 同步模組
├── queue_job/            # 背景任務佇列模組
├── requirements.txt  # Python 套件依賴
├── README.md         # 本檔案
└── README_MSSQL.md      # MSSQL 同步詳細說明
```
---

## 模組清單與功能說明

### 1. idx_ebs (IDX 商務管理平台)

**模組名稱**: `idx商務管理平台`  
**技術名稱**: `idx_ebs`

#### 核心功能

##### 1.1 訂單管理系統
- **多來源訂單整合**: 支援 QR-code、B2B 電商、OCR 辨識、報價單等多種訂單來源
- **訂單生命週期管理**: 
  - 報價中 → 報價已送出 → 訂單待確認 → 已收件 → 訂單已成立 → WF已確認 → 已檢驗 → 報告完成 → 報告已寄出
- **WF ERP 雙向同步**: 訂單資料可同步至鼎新 Workflow ERP
- **送檢單/報告管理**: 支援送檢單上傳、報告產出與批次下載
- **出貨歷程追蹤**: 自動同步 WF 出貨單資訊

##### 1.2 OCR 辨識功能
- **人類醫學檢測單辨識**: 自動辨識送檢單位、姓名、性別、檢測項目等資訊
- **小動物檢測單辨識**: 自動辨識送檢醫院、寵物姓名、送檢種類等資訊
- **加密傳輸**: 使用 AES 加密與外部 OCR API 通訊
- **批次處理**: 支援多張圖片同時上傳辨識

##### 1.3 電商平台 (B2B)
- **產品分類管理**: 支援多層級產品分類與檢測類別
- **購物車篩選**: 依檢測類別快速篩選產品
- **會員制度**: 整合 Loyalty 忠誠度計畫
- **問卷系統**: 整合 Survey 模組進行客戶調查
- **Portal 入口**: 客戶可透過 Portal 查詢訂單與下載報告

##### 1.4 物流串接
- **黑貓宅急便 API**: 查詢物流狀態與配送進度
- **中華郵政 API**: 支援郵政物流查詢
- **物流狀態快取**: 避免重複查詢，提升效能

##### 1.5 OneDrive 整合
- **檔案同步**: 自動從 OneDrive 同步對帳單與報告檔案
- **批次下載**: 支援批次下載指定目錄下的檔案
- **Token 管理**: 自動管理 OAuth2 Token 刷新機制

##### 1.6 庫存管理
- **批號管理**: 支援產品批號與效期追蹤
- **庫存同步**: 從 WF ERP 同步庫存數量與批號資訊
- **電商倉庫**: 支援多倉庫管理與電商專用倉

##### 1.7 客戶關係管理 (CRM)
- **客戶分類**: 支援多維度客戶分類標籤
- **關聯公司**: 管理客戶的關聯企業資訊
- **稅別管理**: 整合 WF 稅別碼與 Odoo 稅別對應

##### 1.8 忠誠度計畫
- **優惠券系統**: 支援折扣碼與促銷活動

#### 依賴模組
- mail (郵件)
- base (基礎)
- sale_management (銷售管理)
- website_sale (電商銷售)
- website_sale_stock (電商庫存)
- website_sale_loyalty (電商忠誠度)
- stock (庫存)
- crm (客戶關係管理)
- product_expiry (產品效期)
- idx_wf_sync (Workflow 同步)
- queue_job (背景任務)
- loyalty (忠誠度)
- survey (問卷)
- portal (客戶入口)
- bus (訊息匯流排)

#### Python 套件依賴
- `pycryptodome`: AES 加密解密 (OCR API 通訊)
- `qrcode[pil]`: QR Code 產生
- `Pillow`: 圖片處理
- `XlsxWriter`: Excel 報表產出
- `openpyxl`: Excel 檔案讀取

---

### 2. idx_wf_sync (IDX Workflow 同步模組)

**模組名稱**: `idx同步Workflow`  
**技術名稱**: `idx_wf_sync`

#### 核心功能

##### 2.1 MSSQL 資料庫連線
- 支援連線至鼎新 Workflow / SmartERP 的 MSSQL 資料庫
  - ODBC Driver 18 for SQL Server (Windows)

##### 2.2 雙向資料同步
- **Odoo → WF**: 將 Odoo 資料寫入 WF (新增/更新)
- **WF → Odoo**: 從 WF 回寫 Odoo (主表更新 + 副表增刪修)
- **欄位對照表**: 視覺化設定 Odoo 與 WF 欄位對應關係

##### 2.3 單號自動編碼
- 支援日編碼 / 月編碼
- 格式: 前綴 + 年份 + 月/日 + 流水號
- 自動回寫 Odoo 單別與單號

##### 2.4 同步後更新
- 支援同步成功後自動更新 Odoo 欄位
- 可記錄同步時間、執行者、次數等資訊

##### 2.5 批次同步
- 支援批次同步產品、訂單、庫存等資料
- 支援條件篩選 (日期區間、品號等)
---

### 3. queue_job (背景任務佇列)

**模組名稱**: `Queue Job`  
**技術名稱**: `queue_job`

#### 功能說明
- 提供非同步任務執行機制
- 避免長時間操作阻塞使用者介面
- 支援任務重試與錯誤處理

#### 應用場景
- 大量資料同步
- 批次報表產生
- 外部 API 呼叫

---

## 安裝與部署

### 1. 系統需求

#### Python 套件
```bash
pip install -r requirements.txt
```

requirements.txt 內容:
```
pyodbc
pycryptodome
qrcode[pil]
```

#### ODBC Driver (用於 WF 同步)

**Windows**:
- 下載並安裝 [Microsoft ODBC Driver 18 for SQL Server](https://learn.microsoft.com/zh-tw/sql/connect/odbc/download-odbc-driver-for-sql-server)

### 2. 模組安裝

1. 將 `idx_ebs`、`idx_wf_sync`、`queue_job` 複製到 Odoo addons 目錄
2. 重啟 Odoo 服務
3. 進入 Odoo 後台 → 應用程式 → 更新應用程式清單
4. 搜尋並安裝:
   - `idx商務管理平台`
   - `idx同步Workflow`
   - `Queue Job`

### 3. 初始化資料

模組安裝時會自動載入以下初始資料:
- CRM 類別
- 客戶分類標籤
- 產品分類
- 計量單位類別
- 預設產品範本
- 問卷範本
- 序號規則

---

## 系統設定

### 1. Workflow ERP 同步設定

路徑: `設定 → 一般設定 → MSSQL 資料庫設定`

#### 必填欄位
- **SQL Server 驅動程式**: 選擇對應的 ODBC Driver
- **Server IP**: WF MSSQL 伺服器 IP 位址
- **WF 帳號**: MSSQL 登入帳號
- **WF 密碼**: MSSQL 登入密碼
- **資料建立者帳號**: WF 系統的 CREATOR 欄位值
- **資料建立者群組**: WF 系統的 USR_GROUP 欄位值

#### 權限設定
- 啟用「啟用同步 Workflow」開關
- 確保 MSSQL 帳號具備 SELECT、INSERT、UPDATE、DELETE 權限

#### 公司設定
路徑: `設定 → 公司 → 編輯公司`
- **MSSQL資料庫代號**: 例如 `EBS_TEST` (公司別)

### 2. OneDrive 同步設定

路徑: `設定 → 一般設定 → OneDrive 設定`

#### 必填欄位
- **啟用同步 OneDrive**: 勾選啟用
- **OneDrive 帳號 (Email)**: 例如 `ebl@ebs.com.tw`
- **Tenant ID**: Azure AD 租戶 ID
- **Client ID**: Azure AD 應用程式 ID
- **Client Secret**: Azure AD 應用程式密鑰

### 3. 黑貓宅急便串接設定

路徑: `設定 → 一般設定 → 黑貓串接設定`

#### 必填欄位
- **啟用黑貓串接**: 勾選啟用
- **黑貓 API 端點**: 例如 `https://api.suda.com.tw`
- **契約客戶代號**: 黑貓提供的客戶代號
- **契約客戶授權碼**: 黑貓提供的授權碼

⚠️ **注意**: 需向黑貓宅急便申請 API 使用權限

### 4. 中華郵政串接設定

路徑: `設定 → 一般設定 → 中華郵政設定`
- **串接資訊**:
- **API & 參數 (`TxnCode`, `BizCode` 等) 檔案位置**: `idx_ebs/services/post_service.py`
- **內容**: `url = "https://postserv.post.gov.tw/pstmail/EsoafDispatcher"`

### 5. OCR 辨識設定

路徑: `設定 → 一般設定 → OCR 辨識設定`

#### 必填欄位
- **啟用 OCR 辨識**: 勾選啟用
- **OCR 辨識 API URL**: OCR 服務端點
- **OCR 辨識 API Token**: API 驗證 Token
- **OCR 辨識金鑰**: AES 加密金鑰 (Key)
- **OCR 辨識向量**: AES 加密向量 (IV)
- **OCR 辨識加密金鑰**: 傳送給 OCR API 的加密資料

⚠️ **注意**: OCR 服務需另外部署或使用第三方服務

---

## 重要配置說明
### 定時任務 (Cron Jobs)
####  WF 訂單及出貨資訊同步

**執行頻率**: 每小時  
**執行方法**: `sale.order._cron_action_get_wf_and_sale_info()`  
**說明**: 自動同步 WF 訂單狀態與出貨單資訊

**修改方式**: 
- 路徑: `設定 → 技術 → 排程動作`
- 搜尋: `WF 訂單及出貨資訊同步`
- 調整執行間隔

---

## 資料對照表

### Odoo ↔ WF ERP 欄位對應
主要對照表:
- **訂單主表**: `sale.order` ↔ `COPTC`
- **訂單明細**: `sale.order.line` ↔ `COPTD`
- **產品主檔**: `product.template` ↔ `INVMB`
- **庫存主檔**: `stock.quant` ↔ `INVMC` / `INVMF`
- **客戶主檔**: `res.partner` ↔ `COPMA`

---

## 常見問題與排除

### 1. WF 同步相關

#### Q: 同步時出現「連線失敗」錯誤
**A**: 
1. 檢查 ODBC Driver 是否正確安裝
2. 確認 Server IP、帳號、密碼是否正確
3. 檢查防火牆是否開放 MSSQL 埠 (預設 1433)
4. 測試 MSSQL 連線: `telnet <server_ip> 1433`

#### Q: 單號重複錯誤
**A**: 
1. 檢查 WF 現有資料的最大單號
2. 確認單號規則設定是否正確
3. 調整流水號起始值

### 2. OCR 辨識相關

#### Q: OCR 辨識失敗或超時
**A**: 
1. 檢查 OCR API URL 是否正確
2. 確認 API Token 是否有效
3. 檢查圖片檔案大小 (建議 < 5MB)
4. 確認網路連線正常

### 3. OneDrive 同步相關

#### Q: Token 過期錯誤
**A**: 
1. Token 會自動刷新，若持續失敗請檢查 Client Secret 是否過期
2. 重新產生 Client Secret 並更新設定

#### Q: 找不到檔案或目錄
**A**: 
1. 確認 OneDrive 帳號是否正確
2. 檢查檔案路徑格式 (使用 `/` 分隔)
3. 確認檔案是否存在於指定目錄

### 4. 物流串接相關

#### Q: 黑貓 API 查詢失敗
**A**: 
1. 確認契約客戶代號與授權碼是否正確
2. 檢查 API 端點是否正確
3. 確認物流編號格式是否正確

---

## 開發與維護

### 目錄結構說明

#### idx_ebs 模組結構
```
idx_ebs/
├── controllers/          # HTTP 控制器
│   ├── idx_ocr.py       # OCR 辨識控制器
│   ├── cart_detects.py  # 購物車檢測控制器
│   └── portal.py        # Portal 入口控制器
├── models/              # 資料模型
│   ├── sale_order.py    # 訂單模型
│   ├── res_partner.py   # 客戶模型
│   ├── product_template.py  # 產品模型
│   └── ...
├── services/            # 外部服務
│   ├── onedrive_service.py  # OneDrive 服務
│   ├── tcat_service.py      # 黑貓物流服務
│   └── post_service.py      # 郵政服務
├── wizards/             # 精靈視窗
│   ├── idx_wf_sync_wizard.py  # WF 同步精靈
│   └── sync_onedrive.py       # OneDrive 同步精靈
├── views/               # 視圖定義
│   ├── back/           # 後台視圖
│   └── front/          # 前台視圖
├── data/               # 初始資料
├── security/           # 權限設定
└── static/             # 靜態資源
    └── src/
        ├── js/         # JavaScript
        ├── css/        # 樣式表
        └── xml/        # QWeb 模板
```

#### idx_wf_sync 模組結構
```
idx_wf_sync/
├── models/
│   ├── wf_mapping.py         # 對照表核心邏輯
│   ├── res_config_setting.py  # 系統設定
│   └── res_company.py        # 公司設定
├── views/
│   ├── wf_mapping_views.xml  # 對照表視圖
│   └── res_config_setting.xml  # 設定視圖
└── security/                 # 權限設定
```

## 附錄

### 相關文檔
- [README_MSSQL.md](./README_MSSQL.md) - MSSQL 同步詳細說明
- [requirements.txt](./requirements.txt) - Python 套件依賴清單

---
