from datetime import timedelta
import logging
import pyodbc

from odoo import api, fields, models, _, tools
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class ProductTemplate(models.Model):
    _inherit = "product.template"

    @tools.ormcache()
    def _get_default_uom_id(self):
        return self.env.ref("uom.product_uom_unit")

    def _get_default_uom_so_id(self):
        return self.default_get(["uom_id"]).get("uom_id") or self._get_default_uom_id()

    catalog_number = fields.Char(string="貨號")
    specification = fields.Char(string="規格")
    category = fields.Selection(
        [("0", "人類醫學"), ("1", "小動物"), ("2", "E66")], string="檢測單類別"
    )
    wf_sync_time = fields.Integer(string="WF同步次數", default=0)
    wf_sync_datetime = fields.Datetime(string="WF同步時間")
    wf_sync_user_id = fields.Many2one("res.users", string="WF同步人員")
    uom_so_id = fields.Many2one(
        "uom.uom", string="銷售單位", default=_get_default_uom_so_id, required=True
    )
    avg_recommended_qty = fields.Char(string="平均建議申請量", default="不限制")
    product_desc = fields.Text(string="產品說明")
    effective_date = fields.Date(string="生效日期")
    expiry_date = fields.Date(string="失效日期")
    sale_price = fields.Float(string="定價", digits="Product Price")
    # lot_ids = fields.One2many(
    #     comodel_name="stock.lot",
    #     inverse_name="product_tmpl_id",
    #     string="批次/序號",
    # )
    lot_line_ids = fields.One2many(
        comodel_name="product.template.lot.line",
        inverse_name="product_tmpl_id",
        string="批次/序號",
    )
    wf_warehouse_id = fields.Char(string="WF主要庫別")
    wf_stock_management = fields.Selection(
        [("Y", "Y"), ("N", "N")], string="WF庫存管理"
    )
    wf_lot_management = fields.Selection(
        [
            ("N", "不需要"),
            ("Y", "需要不檢查庫存"),
            ("W", "僅需警告"),
            ("T", "需要且檢查庫存"),
        ],
        string="WF批號管理",
    )
    wf_inspection_type = fields.Selection(
        [
            ("0", "免驗"),
            ("1", "抽檢（減量）"),
            ("2", "抽檢（正常）"),
            ("3", "抽檢（加嚴）"),
            ("4", "全檢"),
        ],
        string="WF檢驗方式",
    )
    wf_valid_days = fields.Integer(string="WF有效天數")
    wf_reinspection_days = fields.Integer(string="WF複檢天數")
    business_category_id = fields.Many2one("idx.business.category", string="業務類別")
    product_category_id = fields.Many2one("idx.product.category", string="商品類別")
    new_product_approval_date = fields.Date(string="新品核准日期")
    detailed_type = fields.Selection(default="product")
    is_fee = fields.Boolean(string="是否為費用", default=False)
    list_price = fields.Float(default=0)

    @api.constrains("effective_date", "expiry_date")
    def _check_effective_and_expiry_date(self):
        for rec in self:
            if rec.effective_date and rec.expiry_date:
                if rec.effective_date > rec.expiry_date:
                    raise ValidationError(_("「生效日期」不能大於「失效日期」。"))

    def action_sync_wf(self):
        view = self.env.ref("idx_ebs.idx_wf_sync_wizard_form2")

        return {
            "type": "ir.actions.act_window",
            "name": "WF同步至B2B",
            "res_model": "idx.wf.sync.wizard",
            "views": [(view.id, "form")],
            "target": "new",
            "context": {
                "active_ids": self.ids,
                "active_model": self._name,
                "default_default_code": self.default_code,
            },
        }

    def _get_sales_prices(self, pricelist, fiscal_position):
        res = super()._get_sales_prices(pricelist, fiscal_position)
        today = fields.Date.context_today(self)
        for template in self:
            pricelist_item = self.env["product.pricelist.item"].search(
                [
                    ("pricelist_id", "=", pricelist.id),
                    ("product_tmpl_id", "=", template.id),
                    ("compute_price", "=", "fixed"),
                    "|",
                    ("date_start", "=", False),
                    ("date_start", "<=", today),
                    "|",
                    ("date_end", "=", False),
                    ("date_end", ">=", today),
                ],
                order="date_start desc",
                limit=1,
            )
            res[template.id]["inc_tax_price"] = (
                pricelist_item.inc_tax_price
                if pricelist_item
                else res[template.id].get("price_reduce", 0.0)
            )
        return res

    def _get_combination_info(
        self,
        combination=False,
        product_id=False,
        add_qty=1.0,
        parent_combination=False,
        only_template=False,
    ):
        combination_info = super()._get_combination_info(
            combination=combination,
            product_id=product_id,
            add_qty=add_qty,
            parent_combination=parent_combination,
            only_template=only_template,
        )

        prevent_zero_price_sale = combination_info.get("prevent_zero_price_sale", False)
        list_price = combination_info.get("list_price", 0.0)

        # 從當前價格表的 item 直接取含稅單價（inc_tax_price）
        # 過濾有效期間內的 item，取 date_start 最新的一筆（與 website.sale_product_domain 邏輯一致）
        website = self.env["website"].get_current_website()
        pricelist = website._get_current_pricelist()
        today = fields.Date.context_today(self)
        pricelist_item = self.env["product.pricelist.item"].search(
            [
                ("pricelist_id", "=", pricelist.id),
                ("product_tmpl_id", "=", self.id),
                ("compute_price", "=", "fixed"),
                "|",
                ("date_start", "=", False),
                ("date_start", "<=", today),
                "|",
                ("date_end", "=", False),
                ("date_end", ">=", today),
            ],
            order="date_start desc",
            limit=1,
        )
        inc_tax_price = (
            pricelist_item.inc_tax_price
            if pricelist_item
            else combination_info.get("price", 0.0)
        )

        combination_info.update(
            {
                "price": inc_tax_price,
                "list_price": 0 if prevent_zero_price_sale else list_price,
                "sale_price": self.sale_price or 0.0,
                "avg_recommended_qty": self.avg_recommended_qty or "0",
                "product_category_name": (
                    self.product_category_id.name if self.product_category_id else ""
                ),
                "inc_tax_price": inc_tax_price,
            }
        )
        return combination_info

    def write(self, vals):
        if "active" in vals and self.active and not vals.get("active"):
            if not self.user_has_groups(
                "idx_ebs.group_back_document_management"
            ) or self.user_has_groups("idx_ebs.group_back_it"):
                raise ValidationError(_("您沒有權限封存產品"))
        res = super(ProductTemplate, self).write(vals)
        return res

    def unlink(self):
        for template in self:
            has_lots = self.env["stock.lot"].search(
                [("product_id", "in", template.product_variant_ids.ids)], limit=1
            )
            if has_lots:
                raise ValidationError(
                    _("產品「%s」存在批次/序號記錄，無法刪除！") % template.name
                )
        return super().unlink()


class ProductTemplateLotLine(models.Model):
    _name = "product.template.lot.line"
    _description = "產品批次關聯行"

    product_id = fields.Many2one(
        "product.product",
        string="產品變體",
        compute="_compute_product_id",
        store=True,
        readonly=False,
        required=True,
        ondelete="restrict",
    )
    product_tmpl_id = fields.Many2one(
        "product.template",
        string="產品主檔",
        required=True,
        ondelete="cascade",  # 產品刪除 → 關聯行跟著刪
    )
    lot_id = fields.Many2one(
        "stock.lot",
        string="批次/序號",
        required=True,
        ondelete="restrict",  # ✅ 刪除這行「不會」刪掉 stock.lot
        domain="[('product_tmpl_id', '=', product_tmpl_id)]",
        context="{'default_product_tmpl_id': product_tmpl_id}",
    )

    # 以下全部 related，只讀顯示用
    expiration_date = fields.Datetime(
        related="lot_id.expiration_date", string="有效日期", readonly=True
    )
    alert_date = fields.Datetime(
        related="lot_id.alert_date", string="警示日期", readonly=True
    )
    is_alert = fields.Boolean(related="lot_id.is_alert", readonly=True)
    valid_days_remaining = fields.Integer(
        related="lot_id.valid_days_remaining", string="剩餘有效天數", readonly=True
    )
    is_valid_days_remaining = fields.Boolean(
        related="lot_id.is_valid_days_remaining", readonly=True
    )
    product_qty = fields.Float(
        related="lot_id.product_qty", string="在庫數量", readonly=True
    )

    @api.depends("product_tmpl_id")
    def _compute_product_id(self):
        for line in self:
            if line.product_tmpl_id and line.product_tmpl_id.product_variant_id:
                line.product_id = line.product_tmpl_id.product_variant_id
            else:
                line.product_id = False


class ProductPricelist(models.Model):
    _inherit = "product.pricelist"
    _sql_constraints = [
        ("partner_id_unique", "unique(partner_id)", "每個客戶只能有一個價格表！"),
    ]

    partner_full_name = fields.Char(
        string="客戶全名",
        related="partner_id.full_name",
        store=True,
        tracking=True,
        copy=False,
    )
    partner_code = fields.Char(
        string="客戶代號",
        related="partner_id.partner_code",
        store=True,
        tracking=True,
        copy=False,
    )
    partner_id = fields.Many2one(
        "res.partner",
        string="客戶簡稱",
        tracking=True,
        copy=False,
        domain="[('parent_id', '=', False)]",
    )
    wf_tax_id = fields.Many2one(
        string="WF稅別碼",
        related="partner_id.wf_tax_id",
        store=True,
        tracking=True,
        copy=False,
    )
    wf_tax_type = fields.Selection(
        string="WF課稅別",
        related="partner_id.wf_tax_type",
        store=True,
        tracking=True,
        copy=False,
    )
    consumables = fields.Many2many(
        'product.template',
        string="適用產品",
        domain=[('product_category_id.name', '=', '耗材')],
    )

    @api.onchange("partner_id")
    def _onchange_partner_id(self):
        # 透過commands清空單身
        self.item_ids = [(5, 0, 0)]
        if self.partner_id:
            # 依據該客戶代號，寫入價格表
            self.env["res.partner"].browse(self.partner_id.id).write(
                {"property_product_pricelist": self.id}
            )

    def action_sync_wf(self):
        view = self.env.ref("idx_ebs.pricelist_wf_sync_wizard_form")

        return {
            "type": "ir.actions.act_window",
            "name": "WF同步至B2B",
            "res_model": "pricelist.wf.sync.wizard",
            "views": [(view.id, "form")],
            "target": "new",
        }

    def sync_with_wf(
        self,
        quote_date_start=None,
        quote_date_end=None,
        create_date_start=None,
        create_date_end=None,
        modi_date_start=None,
        modi_date_end=None,
    ):
        _logger.info(
            f"開始同步價格表 {self.id} 至WF，篩選條件 - 報價日期: {quote_date_start} ~ {quote_date_end}, 建立日期: {create_date_start} ~ {create_date_end}, 修改日期: {modi_date_start} ~ {modi_date_end}"
        )

        company = self.env.company
        wf_db = company.wf_db
        if not wf_db:
            raise ValidationError("尚未設定WF資料庫，請洽詢管理員。")

        try:
            priceList = (
                self.env["product.pricelist"].browse(self.env.context.get("active_id"))
                if self.env.context.get("active_id")
                else None
            )
            quote_condition = self._get_quote_condition(
                quote_date_start, quote_date_end
            )
            create_condition = self._get_create_condition(
                create_date_start, create_date_end
            )
            modi_condition = self._get_modi_condition(modi_date_start, modi_date_end)

            operate_conditions = " OR ".join(
                filter(
                    None,
                    [
                        f"({create_condition})" if create_condition else "",
                        f"({modi_condition})" if modi_condition else "",
                    ],
                )
            )
            final_conditions = " AND ".join(
                filter(
                    None,
                    [
                        (
                            f"COPTA.TA004 = '{priceList.partner_code}'"
                            if priceList and priceList.partner_code
                            else ""
                        ),
                        quote_condition,
                        f"({operate_conditions})" if operate_conditions else "",
                    ],
                )
            )
            condition = final_conditions if final_conditions else "1=1"

            #### 排序方式不做變動，確保同一客戶的資料是連續的，以利後續在程式中暫存價格表記錄進行比對和更新
            sql = (
                "SELECT TA004, TA001, TA002, TB003, TA013, TA003, TB004, TB009, TB016, TB017 FROM COPTA "
                "LEFT JOIN COPTB ON COPTA.TA001 = COPTB.TB001 AND COPTA.TA002 = COPTB.TB002 "
                f"WHERE {condition} "
                "ORDER BY COPTA.TA004, COPTA.TA013, COPTB.TB003"
            )

            connection_params = self.env["wf.mapping"]._get_connection_parameters(wf_db)

            with (
                pyodbc.connect(
                    connection_params["connection_string"], timeout=3
                ) as connection,
                connection.cursor() as cursor,
            ):
                cursor.execute(sql)
                results = cursor.fetchall()
                self._create_or_update_pricelist_item(results)
                # 確保每個有 partner_id 的價格表，partner 的 property_product_pricelist 都指向正確的價格表
                self._sync_partner_pricelist_property()
                _logger.info(
                    f"完成同步價格表 {self.id} 至WF，共同步 {len(results)} 筆資料。"
                )
                self._notify_user_sync(
                    status=True, message="WF報價單->odoo價格表同步完成"
                )
                return {
                    "type": "ir.actions.client",
                    "tag": "display_notification",
                    "params": {
                        "title": "WF報價單->odoo價格表同步完成",
                        "message": f"共同步 {len(results)} 筆資料，請至價格表中查看。",
                        "type": "success",
                    },
                    "next": {
                        "type": "ir.actions.client",
                        "tag": "soft_reload",
                    },
                }
        except Exception as e:
            _logger.error(f"同步WF報價單至價格表失敗: {e}")
            self._notify_user_sync(status=False, message="WF報價單->odoo價格表同步失敗")
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": "WF報價單->odoo價格表同步失敗",
                    "message": f"請洽詢管理員，錯誤訊息: {e}",
                    "type": "warning",
                },
                "next": {
                    "type": "ir.actions.client",
                    "tag": "soft_reload",
                },
            }

    def _get_quote_condition(self, quote_date_start, quote_date_end):
        """
        根據報價日期篩選條件生成SQL WHERE子句的一部分
        @param quote_date_start: 報價日期起始值
        @param quote_date_end: 報價日期結束值
        @return: SQL條件字串
        """
        quote_date_start = (
            quote_date_start.strftime("%Y%m%d") if quote_date_start else None
        )
        quote_date_end = quote_date_end.strftime("%Y%m%d") if quote_date_end else None
        if quote_date_start and quote_date_end:
            if quote_date_start == quote_date_end:
                return f"COPTA.TA003 = N'{quote_date_start}'"
            else:
                return f"COPTA.TA003 >= N'{quote_date_start}' AND COPTA.TA003 <= N'{quote_date_end}'"
        elif quote_date_start:
            return f"COPTA.TA003 >= N'{quote_date_start}'"
        elif quote_date_end:
            return f"COPTA.TA003 <= N'{quote_date_end}'"

        return ""

    def _get_create_condition(self, create_date_start, create_date_end):
        """
        根據建立日期篩選條件生成SQL WHERE子句的一部分
        @param create_date_start: 建立日期起始值
        @param create_date_end: 建立日期結束值
        @return: SQL條件字串
        """
        create_date_start = (
            create_date_start.strftime("%Y%m%d") if create_date_start else None
        )
        create_date_end = (
            create_date_end.strftime("%Y%m%d") if create_date_end else None
        )
        if create_date_start and create_date_end:
            if create_date_start == create_date_end:
                return f"COPTA.CREATE_DATE = N'{create_date_start}'"
            else:
                return f"COPTA.CREATE_DATE >= N'{create_date_start}' AND COPTA.CREATE_DATE <= N'{create_date_end}'"
        elif create_date_start:
            return f"COPTA.CREATE_DATE >= N'{create_date_start}'"
        elif create_date_end:
            return f"COPTA.CREATE_DATE <= N'{create_date_end}'"

        return ""

    def _get_modi_condition(self, modi_date_start, modi_date_end):
        """
        根據修改日期篩選條件生成SQL WHERE子句的一部分
        @param modi_date_start: 修改日期起始值
        @param modi_date_end: 修改日期結束值
        @return: SQL條件字串
        """
        modi_date_start = (
            modi_date_start.strftime("%Y%m%d") if modi_date_start else None
        )
        modi_date_end = modi_date_end.strftime("%Y%m%d") if modi_date_end else None
        if modi_date_start and modi_date_end:
            if modi_date_start == modi_date_end:
                return f"COPTA.MODI_DATE = N'{modi_date_start}'"
            else:
                return f"COPTA.MODI_DATE >= N'{modi_date_start}' AND COPTA.MODI_DATE <= N'{modi_date_end}'"
        elif modi_date_start:
            return f"COPTA.MODI_DATE >= N'{modi_date_start}'"
        elif modi_date_end:
            return f"COPTA.MODI_DATE <= N'{modi_date_end}'"

        return ""

    def _create_or_update_pricelist_item(self, results):
        cur_partner_code, cur_price_list, product_cache = None, None, {}

        def fmt_date(val):
            """將 WF 日期字串 'YYYYMMDD' 轉換為 Odoo 可接受的 'YYYY-MM-DD'"""
            s = str(val).strip() if val else ""
            return f"{s[:4]}-{s[4:6]}-{s[6:8]}" if len(s) == 8 else None

        for row in results:
            # 暫存產品資料，避免重複查詢資料庫
            if row[6] not in product_cache:
                product = self.env["product.template"].search(
                    [("default_code", "=", row[6])], limit=1
                )
                product_cache[row[6]] = product.id if product else None

            if not product_cache[row[6]]:
                _logger.warning(
                    f"同步價格表時，找不到品號 {row[6]} 對應的產品，跳過該筆資料 - WF單別: {row[1]}, WF單號: {row[2]}, WF序號: {row[3]}"
                )
                continue

            # SQL結果依照客戶代號排序，透過two pointer演算法暫存價格表記錄，當客戶代號變動時才查詢資料庫，減少查詢次數
            if cur_partner_code != row[0]:
                cur_partner_code = row[0]
                cur_price_list = self.env["product.pricelist"].search(
                    [("partner_code", "=", cur_partner_code)], limit=1
                )

            # 該客戶的價格表尚未建立
            if not cur_price_list:
                # 確認客戶主檔是否存在該客戶代號，存在則建立價格表，不存在則跳過該筆資料
                partner = self.env["res.partner"].search(
                    [("partner_code", "=", cur_partner_code)], limit=1
                )
                if not partner:
                    _logger.warning(
                        f"同步價格表時，找不到客戶代號 {cur_partner_code} 對應的客戶，跳過該筆資料 - WF單別: {row[1]}, WF單號: {row[2]}, WF序號: {row[3]}"
                    )
                    continue

                cur_price_list = self.env["product.pricelist"].create(
                    {
                        "name": f"{partner.name} 的價格表",
                        "partner_id": partner.id,
                        "currency_id": self.env.company.currency_id.id,
                    }
                )
                # 新建價格表時，立即寫回 partner 的 property_product_pricelist
                partner.write({"property_product_pricelist": cur_price_list.id})

            # 確認價格表單身是否已存在，存在則更新，不存在則建立
            price_list_item = self.env["product.pricelist.item"].search(
                [
                    ("pricelist_id", "=", cur_price_list.id),
                    ("wf_slip", "=", row[1]),
                    ("wf_number", "=", row[2]),
                    ("wf_serial", "=", row[3]),
                ],
                limit=1,
            )

            vals = {
                "wf_doc_date": fmt_date(row[4]),
                "wf_quote_date": fmt_date(row[5]),
                "product_tmpl_id": product_cache[row[6]],
                "wf_price": row[7],
                "date_start": fmt_date(row[8]),
                "date_end": fmt_date(row[9]),
            }

            if price_list_item:
                price_list_item.write(vals)
            else:
                vals.update(
                    {
                        "pricelist_id": cur_price_list.id,
                        "wf_slip": row[1],
                        "wf_number": row[2],
                        "wf_serial": row[3],
                    }
                )
                self.env["product.pricelist.item"].create(vals)

    def _notify_user_sync(self, status=False, message="") -> None:
        """
        發送右上角的彈出通知
        @param status: 同步狀態
        """
        self.env["bus.bus"]._sendone(
            self.env.user.partner_id,
            "simple_notification",
            {
                "type": "warning" if not status else "success",
                "title": "同步狀態",
                "message": message,
            },
        )
        self.env.cr.commit()

    def _sync_partner_pricelist_property(self) -> None:
        """
        確保所有有 partner_id 的價格表，其 partner 的 property_product_pricelist 都指向該價格表。
        呼叫時機：sync_with_wf 同步成功後，修補因程式直接建立而未觸發 onchange 的漏網情況。
        """
        pricelists = self.search([("partner_id", "!=", False)])
        for pl in pricelists:
            current = pl.partner_id.property_product_pricelist
            if current.id != pl.id:
                pl.partner_id.write({"property_product_pricelist": pl.id})
                _logger.info(
                    f"修補 partner {pl.partner_id.name}({pl.partner_id.id}) 的 property_product_pricelist: "
                    f"{current.id}({current.name}) → {pl.id}({pl.name})"
                )


class ProductPricelistItem(models.Model):
    _inherit = "product.pricelist.item"
    _order = "wf_slip desc, wf_number desc, wf_serial desc"

    partner_id = fields.Many2one(
        "res.partner",
        string="客戶簡稱",
        related="pricelist_id.partner_id",
        store=True,
    )
    partner_code = fields.Char(
        string="客戶代號",
        related="pricelist_id.partner_code",
        store=True,
        index=True,
    )
    wf_slip = fields.Char(
        string="WF報價單單別", readonly=True, help="COPTA的TA001欄位", index=True
    )
    wf_number = fields.Char(
        string="WF報價單單號", readonly=True, help="COPTA的TA002欄位", index=True
    )
    wf_serial = fields.Char(
        string="WF報價單序號", readonly=True, help="COPTB的TB003欄位", index=True
    )
    wf_doc_date = fields.Char(
        string="WF單據日期", readonly=True, help="COPTA的TA013欄位"
    )
    wf_quote_date = fields.Char(
        string="WF報價日期", readonly=True, help="COPTA的TA003欄位"
    )
    default_code = fields.Char(
        string="品號",
        related="product_tmpl_id.default_code",
        store=True,
        readonly=True,
        help="COPTB的TB004欄位",
    )
    date_start = fields.Date(string="生效日", readonly=True, help="COPTB的TB016欄位")
    date_end = fields.Date(string="失效日", readonly=True, help="COPTB的TB017欄位")
    wf_price = fields.Float(string="單價", default=0.0, help="COPTB的TB009欄位")
    fixed_price = fields.Float(
        string="未稅單價", compute="_compute_tax_prices", store=True
    )
    inc_tax_price = fields.Float(
        string="含稅單價", compute="_compute_tax_prices", store=True
    )

    @api.depends(
        "wf_price",
        "pricelist_id.wf_tax_type",
        "pricelist_id.wf_tax_id",
        "pricelist_id.wf_tax_id.rate",
    )
    def _compute_tax_prices(self):
        for item in self:
            if not item.pricelist_id.wf_tax_type:
                item.fixed_price = item.wf_price
                item.inc_tax_price = item.wf_price
                continue

            if item.pricelist_id.wf_tax_type == "1":  # 1:應稅內含
                item.fixed_price = round(
                    (
                        item.wf_price / (1 + item.pricelist_id.wf_tax_id.rate)
                        if item.pricelist_id.wf_tax_id.rate
                        else item.wf_price
                    ),
                    0,
                )
                item.inc_tax_price = item.wf_price
            elif item.pricelist_id.wf_tax_type == "2":  # 2:應稅外加
                item.fixed_price = item.wf_price
                item.inc_tax_price = round(
                    (
                        item.wf_price * (1 + item.pricelist_id.wf_tax_id.rate)
                        if item.pricelist_id.wf_tax_id.rate
                        else item.wf_price
                    ),
                    0,
                )
            else:
                item.fixed_price = item.wf_price
                item.inc_tax_price = item.wf_price
