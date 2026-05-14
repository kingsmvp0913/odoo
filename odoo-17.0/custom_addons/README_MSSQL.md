# IDX MSSQL 資料串接應用 

## 1\. 簡介
本模組提供 Odoo 與 鼎新 Workflow / SmartERP (以下簡稱 WF) 之 MSSQL 資料雙向對照、同步與單號編碼規則管理。  
透過可視化「檔案對照表」(Mapping) 設定，即可：
\- 將 Odoo 資料寫入 WF (建立 / 更新)  
\- 從 WF 回寫 Odoo (主表僅更新，副表做增刪修同步)  
\- 支援交易單號自動編碼（日期＋流水碼）  
\- 自動於同步後回填 Odoo 指定欄位（時間、使用者、計數等）

## 2\. 架構概覽
```
+-------------+        pyodbc / ODBC Driver       +------------------+
|   Odoo ORM  |  <-------------------------------->  MSSQL (WF DB)   |
+------+------+\                                     +--------+-------+
       |       \-- Mapping 定義 (wf.mapping / line / sub / sync.info)
       |
       +--> _odoo_to_wf_create / _odoo_to_wf_update
       +--> _wf_to_odoo_sync / _wf_to_odoo_update_part
```

## 3\. 主要模型
\- `wf.mapping`：主檔對照表（定義 WF 表、Odoo 模型、單號規則、同步後更新規則）  
\- `wf.mapping.line`：欄位級對照；支援多種同步型態 (F/C/N/W/D/B/A/S)  
\- `wf.mapping.sub`：副表對照（主從結構、一對多同步、主鍵關聯欄位）  
\- `wf.mapping.sync.info`：同步成功後，回填 Odoo 欄位策略  
\- 系統設定來源：`res.config.settings` 讀取 WF 連線參數（server\_ip / username / password / creator / usr\_group）

## 4\. 同步核心方法（供程式呼叫）
\- `_odoo_to_wf_create(wf_model, record_ids, database, wf_company)`：Odoo → WF 新增  
\- `_odoo_to_wf_update(wf_model, record_ids, database, wf_company)`：Odoo → WF 更新（存在才改）  
\- `_wf_to_odoo_sync(wf_model, wf_domain, wf_db, wf_main_domain=None, wf_line_domain=None)`：WF → Odoo 主表更新＋副表增刪修  
\- `_wf_to_odoo_update_part(wf_model, return_fields, key_fields, key_values_list, odoo_model, odoo_key_fields, wf_db, lines)`：依多組鍵值批次回填  
內部輔助：`_get_wf_value`、`_wf_value_to_odoo_value`、`_batch_insert_records`、`_batch_update_records`、`_check_duplicate_key`、`_update_sync_info_fields`

## 5\. 欄位對照重點 (wf.mapping.line)
| 同步方式 | 說明 |
|---------|------|
| F | 直接取 Odoo 欄位值，支援 many2one 取關聯最終欄位 |
| C | 固定文字 |
| N | 固定數值 |
| W | 透過 WF 其他表做二次查詢 |
| D | 動態日期格式（YYYY / YY / YYYYMM / YYYYMMDD 等） |
| B | 固定 Y / N |
| A | 以占位 `{FIELD}` 串接多欄位值 |
| S | 單一空白字元 |

`wf_key`：組成 WF 主鍵條件，用於重複檢查與比對。  

## 6\. 單號自動編碼規則 (main_type='3')
\- 需設定：`code_type`（日編=1 / 月編=2）、`year_digits`（2 / 4）、`serial_digits`（流水碼長度）、`wf_slip`、`wf_s_field`、`wf_b_field`、對應 Odoo 欄位 `odoo_s_field`、`odoo_b_field`  
\- 生成格式：前綴(年＋月/日)＋流水碼（總長不超過 11）  
\- 每筆主表寫入後自增，並回寫 Odoo 單別與單號

## 7\. 同步後更新 (wf.mapping.sync.info)
`value_type` 支援：today / now / user / fixed_text / fixed_number / bool_true / bool_false / plus  
應用情境：記錄同步時間、執行者、次數累加、狀態旗標等。

## 8\. 安裝前置需求
1\. 系統  
\- Odoo 17
\- 伺服器可連線 WF MSSQL 埠  
2\. ODBC Driver  
\- 安裝 Microsoft ODBC Driver 18 (或 17) for SQL Server  (For Linux)
\-官方安裝步驟 https://reurl.cc/Mz6ZvW 
3\. Python 套件
  ```pip install pyodbc```
4\. 權限  
\- MSSQL 使用者需具備：SELECT / INSERT / UPDATE / DELETE 權限

## 9\. 安裝步驟
1\. 放置模組於 `addons` 路徑並啟用  
2\. 於 Odoo Apps 安裝 `IDX MSSQL資料串接應用`  
3\. 至「一般設定 → MSSQL資料庫設定區塊」輸入：
   \- `server_ip`  
   \- `username`  
   \- `password`  
   \- `creator`（WF 欄位 CREATOR 填值）  
   \- `usr_group`（WF 欄位 USR_GROUP 填值）  
4\. 確認安裝 pyodbc 與 ODBC Driver  
5\. 測試連線（可先建立一個 mapping 後試同步）

## 10\. 建立對照表流程
1\. 新增 `MSSQL檔案對照表`（wf.mapping）  
2\. 設定：`wf_model_id`、`wf_model_name`、`wf_prid`、`odoo_model_id`、`extra_domain`（選）  
3\. 新增「主欄位對照」行：  
   \- 勾選必要 `wf_key`  
   \- 設定 `snyc_type` 與對應來源  
4\. 若為交易（main_type='3'）設定單號規則頁籤  
5\. 若含副表：於「副表清單」新增 `wf.mapping.sub`（主從關聯 key 對應）  
6\. 同步資訊：按需新增 `wf.mapping.sync.info`（回寫 Odoo）  
7\. 以程式或自建按鈕呼叫 `_odoo_to_wf_create` / `_odoo_to_wf_update` 或 `_wf_to_odoo_sync`

## 11\. WF → Odoo 副表同步策略
\- 以副表 key 做集合差異：  
  \- WF 存在 / Odoo 不存在 → create  
  \- 兩邊皆存在 → write  
  \- Odoo 存在 / WF 不存在 → unlink  
\- 主表不存在時該副表群組跳過  
\- 可用 `wf_line_domain` 擴充副表 where

## 12\. 錯誤處理與日誌
\- 連線 / SQL 例外統一轉為 `ValidationError`  
\- `_handle_error` 紀錄 `_logger.error`  
\- 批次同步若部分失敗：彙整錯誤訊息一次拋出  
\- 建議檢視 Odoo log 追蹤細節

## 13\. 常見問題
| 問題 | 說明 |
|------|------|
| 單號重複 | 確認 WF 現有資料最大碼與規則是否一致 |
| many2one 無法回填 | 檢查 `odoo_related_id` / 第二 key 設定 |
| 副表未同步 | 確認 `wf_parent_field` / `wf_body_field` 對應欄位是否齊全 |
| 日期錯誤 | 確認 WF 欄位實際格式；若非 YYYYMMDD 需調整解析邏輯 |
| 連線失敗 | 驗證 ODBC Driver / 帳號權限 / 防火牆 / 參數設定 |

## 14\. 程式呼叫示例（自定義按鈕） 維護者可依實際客製介面（如新增 UI 按鈕）補充操作說明。
``` 
    def action_sync_wf(self):
        success_records = []
        # 執行同步
        result = self.env['wf.mapping'].sudo()._odoo_to_wf_create(
            wf_model='COPTC',
            record_ids=self.ids,
            database=self.company_id.wf_db,
            wf_company=self.company_id.wf_company
        )
        message = _("訂單已同步WF") if result else _("同步失敗，請檢查相關設定或資料。")
        message_type = 'success' if result else 'danger'
        sticky = False

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'context': dict(self._context, active_ids=self.ids),
            'target': 'new',
            'params': {
                'message': message,
                'type': message_type,
                'sticky': sticky,
                'next': {'type': 'ir.actions.act_window_close'} if result else None,
            }
        }
```
## 15\. 目前提供的MSSQL連結版本是 ODBC Driver 18 for SQL Server
若與此不同版本，需到wf_mapping.py 調整_get_connection_parameters。


