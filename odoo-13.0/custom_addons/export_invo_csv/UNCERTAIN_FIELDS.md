# 不確定欄位清單

待確認後更新此檔，並同步修改 `models/export_invo_csv.py` 與 `controllers/main.py`。

| # | 段 | 欄位 | 目前預設 | 待確認問題 |
|---|---|------|---------|-----------|
| 1 | M | 發票號碼 | `move.name` | INV 單頭是否有獨立的台灣字軌發票號碼欄位（格式：AA12345678）？ |
| 2 | M | 發票日期時間 | `move.invoice_date` + ` 00:00:00` | 時間部分（hh:mm:ss）從哪裡取？`invoice_date` 只有日期無時間。 |
| 3 | M | 課稅別 | 固定 `1`（應稅） | Odoo 稅率如何區分應稅/零稅率/免稅？用 `tax_group_id` 還是 `amount` 判斷？ |
| 4 | M | 稅率 | `invoice_line_ids.tax_ids[0].amount` | 單張發票有多種稅率行時，M 行的稅率如何取？取主要稅率？ |
| 5 | D | 單位 | `line.product_uom_id.name` | 確認欄位。 |







