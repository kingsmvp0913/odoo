from email.policy import default

from odoo import api, models, fields, _
from odoo.tools import float_is_zero
from odoo.exceptions import ValidationError, UserError
from collections import defaultdict
import pyodbc
import logging
from datetime import datetime

_logger = logging.getLogger(__name__)

CUSTOM_SALE_ORDER_STATE = [
    ("draft", "報價中"),
    ("sent", "報價已送出"),
    ("confirmed", "訂單待確認"),
    ("received", "已收件"),
    ("active", "訂單已成立"),
    ("wf_confirm", "WF已確認"),
    ("inspected", "已檢驗"),
    ("reported", "報告完成"),
    ("sent_report", "報告已寄出"),
    ("cancel", "已取消"),
]


class SaleOrder(models.Model):
    _inherit = "sale.order"

    request_inspection_date = fields.Date(string="收件日期")
    inspection_date = fields.Date(string="採檢日期")
    wf_confirmation_status = fields.Selection(
        [("Y", "已確認"), ("N", "未確認"), ("V", "作廢")],
        string="WF確認碼",
        default="N",
    )
    wf_quotation_confirmation_code = fields.Selection(
        [("Y", "已確認"), ("N", "未確認"), ("V", "作廢")],
        string="WF報價單確認碼",
        default="N",
    )
    order_source = fields.Selection(
        [("qrcode", "QR-code"), ("b2b", "B2B"), ("ocr", "OCR"), ("qt", "報價單")],
        string="訂單來源",
        default="qt",
        readonly=True,
    )
    allow_inspection = fields.Boolean(string="已收檢", default=False)
    wf_order_type = fields.Char(string="WF訂單單別", default="2240")
    wf_order_number = fields.Char(string="WF訂單單號")
    wf_tax_id = fields.Many2one(related="partner_id.wf_tax_id", string="WF稅別碼")
    wf_tax_type = fields.Selection(
        string="WF課稅別",
        related="wf_tax_id.tax_type",
    )
    odoo_tax_id = fields.Many2one(
        string="Odoo稅別", related="wf_tax_id.odoo_tax_id", store=True
    )
    partner_class_ids = fields.Many2many(
        "res.partner.class",
        "sale_order_partner_class_rel",
        "order_id",
        "class_id",
        string="客戶類別",
    )
    expedite_date = fields.Date(string="急件日期")
    expected_delivery_date = fields.Date(string="預計送達日")
    state = fields.Selection(
        selection=CUSTOM_SALE_ORDER_STATE,
        string="Status",
        readonly=True,
        copy=False,
        index=True,
        tracking=3,
        default="draft",
    )
    report_ids = fields.One2many("sale.order.report", "order_id", string="送檢單/報告")
    delivery_ids = fields.One2many(
        "sale.order.wf.delivery", "order_id", string="WF出貨歷程"
    )
    report_qty_equal = fields.Boolean(
        string="送檢單報告數量相符",
        compute="_compute_report_qty_equal",
        store=False,
    )
    total_qty = fields.Float(string='總數量', compute='_compute_total_qty', store=True, precompute=True, tracking=2)
    carrier_number_flag = fields.Boolean(string="前台是否可填寫物流單號", default=True)
    contains_consumables = fields.Boolean(string='包含耗材', compute='_compute_consumables', store=True)
    only_consumables = fields.Boolean(string='僅耗材', compute='_compute_consumables', store=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('website_id'):
                vals['order_source'] = 'b2b'
            # 預帶客戶標籤
            if not vals.get('tag_ids') and vals.get('partner_id'):
                partner = self.env['res.partner'].browse(vals['partner_id'])
                if partner.category_id:
                    category_names = partner.category_id.mapped('display_name')
                    matching_tags = self.env['crm.tag'].search([('name', '=', category_names)])
                    if matching_tags:
                        vals['tag_ids'] = [(6, 0, matching_tags.ids)]
        return super().create(vals_list)

    def write(self, vals):
        if 'wf_confirmation_status' in vals and vals['wf_confirmation_status'] == 'Y':
            vals['state'] = 'wf_confirm'
        if 'wf_confirmation_status' in vals and vals['wf_confirmation_status'] == 'V':
            vals['state'] = 'cancel'
        res = super().write(vals)

        watched = {
           "applied_coupon_ids",
            "coupon_point_ids",
            "reward_ids",
        }

        if watched.intersection(vals.keys()):
            for order in self:
                order.order_line._apply_auto_note()

        return res
    
    @api.onchange("partner_id")
    def _onchange_partner_id(self):
        for rec in self:
            if rec.partner_id:
                pricelist_id = self.env["product.pricelist"].search(
                    [("partner_id", "=", rec.partner_id.id)], limit=1
                )
                rec.pricelist_id = pricelist_id or False
            else:
                rec.pricelist_id = False

    @api.depends('order_line.product_uom_qty', 'order_line')
    def _compute_total_qty(self):
        for order in self:
            order.total_qty = sum(line.product_uom_qty for line in order.order_line)

    @api.depends("report_ids", "order_line")
    def _compute_report_qty_equal(self):
        qty_equals = []
        for order in self:
            for line in order.order_line:
                if line.product_template_id.detailed_type != "service":
                    continue
                if not line.product_template_id.category:
                    continue
                line_qty = line.product_uom_qty
                report_qty = len(
                    order.report_ids.filtered(lambda r: (r.order_line_id._origin or r.order_line_id).id == (line._origin or line).id)
                )
                qty_equals.append(line_qty == report_qty)

            order.report_qty_equal = all(qty_equals)

    def _manual_create_and_reserve_delivery(self):
        self.ensure_one()

        # 銷售訂單的補貨組，用來關聯出貨單
        if not self.procurement_group_id:
            self.procurement_group_id = self.env['procurement.group'].create({
                'name': self.name,
                'move_type': self.picking_policy,
                'sale_id': self.id,
                'partner_id': self.partner_id.id,
            })
        group_id = self.procurement_group_id

        # 2. 取得作業類型與庫位
        picking_type = self.env['stock.picking.type'].search([
            ('code', '=', 'outgoing'),
            ('company_id', '=', self.company_id.id)
        ], limit=1)

        source_location = picking_type.default_location_src_id or \
                          self.env['stock.warehouse'].search([('company_id', '=', self.company_id.id)],
                                                             limit=1).lot_stock_id
        dest_location = picking_type.default_location_dest_id or \
                        self.partner_id.property_stock_customer or \
                        self.env.ref('stock.stock_location_customers')

        # 建立出貨單頭
        picking = self.env['stock.picking'].create({
            'partner_id': self.partner_id.id,
            'picking_type_id': picking_type.id,
            'location_id': source_location.id,
            'location_dest_id': dest_location.id,
            'origin': self.name,
            'group_id': group_id.id,  # 這裡關聯了，sale_id 就會透過 related 出現
        })

        # 建立庫存移動
        for line in self.order_line:
            if line.product_id.type not in ['product', 'consu'] or line.product_uom_qty <= 0:
                continue

            move = self.env['stock.move'].create({
                'name': line.name,
                'product_id': line.product_id.id,
                'product_uom_qty': line.product_uom_qty,
                'product_uom': line.product_uom.id,
                'picking_id': picking.id,
                'location_id': source_location.id,
                'location_dest_id': dest_location.id,
                'sale_line_id': line.id,
                'group_id': group_id.id,
                'origin': self.name,
            })

            move._action_confirm()
            if line.lot_id:
                move._action_assign()
                for ml in move.move_line_ids:
                    ml.write({
                        'lot_id': line.lot_id.id,
                        'quantity': line.product_uom_qty,
                    })
            else:
                move._action_assign()

        return picking

    # 出貨單核實
    def _manual_validate_delivery(self):
        self.ensure_one()

        # 找到該訂單關聯且尚未完成的出貨單
        pickings = self.env['stock.picking'].search([
            ('sale_id', '=', self.id),
            ('state', 'not in', ['done', 'cancel'])
        ])

        for picking in pickings:
            for move in picking.move_ids:
                sale_line = move.sale_line_id
                product = sale_line.product_id

                if product.tracking != 'none':
                    # 1. 檢查批號是否已填 (前台下單可能未填，後台主管點擊前必須補齊)
                    if not sale_line.lot_id:
                        raise UserError(_(
                            "訂單 %s 核實失敗！\n產品 [%s] 尚未指定批號，請補齊批號後再執行核實。"
                        ) % (self.name, product.display_name))

                    # 2. 檢查實體在庫數量是否足夠
                    if sale_line.product_uom_qty > sale_line.quantity:
                        raise UserError(_(
                            "無法完成出貨！訂單 %s 庫存不足。\n"
                            "產品：[%s]\n批號：[%s]\n"
                            "需求數量：%.2f / 目前實體在庫：%.2f\n\n"
                            "請先辦理入庫補貨或更換批號。"
                        ) % (self.name, product.display_name, sale_line.lot_id.name,
                             sale_line.product_uom_qty, sale_line.quantity))

                move.move_line_ids.unlink()

                self.env['stock.move.line'].create({
                    'move_id': move.id,
                    'picking_id': picking.id,
                    'product_id': product.id,
                    'lot_id': sale_line.lot_id.id,
                    'quantity': sale_line.product_uom_qty,
                    'location_id': picking.location_id.id,
                    'location_dest_id': picking.location_dest_id.id,
                })

            # 執行驗證過帳
            try:
                # 使用 skip_backorder=True 避免產生欠單
                res = picking.with_context(skip_backorder=True).button_validate()
            except Exception as e:
                _logger.error(f"訂單 {self.name} 自動出貨驗證失敗: {str(e)}")
                raise UserError(_("庫存單據驗證失敗。錯誤訊息：%s") % str(e))

    @api.onchange("partner_id")
    def _onchange_partner_id_set_tax_and_class(self):
        for rec in self:
            if rec.partner_id:
                rec.wf_tax_id = rec.partner_id.wf_tax_id
                rec.partner_class_ids = [(6, 0, rec.partner_id.partner_class_ids.ids)]
                if rec.partner_id.partner_code:
                    if rec.partner_id.partner_code.startswith("1"):
                        rec.wf_order_type = "2240"
                    else:
                        rec.wf_order_type = "2250"
            else:
                rec.wf_tax_id = False
                rec.partner_class_ids = [(5, 0, 0)]

    @api.depends('order_line.product_template_id.product_category_id.name', 'order_line')
    def _compute_consumables(self):
        for order in self:
            order.contains_consumables = any(
                line.product_template_id.product_category_id and line.product_template_id.product_category_id.name == '耗材'
                for line in order.order_line
            )
            order.only_consumables = all(
                line.product_template_id.product_category_id and line.product_template_id.product_category_id.name == '耗材'
                for line in order.order_line
            )
    # 確認
    def _prepare_confirmation_values(self):
        values = super()._prepare_confirmation_values()
        values["state"] = "confirmed"
        # 耗材訂單產生出貨單
        if self.only_consumables:
            self._manual_create_and_reserve_delivery()
        return values

    # 已收件
    def action_toggle_allow_inspection(self):
        for record in self:
            record.allow_inspection = not record.allow_inspection

    def action_received(self):
        self._check_states_or_raise(allowed_states=['confirmed'], action_name='批次已收件')

        for record in self:
            if record.contains_consumables:
                raise UserError(_("包含耗材的訂單不可進行「已收件」"))
            if not record.allow_inspection:
                raise UserError(_("需勾選【已收檢】才可進行「已收件」"))

        self.write({
            "request_inspection_date": fields.Date.today(),
            "state": "received"
        })
        self.report_ids.compute_expected_date()

        notification = self.report_ids._check_duplicate_submission()
        if notification:
            return notification

    #耗材確認
    def action_active_consumables(self):
        if not self.only_consumables:
            raise UserError(_("請確保訂單只含有耗材，才能進行「耗材已確認」"))
        # 耗材訂單才檢查批號
        for order in self:
            if order.only_consumables:
                missing_lot_lines = order.order_line.filtered(
                    lambda l: l.product_id.tracking != 'none' and not l.lot_id
                )
                if missing_lot_lines:
                    msg = ", ".join(missing_lot_lines.mapped('product_id.name'))
                    raise UserError(_("此訂單為耗材訂單，產品 [%s] 必須填寫批號才能執行商務確認！") % msg)
        self.write({"state": "active"})
        for order in self:
            order._manual_validate_delivery()

    # 商務確認
    def action_active(self):
        self._check_states_or_raise(allowed_states=['received'], action_name='批次商務確認')

        # 確認WF客戶是否存在
        # 設定-同步WF開關
        target_group = self.env.ref('idx_wf_sync.group_prod_sync_wf')
        base_user_group = self.env.ref('base.group_user')
        is_enabled = target_group in base_user_group.implied_ids
        qty_invalid_orders = self.filtered(lambda o: not o.report_qty_equal)
        
        if not is_enabled:
            raise ValidationError("您沒有啟用同步WF開關，無法執行動作！")
        if not base_user_group:
            raise ValidationError(_("您沒有執行產品同步的權限"))
        if qty_invalid_orders:
            msg = "\n".join(o.name for o in qty_invalid_orders)
            raise UserError(_("以下單據「送檢單報告數量」與「單身明細數量」不符：\n%s") % msg)
        
        result = self.env['wf.mapping'].sudo()._odoo_to_wf_create(
            wf_model='COPTC',
            record_ids=self.ids,
            database=self.company_id.wf_db,
            wf_company=self.company_id.wf_company
        )
        message = _("訂單已同步WF") if result else _("同步失敗，請檢查相關設定或資料。")
        message_type = 'success' if result else 'danger'
        sticky = False
        
        if result:
            self.write({"state": "active", "carrier_number_flag": False})
            # 第一批物流資訊清空
            self.report_ids.write({"carrier": False, "carrier_number": False, "carrier_type": False})

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

    def action_sync_to_wf(self):
        """
            同步到WF
        """
        target_group = self.env.ref('idx_wf_sync.group_prod_sync_wf')
        base_user_group = self.env.ref('base.group_user')
        is_enabled = target_group in base_user_group.implied_ids
        if not is_enabled:
            raise ValidationError("您沒有啟用同步WF開關，無法執行動作！")
        if not base_user_group:
            raise ValidationError(_("您沒有執行產品同步的權限"))
        
        result = self.env['wf.mapping'].sudo()._odoo_to_wf_update(
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
    
    def action_wf_confirm(self):
        """
            主管WF確認
        """
        self._check_states_or_raise(allowed_states=['active'], action_name='批次主管WF確認')
        target_group = self.env.ref('idx_wf_sync.group_prod_sync_wf')
        base_user_group = self.env.ref('base.group_user')
        is_enabled = target_group in base_user_group.implied_ids
        
        if not is_enabled:
            raise ValidationError("您沒有啟用同步WF開關，無法執行動作！")
        if not base_user_group:
            raise ValidationError(_("您沒有執行產品同步的權限"))
        
        self.write({"wf_confirmation_status": "Y"})
        
        result = self.env['wf.mapping'].sudo()._odoo_to_wf_update(
            wf_model='COPTC',
            record_ids=self.ids,
            database=self.company_id.wf_db,
            wf_company=self.company_id.wf_company
        )
        message = _("訂單已同步WF") if result else _("同步失敗，請檢查相關設定或資料。")
        message_type = 'success' if result else 'danger'
        sticky = False
        
        if result:
            self.write({"state": "wf_confirm"})
        else:
            self.write({"wf_confirmation_status": "N"})
        
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

    # 已檢驗
    def action_inspected(self):
        self._check_states_or_raise(allowed_states=['wf_confirm'], action_name='批次已檢驗')

        self.write({
            "inspection_date": fields.Date.today(),
            "state": "inspected",
        })

    # 報告完成
    def action_reported(self):
        self._check_states_or_raise(allowed_states=['inspected'], action_name='批次報告已完成')
        self.write({"state": "reported"})

    # 寄出報告
    def action_sent_report(self):
        self._check_states_or_raise(allowed_states=['reported'], action_name='批次報告已寄出')

        self.write({"state": "sent_report", 'commitment_date': datetime.now()})

    def _action_cancel(self):
        """
        銷售訂單取消時，根據關聯出貨單的狀態決定取消或退貨
        """
        res = super(SaleOrder, self)._action_cancel()
        action_feedback = False

        for order in self:
            # 限定耗材訂單且有關聯出貨單才執行
            if not order.only_consumables or not order.picking_ids:
                continue
            picking = order.picking_ids[0]

            # 出貨單已完成 -> 執行銷貨退回
            if picking.state == 'done':
                action_feedback = self._handle_picking_return(picking)

            # 出貨單未完成且未取消 -> 取消出貨單
            elif picking.state not in ['cancel']:
                picking.action_cancel()
        if isinstance(action_feedback, dict):
            return action_feedback

        return res

    def _handle_picking_return(self, picking):
        """
        處理已完成出貨單的自動退貨邏輯
        """
        if not picking:
            return

        ReturnWizard = self.env['stock.return.picking']

        # 取得預設值，傳入 active_id
        ctx = {'active_id': picking.id, 'active_model': 'stock.picking'}
        default_vals = ReturnWizard.with_context(ctx).default_get(['product_return_moves', 'picking_id', 'location_id'])
        default_vals.update({
            'picking_id': picking.id,
        })

        # 建立退貨wizard
        return_wiz = ReturnWizard.with_context(ctx).create(default_vals)
        res = return_wiz.create_returns()

        # 自動審核銷貨退回單據
        return_picking_id = res.get('res_id')
        if return_picking_id:
            return_picking = self.env['stock.picking'].browse(return_picking_id)

            # 檢查是否有 move 行需要處理
            if return_picking.state == 'draft':
                return_picking.action_confirm()

            return_picking.action_assign()
            try:
                for move in return_picking.move_ids:
                    move.quantity = move.product_uom_qty
                return_picking.button_validate()
                return True
            except Exception as e:
                # 如果自動審核失敗，至少保留這張退貨單讓人工處理
                return {
                    "type": "ir.actions.client",
                    "tag": "display_notification",
                    "params": {
                        "title": _("自動退貨核實失敗"),
                        "message": _("退貨單 %s 已建立，但無法自動核實，請手動處理。錯誤原因：%s", return_picking.name,
                                     str(e)),
                        "sticky": True,
                        "type": "warning",
                        "next": {"type": "ir.actions.client", "tag": "soft_reload"},
                    },
                }
        return False

    def _try_apply_program(self, program, coupon=None):
        self.ensure_one()

        # 🔹 新增：檢查同 coupon 是否已使用
        if coupon and coupon in self.order_line.mapped('coupon_id'):
            return {'error': _('此優惠卷在訂單使用過.')}

        return super()._try_apply_program(program, coupon=coupon)
    
    #優惠卷檢查邏輯
    def _get_applied_programs(self):
        """
        Returns all applied programs on current order.

        Applied programs is the combination of both new points for your order and the programs linked to rewards.
        """
        self.ensure_one()
        return self._get_points_programs()
    
    #前台優惠卷list邏輯
    def _get_claimable_and_showable_rewards(self):
        self.ensure_one()
        res = {}

        # 搜尋符合條件的 loyalty card / coupon
        loyality_cards = self.env['loyalty.card'].search([
            ('partner_id', '=', self.partner_id.id),
            ('program_id', 'any', self._get_program_domain()),
            '|',
                ('program_id.trigger', '=', 'with_code'),
                '&', ('program_id.trigger', '=', 'auto'), ('program_id.applies_on', '=', 'future'),
        ])

        total_is_zero = float_is_zero(self.amount_total, precision_digits=2)
        global_discount_reward = self._get_applied_global_discount()

        for coupon in loyality_cards:
            # 🔹 核心修改：如果 coupon 已經使用過，就跳過
            if coupon in self.order_line.mapped('coupon_id'):
                continue

            points = self._get_real_points_for_coupon(coupon)

            # 遍歷該 coupon 對應 program 的 reward
            for reward in coupon.program_id.reward_ids:
                # 過濾不符合條件的 reward
                if reward.is_global_discount and global_discount_reward and global_discount_reward.discount >= reward.discount:
                    continue
                if reward.reward_type == 'discount' and total_is_zero:
                    continue
                if coupon.expiration_date and coupon.expiration_date < fields.Date.today():
                    continue
                # 點數足夠兌換 reward
                if points >= reward.required_points:
                    if coupon in res:
                        res[coupon] |= reward
                    else:
                        res[coupon] = reward

        return res

    def _cron_action_get_wf_and_sale_info(self):
        """
            定時批次取得WF訂單及出貨資訊
        """
        orders = self.search([('state', 'in', ['wf_confirm', 'inspected', 'reported'])])
        for order in orders:
            order.action_get_wf_and_sale_info()

    def action_get_wf_and_sale_info(self):
        """
            取得WF訂單及出貨資訊
        """
        self.ensure_one()
        wf_main_domain = f"TC058 IS NOT NULL AND TC001 = '{self.wf_order_type}' AND TC002 = '{self.wf_order_number}'"
        wf_domain = f" 1=1 "
        wf_line_domain = {
            'COPTD': f"TD001 = '{self.wf_order_type}' AND TD002 = '{self.wf_order_number}'",
        }

        wf_db = self.company_id.wf_db
        result = self.env['wf.mapping'].sudo()._wf_to_odoo_sync(
            wf_model='COPTC',
            wf_domain=wf_domain,
            wf_db=wf_db,
            wf_main_domain=wf_main_domain,
            wf_line_domain=wf_line_domain,
        )

        #同步WF銷貨單(PHSI13)單資訊到Odoo
        if result[0]:
            result = self._wf_to_odoo_sync_ship(wf_order_type = self.wf_order_type, wf_order_number = self.wf_order_number, wf_db = wf_db)

        message = _('批次同步完成。') if result else _(
            '同步失敗，請檢查相關設定或資料。')
        message_type = 'success' if result else 'danger'
        sticky = False

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': message,
                'type': message_type,
                'sticky': sticky,
                'next': {'type': 'ir.actions.act_window_close'} if result else None,
            }
        }
        
    def _wf_to_odoo_sync_ship(self, wf_order_type=None, wf_order_number=None, wf_db=None, wf_domain=None):
        """
        支援單一或多筆訂單的 WF 出貨單同步
        :param wf_order_type: 單別
        :param wf_order_number: (可選)單號，若無則用 wf_domain 查詢多筆
        :param wf_db: WF 資料庫
        :param wf_domain: (可選)SQL 條件字串，批次時用
        """
        def _format_date(date_str):
            """將日期從 YYYYMMDD 格式轉換為 YYYY-MM-DD"""
            if date_str and len(date_str) == 8 and date_str.isdigit():
                return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
            return False

        if not wf_db:
            _logger.warning("未提供 WF 資料庫參數，無法同步。")
            return False

        connection_params = self.env['wf.mapping'].sudo()._get_connection_parameters(wf_db)
        sql = (
            "SELECT DISTINCT TH001, TH002, TG003, TH014, TH015 "
            "FROM COPTG tg, COPTH th "
            "WHERE TG001 = TH001 AND TG002 = TH002 AND TG023 = 'Y' AND TH015 IS NOT NULL "
            "AND TH014 = ? "
        )
        params = [wf_order_type]

        if wf_order_number:
            sql += "AND TH015 = ? "
            params.extend([wf_order_number])
        elif wf_domain:
            sql += f"AND {wf_domain} "

        sql += "ORDER BY TH001, TH002, TG003"

        try:
            with pyodbc.connect(connection_params['connection_string'],
                                timeout=3) as connection, connection.cursor() as cursor:
                cursor.execute(sql, params)
                rows = cursor.fetchall()
        except Exception as e:
            _logger.warning(f"WF DB 連線失敗: {e}")
            return False

        count = 0
        WfDo = self.env['sale.order.wf.delivery'].sudo()
        for slip, name, do_date, so_slip, so_name in rows:
            slip = slip.strip() if isinstance(slip, str) else slip
            so_slip = so_slip.strip() if isinstance(so_slip, str) else so_slip
            name = name.strip() if isinstance(name, str) else name
            so_name = so_name.strip() if isinstance(so_name, str) else so_name
            do_date_fmt = _format_date(do_date)

            # 查找對應 Odoo 訂單
            order = self.env['sale.order'].sudo().search([
                ('wf_order_type', '=', so_slip),
                ('wf_order_number', '=', so_name)
            ], limit=1)
            if not order:
                _logger.warning(f"找不到對應訂單: 單別={so_slip}, 單號={so_name}")
                continue

            # 檢查是否已存在
            if WfDo.search_count([('order_id', '=', order.id), ('wf_delivery_type', '=', slip), ('wf_delivery_number', '=', name)]) > 0:
                continue

            # 建立 WF 出貨歷程
            WfDo.create({
                'order_id': order.id,
                'wf_delivery_type': slip,
                'wf_delivery_number': name,
                'wf_delivery_date': do_date_fmt
            })
            count += 1

        _logger.info(f"公司 {wf_db} 成功同步 {count} 筆 WF 出貨單。")
        return True

    def _get_reward_values_product(self, reward, coupon, product=None, **kwargs):
        """移除 loyalty 自動計算的 sequence（max 非獎勵行 + 1），
        改由 sale_order_line.create() 統一以 max+1 分配，
        同時避免 re-evaluate 時 write() 覆蓋已存在獎勵行的序號。"""
        result = super()._get_reward_values_product(reward, coupon, product, **kwargs)
        return self._pop_reward_sequence(result)

    def _get_reward_values_discount(self, reward, coupon, **kwargs):
        """同 _get_reward_values_product，移除 sequence 交由 create() 統一分配。"""
        result = super()._get_reward_values_discount(reward, coupon, **kwargs)
        return self._pop_reward_sequence(result)

    def _pop_reward_sequence(self, vals_list: list) -> list:
        """從獎勵行 vals 中移除 sequence 欄位。"""
        for vals in vals_list:
            vals.pop('sequence', None)
        return vals_list

    def _check_states_or_raise(self, allowed_states, action_name):
        state_label_map = dict(CUSTOM_SALE_ORDER_STATE)

        invalid_orders = self.filtered(lambda o: o.state not in allowed_states)
        if invalid_orders:
            msg = "\n".join([
                f"{o.name}（目前狀態：{state_label_map.get(o.state, o.state)}）"
                for o in invalid_orders
            ])
            raise UserError(_(f"以下單據無法執行「{action_name}」，狀態不符：\n{msg}"))
