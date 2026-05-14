from odoo import api, models, fields, _
from collections import defaultdict
from odoo.exceptions import ValidationError, UserError
import logging

_logger = logging.getLogger(__name__)


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"
    sequence = fields.Integer(string="Sequence", default=1)
    wf_sequence = fields.Char(string="WF訂單序號")
    wf_slip = fields.Char(string="WF報價單單別")
    wf_number = fields.Char(string="WF報價單單號")
    wf_serial = fields.Char(string="WF報價單序號")
    partner_id = fields.Many2one(
        "res.partner",
        string="客戶",
        related="order_id.partner_id",
        store=True,
        readonly=True,
    )
    default_code = fields.Char(
        string="品號",
        related="product_template_id.default_code",
        store=True,
    )
    business_category_id = fields.Many2one(
        "idx.business.category",
        string="業務類別",
        related="product_template_id.business_category_id",
        store=True,
        readonly=True,
    )
    product_category_id = fields.Many2one(
        "idx.product.category",
        string="商品類別",
        related="product_template_id.product_category_id",
        store=True,
        readonly=True,
    )
    product_category_name = fields.Char(
        string="商品類別名稱",
        related="product_category_id.name",
        store=True,
        readonly=True,
    )
    category = fields.Selection(
        related="product_template_id.category",
        string="檢測單類別",
    )
    effective_date = fields.Date(
        string="生效日期", related="product_template_id.effective_date"
    )
    expiry_date = fields.Date(
        string="失效日期", related="product_template_id.expiry_date"
    )
    lot_id = fields.Many2one(
        "stock.lot",
        string="批次/序號",
    )
    lot_id_domain = fields.Char(
        compute='_compute_lot_id_domain',
        readonly=True,
        store=False,
    )

    @api.depends('product_id')
    def _compute_lot_id_domain(self):
        for line in self:
            if line.product_id:
                line.lot_id_domain = (
                    f"[('product_id', '=', {line.product_id.id}), "
                    f"('expiration_date', '>=', context_today().strftime('%Y-%m-%d'))]"
                )
            else:
                line.lot_id_domain = "[('product_id', '=', False)]"

    expiration_date = fields.Datetime(
        string="有效日期",
        related="lot_id.expiration_date",
        store=True,
        readonly=True,
    )
    quantity = fields.Float(
        string="在庫數量",
        compute="_compute_quantity",
        store=False,
    )
    giveaway_qty = fields.Float(string="贈品數")
    note = fields.Char(string="備註", readonly=True)
    report_ids = fields.One2many(
        "sale.order.report", "order_line_id", string="送檢單/報告"
    )
    stock_amount = fields.Monetary(string="庫存金額", compute='_compute_stock_amount', store=True, currency_field='currency_id')

    _sql_constraints = [
        (
            "unique_order_wf_sequence",
            "unique(order_id, wf_sequence)",
            "同一訂單的序號不可重複！",
        ),
    ]

    # -------------------------------------------------------------------------
    # CRUD
    # -------------------------------------------------------------------------

    @api.model_create_multi
    def create(self, vals_list):
        # 按訂單分組，並補全 product_id
        order_groups: dict = defaultdict(list)
        for vals in vals_list:
            self._resolve_product_from_template(vals)
            order_groups[vals.get("order_id")].append(vals)

        for order_id, group in order_groups.items():
            if order_id:
                self._assign_line_sequences(order_id, group)

        records = super().create(vals_list)
        records.filtered(
            lambda l: not l.wf_slip and not l.wf_number and not l.wf_serial
        )._fill_wf_fields_from_pricelist()
        return records

    def write(self, vals):
        self._resolve_product_from_template(vals)
        # wf_sequence 只在 create() 時寫入，之後永遠不異動
        vals.pop('wf_sequence', None)
        res = super().write(vals)
        if 'price_unit' in vals and not any(k in vals for k in ('wf_slip', 'wf_number', 'wf_serial')):
            self._fill_wf_fields_from_pricelist()
        # 判斷是否需要同步庫存資料
        sync_fields = {'lot_id', 'product_id', 'product_uom_qty', 'product_uom'}
        if any(field in vals for field in sync_fields):
            for line in self:
                line._sync_to_stock_moves()
        return res

    def _sync_to_stock_moves(self):
        """同步銷售明細變更，並處理多行庫存明細合併為單一行的邏輯"""
        self.ensure_one()

        # 1. 尋找關聯且未完成的 Stock Moves
        moves = self.env['stock.move'].search([
            ('sale_line_id', '=', self.id),
            ('state', 'not in', ['done', 'cancel'])
        ])

        if not moves:
            return

        for move in moves:
            # A. 同步商品 (若有變動)
            if move.product_id != self.product_id:
                move.write({
                    'product_id': self.product_id.id,
                    'product_uom': self.product_uom.id,
                })

            # B. 同步 Move 需求數量 (Demand)
            if move.product_uom_qty != self.product_uom_qty:
                move.write({'product_uom_qty': self.product_uom_qty})

            # C. 處理 Move Lines (實際分配/批號行)
            if move.move_line_ids:
                # 取得第一筆作為保留行
                keep_line = move.move_line_ids[0]
                # 取得其餘多餘的行
                unlink_lines = move.move_line_ids[1:]

                # 將第一筆更新為正確的批號與數量
                keep_line.write({
                    'lot_id': self.lot_id.id if self.lot_id else False,
                    'quantity': self.product_uom_qty
                })

                # 刪除多餘的拆分行，避免數量疊加
                if unlink_lines:
                    unlink_lines.unlink()
            else:
                # 如果目前沒有明細行且有指定批號，則手動建立一筆
                if self.lot_id:
                    self.env['stock.move.line'].create({
                        'move_id': move.id,
                        'picking_id': move.picking_id.id,
                        'product_id': move.product_id.id,
                        'lot_id': self.lot_id.id,
                        'quantity': self.product_uom_qty,
                        'location_id': move.location_id.id,
                        'location_dest_id': move.location_dest_id.id,
                    })

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------

    def _resolve_product_from_template(self, vals: dict) -> None:
        """若 vals 只帶 product_template_id 而未帶 product_id，
        自動填入該模板的第一個變體，供 create / write 共用。"""
        if 'product_id' not in vals and vals.get('product_template_id'):
            template = self.env['product.template'].sudo().browse(vals['product_template_id'])
            if template.product_variant_id:
                vals['product_id'] = template.product_variant_id.id

    def _assign_line_sequences(self, order_id: int, group: list) -> None:
        """為同一訂單的新增行批次分配 sequence / wf_sequence。

        規則：
        - 有明確帶入 wf_sequence（WF 同步場景）→ 以 wf_sequence 為主，
          若對應 sequence 衝突則自動遞增。
        - 未帶 wf_sequence（一般/前台新增）→ sequence 和 wf_sequence
          均取各自現有最大值 + 1，確保連續不跳號。
        """
        existing = self.env["sale.order.line"].search_read(
            [("order_id", "=", order_id)],
            fields=["sequence", "wf_sequence"],
        )
        existing_seqs = {r["sequence"] for r in existing}
        existing_wf_seqs = {
            int(r["wf_sequence"])
            for r in existing
            if r["wf_sequence"] and r["wf_sequence"].isdigit()
        }
        max_seq = max(existing_seqs, default=0)
        max_wf_seq = max(existing_wf_seqs, default=0)

        for vals in group:
            wf_seq_str = vals.get("wf_sequence")
            if wf_seq_str:
                # WF 同步：使用指定的 wf_sequence；sequence 若衝突則遞增
                candidate = int(wf_seq_str)
                if candidate in existing_seqs:
                    max_seq += 1
                    vals["sequence"] = max_seq
                    existing_seqs.add(max_seq)
                else:
                    vals["sequence"] = candidate
                    existing_seqs.add(candidate)
                existing_wf_seqs.add(candidate)
            else:
                # 一般新增：sequence 和 wf_sequence 各自取 max+1
                max_seq += 1
                max_wf_seq += 1
                vals["sequence"] = max_seq
                vals["wf_sequence"] = f"{max_wf_seq:04d}"
                existing_seqs.add(max_seq)
                existing_wf_seqs.add(max_wf_seq)
                    
    def _fill_wf_fields_from_pricelist(self):
        """依價格表規則回填 wf_slip / wf_number / wf_serial，不覆蓋 price_unit。"""
        for line in self:
            order = line.order_id
            if not order.pricelist_id or not line.product_id or not line.product_uom:
                continue
            price_dict = order.pricelist_id._compute_price_rule(
                line.product_id, line.product_uom_qty or 1.0,
                uom=line.product_uom, date=order.date_order,
            )
            _, rule_id = price_dict.get(line.product_id.id, (0.0, False))
            rule = rule_id and self.env['product.pricelist.item'].browse(rule_id)
            line.wf_slip = rule and rule.wf_slip or False
            line.wf_number = rule and rule.wf_number or False
            line.wf_serial = rule and rule.wf_serial or False

    @api.depends('product_uom_qty', 'price_unit')
    def _compute_stock_amount(self):
        for line in self:
            line.stock_amount = line.product_uom_qty * line.price_unit

    @api.depends("product_template_id")
    def _compute_lot_ids(self):
        for line in self:
            line.lot_ids = line.product_template_id.lot_ids

    @api.onchange("product_template_id", "price_unit", "product_uom_qty")
    def _onchange_product_id_is_fee_set_tax_zero(self):
        for line in self:
            product = line.product_template_id
            if not product:
                continue

            # 產品是否為費用
            if product.is_fee:
                line.tax_id = False
    
    @api.depends('order_id.wf_tax_type', 'product_id', 'company_id')
    def _compute_tax_id(self):
        for line in self:
            if line.order_id.odoo_tax_id:
                line.tax_id = line.order_id.odoo_tax_id
            else:
                line.tax_id = False
    
    @api.depends('product_id', 'product_uom', 'product_uom_qty', 'order_id.pricelist_id', 'tax_id')
    def _compute_price_unit(self):
        for line in self:
            if not line.product_uom or not line.product_id:
                line.price_unit = 0.0
                continue

            line = line.with_company(line.company_id)
            order = line.order_id
            price_dict = order.pricelist_id._compute_price_rule(
                line.product_id, line.product_uom_qty or 1.0,
                uom=line.product_uom, date=order.date_order,
            )
            raw_price, rule_id = price_dict.get(line.product_id.id, (0.0, False))

            # 寫入命中的價格表明細 wf 欄位
            rule = rule_id and self.env['product.pricelist.item'].browse(rule_id)
            line.wf_slip = rule and rule.wf_slip or False
            line.wf_number = rule and rule.wf_number or False
            line.wf_serial = rule and rule.wf_serial or False

            # 含稅單價處理
            include_tax_percent = (
                sum(t.amount for t in line.tax_id.flatten_taxes_hierarchy() if t.price_include)
                if line.tax_id else 0.0
            )
            line.price_unit = round(
                raw_price * (1 + include_tax_percent / 100) if include_tax_percent else raw_price, 0
            )


    @api.depends("order_partner_id", "order_id", "product_id")
    def _compute_display_name(self):
        use_wf = self.env.context.get("use_wf_sequence", False)
        name_per_id = self._additional_name_per_id()
        for so_line in self.sudo():
            if use_wf:
                so_line.display_name = so_line.wf_sequence or "未編號"
            else:
                name = "{} - {}".format(
                    so_line.order_id.name,
                    so_line.name
                    and so_line.name.split("\n")[0]
                    or so_line.product_id.name,
                )
                additional_name = name_per_id.get(so_line.id)
                if additional_name:
                    name = f"{name} {additional_name}"
                so_line.display_name = name

    @api.depends("lot_id")
    def _compute_quantity(self):
        Quant = self.env["stock.quant"]
        for rec in self:
            if not rec.lot_id:
                rec.quantity = None # 沒有批次時不顯示數量
                continue

            domain = [
                ('product_id', '=', rec.product_id.id),
                ('lot_id', '=', rec.lot_id.id),
                ('company_id', '=', rec.order_id.company_id.id),
                ('location_id.usage', '=', 'internal'),
            ]

            quants = Quant.search(domain)

            rec.quantity = sum(quants.mapped("quantity"))

    def _get_coupon_display(self):
        self.ensure_one()

        cards = self.env["loyalty.card"]

        if hasattr(self, "coupon_point_id") and self.coupon_point_id:
            cp = self.coupon_point_id
            if hasattr(cp, "coupon_id") and cp.coupon_id:
                cards |= cp.coupon_id

        if hasattr(self, "coupon_id") and self.coupon_id:
            cards |= self.coupon_id

        if not cards:
            return ""

        parts = []
        for c in cards:
            serial = (getattr(c, "serial_number", "") or "").strip()
            if serial:
                parts.append(f"{serial}")

        parts = list(dict.fromkeys([p for p in parts if p]))
        return "/".join(parts)

    def _build_auto_note(self):
        self.ensure_one()

        reports = self.report_ids.sorted(lambda r: (r.name or "", r.inspect_number or ""))
        if not reports:
            return ""

        coupon = self._get_coupon_display()

        parts = []
        for r in reports:
            name = (r.name or "").strip()
            unit = (r.inspection_unit or "").strip()
            extra = f"({coupon})" if coupon else ""

            item = ""
            if name:
                item += name
            if extra:
                item += extra
            if unit:
                item += f"-{unit}"

            if item:
                parts.append(item)

        return "/".join(parts)


    def _apply_auto_note(self):
        for line in self:
            line.note = line._build_auto_note() or ""
