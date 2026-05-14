import logging
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
import pyodbc
from datetime import datetime

_logger = logging.getLogger(__name__)


class IDXWFSyncWizard(models.TransientModel):
    _name = "idx.wf.sync.wizard"
    _description = "WF同步B2B Wizard"

    approve_date_start = fields.Date(string="新品號核准日期_起始日期")
    approve_date_end = fields.Date(string="新品號核准日期_結束日期")
    create_date_start = fields.Date(string="建立日期_起始日期")
    create_date_end = fields.Date(string="建立日期_結束日期")
    write_date_start = fields.Date(string="修改日期_起始日期")
    write_date_end = fields.Date(string="修改日期_結束日期")
    default_code = fields.Char(string="品號")

    @api.constrains("approve_date_start", "approve_date_end", "create_date_start", "create_date_end", "write_date_start", "write_date_end")
    def _check_date_ranges(self):
        for rec in self:
            rec._check_single_date_range(rec.approve_date_start, rec.approve_date_end, _("新品號核准日期"))
            rec._check_single_date_range(rec.create_date_start, rec.create_date_end, _("建立日期"))
            rec._check_single_date_range(rec.write_date_start, rec.write_date_end, _("修改日期"))

    def _check_single_date_range(self, start, end, label):
        if start and end and end < start:
            raise ValidationError(_(f"{label}的結束日期不可早於起始日期"))

    def action_confirm(self):
        # 設定-同步WF開關
        # user_has_sync_perm = self.env.user.has_group("")  # 尚未定義
        #
        # if not user_has_sync_perm:
        #     raise ValidationError("您沒有啟用同步WF開關，無法執行動作！")
        #
        # if not self.env.user.has_group(""):  # 尚未定義
        #     raise ValidationError(_("您沒有執行產品同步的權限"))

        if self.default_code:
            wf_main_domain = f"MB001 = '{self.default_code}' "
        else:
            #組wizard條件
            conditions = []

            # 新品號核准日期（MB158）
            if self.approve_date_start and self.approve_date_end:
                conditions.append(f"(MB158 BETWEEN '{self.approve_date_start}' AND '{self.approve_date_end}')")
            elif self.approve_date_start:
                conditions.append(f"(MB158 >= '{self.approve_date_start}')")
            elif self.approve_date_end:
                conditions.append(f"(MB158 <= '{self.approve_date_end}')")

            # 建立日期（CREATE_DATE）
            if self.create_date_start and self.create_date_end:
                conditions.append(f"(CREATE_DATE BETWEEN '{self.create_date_start}' AND '{self.create_date_end}')")
            elif self.create_date_start:
                conditions.append(f"(CREATE_DATE >= '{self.create_date_start}')")
            elif self.create_date_end:
                conditions.append(f"(CREATE_DATE <= '{self.create_date_end}')")

            # 修改日期（MODI_DATE）
            if self.write_date_start and self.write_date_end:
                conditions.append(f"(MODI_DATE BETWEEN '{self.write_date_start}' AND '{self.write_date_end}')")
            elif self.write_date_start:
                conditions.append(f"(MODI_DATE >= '{self.write_date_start}')")
            elif self.write_date_end:
                conditions.append(f"(MODI_DATE <= '{self.write_date_end}')")

            # 組成 WHERE 條件
            if conditions:
                wf_main_domain = " OR ".join(conditions)
                wf_main_domain = f"({wf_main_domain})"
            else:
                wf_main_domain = "1=1"

        wf_domain = "1=1"
        wf_line_domain = None
        wf_db = self.env.company.wf_db
        result, err_msg = (
            self.env["wf.mapping"]
            .sudo()
            ._wf_to_odoo_sync(
                wf_model="INVMB",
                wf_db=wf_db,
                wf_domain=wf_domain,
                wf_main_domain=wf_main_domain,
                wf_line_domain=wf_line_domain,
            )
        )

        if result:
            result = self._sync_product_detailed_type(company_id=self.env.company, wf_domain=wf_main_domain)

        # if result:
        #     result = self._sync_product_qty(company_id=self.env.company, wf_domain=wf_main_domain)

        if result:
            message = _("同步完成")
        else:
            message = err_msg if err_msg else _("同步失敗，請檢查相關設定或資料。")
        message_type = "success" if result else "danger"

        # 顯示成功通知並關閉彈窗
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "message": message,
                "type": message_type,
                "sticky": False,
                "next": {"type": "ir.actions.client", "tag": "soft_reload"},
            },
        }

    def _sync_product_detailed_type(self, company_id=None, wf_domain=None):
        """
        連上WF資料庫，根據 wf_domain 取得商品資訊並更新 Odoo 商品資料。
        """
        sql = (
            "SELECT MB001 AS default_code "
            "FROM INVMB "
            f"WHERE {wf_domain} "
        )
        connection_params = self.env['wf.mapping']._get_connection_parameters(company_id.wf_db)
        try:
            _logger.info(f"開始取得WF商品資料，wf_db: {company_id.wf_db}")
            with pyodbc.connect(connection_params['connection_string'], timeout=3) as conn, conn.cursor() as cursor:
                cursor.execute(sql)
                rows = cursor.fetchall()
        except Exception as e:
            _logger.error(f"更新WF商品類型失敗: {e}")
            return False

        for row in rows:
            default_code = (row[0] or '').strip()
            product_id = self.env['product.template'].sudo().search([('default_code', '=', default_code)])
            if default_code.startswith('46'):
                product_id.write({'detailed_type': 'service'})
            else:
                if product_id.wf_stock_management == 'N':
                    product_id.write({'detailed_type': 'consu'})
                else:
                    product_id.write({'detailed_type': 'product'})

        _logger.info(f"更新WF商品類型，wf_db: {company_id.wf_db}")
        return True

    def _sync_product_qty(self, company_id=None, wf_domain=None):
        """
        連上WF資料庫，根據 wf_domain 取得庫存資訊並更新 Odoo 庫存資料。
        """
        sql = (
            "SELECT mb.MB001 AS default_code, "
            "       '' AS lot_name, "
            "       SUM(mc.MC007) AS quantity, "
            "       '' AS expiry_date "
            "FROM INVMB AS mb "
            "INNER JOIN INVMC AS mc ON mb.MB001 = mc.MC001 "
            "WHERE mb.MB019 = 'Y' "
            "  AND mb.MB022 = 'N' "
            f" AND {wf_domain} "
            "GROUP BY mb.MB001 "
            "UNION ALL "
            "SELECT mb.MB001, "
            "       me.ME002, "
            "       SUM(mf.MF010 * mf.MF008) "
            "      , me.ME009 "
            "FROM INVMB AS mb "
            "INNER JOIN INVME AS me ON mb.MB001 = me.ME001 "
            "LEFT JOIN INVMF AS mf ON me.ME001 = mf.MF001 AND me.ME002 = mf.MF002 "
            "WHERE mb.MB019 = 'Y' "
            "  AND mb.MB022 <> 'N' "
            f" AND {wf_domain} "
            "GROUP BY mb.MB001, me.ME002, me.ME003,me.ME009"
        )

        location = self.env['stock.location'].sudo().search(
            [('usage', '=', 'internal'), ('replenish_location', '=', True)], limit=1)
        connection_params = self.env['wf.mapping']._get_connection_parameters(company_id.wf_db)
        try:
            _logger.info(f"開始取得WF庫存資料，wf_db: {company_id.wf_db}")
            with pyodbc.connect(connection_params['connection_string'], timeout=3) as conn, conn.cursor() as cursor:
                cursor.execute(sql)
                rows = cursor.fetchall()
        except Exception as e:
            _logger.error(f"WF庫存同步失敗: {e}")
            return False

        # 批量查詢產品
        default_codes = list({(row[0] or '').strip() for row in rows if row[0]})
        products = self.env['product.product'].sudo().search([('default_code', 'in', default_codes),('detailed_type', '=', 'product')])
        product_map = {p.default_code: p for p in products}

        # 批量查詢批號
        lot_keys = {(row[0].strip(), row[1].strip()) for row in rows if row[0] and row[1]}
        lots = self.env['stock.lot'].sudo().search([
            ('name', 'in', [k[1] for k in lot_keys]),
            ('product_id', 'in', [p.id for p in products])
        ])
        lot_map = {(l.product_id.default_code, l.name): l for l in lots}

        # 批量查詢庫存量
        quants = self.env['stock.quant'].sudo().search([
            ('product_id', 'in', [p.id for p in products]),
            ('location_id', '=', location.id)
        ])
        quant_map = {}
        for q in quants:
            key = (q.product_id.default_code, q.lot_id.name if q.lot_id else '')
            quant_map[key] = q

        # 批量處理 rows
        new_lots = []
        new_quants = []
        for row in rows:
            default_code = (row[0] or "").strip()
            lot_name = (row[1] or "").strip()
            quantity = float(row[2] or 0.0)
            expiration_date = row[3] or ""

            try:
                expiration_date = datetime.strptime(expiration_date, "%Y%m%d").date() if expiration_date else None
            except ValueError:
                expiration_date = None

            product = product_map.get(default_code)
            if not product:
                continue

            # 處理批號
            lot = lot_map.get((default_code, lot_name))
            if not lot and lot_name:
                lot = self.env['stock.lot'].sudo().create({
                    'name': lot_name,
                    'product_id': product.id,
                    'company_id': self.env.company.id,
                    'expiration_date': expiration_date,
                })
                lot_map[(default_code, lot_name)] = lot

            # 處理庫存量
            quant_key = (default_code, lot_name)
            quant = quant_map.get(quant_key)
            quant_vals = {
                'product_id': product.id,
                'location_id': location.id,
                'quantity': quantity,
                'expiration_date': expiration_date,
            }
            if lot:
                quant_vals['lot_id'] = lot.id

            if quant:
                quant.write({'quantity': quantity, 'expiration_date': expiration_date})
            else:
                new_quants.append(quant_vals)

        # 批量建立庫存量
        if new_quants:
            self.env['stock.quant'].sudo().create(new_quants)

        _logger.info(f"WF庫存同步成功，wf_db: {company_id.wf_db}")
        return True