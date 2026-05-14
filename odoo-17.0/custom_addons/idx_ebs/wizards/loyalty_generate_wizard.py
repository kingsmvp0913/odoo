# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.osv import expression


class LoyaltyGenerateWizard(models.TransientModel):
    _inherit = "loyalty.generate.wizard"

    mode = fields.Selection(
        [("anonymous", "匿名客戶"), ("selected", "已選取客戶")],
        string="對於",
        required=True,
        default="selected",
    )
    coupon_batch_qty = fields.Integer(
        string="批量生成",
        default=1,
        required=True,
    )
    total_coupon_qty = fields.Integer(
        string="總生成數量",
        compute="_compute_total_coupon_qty",
    )

    @api.depends("coupon_qty", "coupon_batch_qty")
    def _compute_total_coupon_qty(self):
        for wizard in self:
            wizard.total_coupon_qty = wizard.coupon_qty * wizard.coupon_batch_qty

    def generate_coupons(self):
        """生成優惠券"""
        if any(not wizard.program_id for wizard in self):
            raise ValidationError(_("會員計劃不存在，請選擇計劃。"))
        if any(wizard.coupon_qty <= 0 for wizard in self):
            raise ValidationError(_("數量無效。請輸入大於0的數量。"))
        if any(
            wizard.program_type == "coupons" and wizard.coupon_batch_qty <= 0
            for wizard in self
        ):
            raise ValidationError(_("優惠券的批量生成欄位必須大於0。"))
        coupon_create_vals = []
        for wizard in self:
            customers = wizard._get_partners() or range(wizard.coupon_qty)
            for partner in customers:
                for _ in range(wizard.coupon_batch_qty):
                    coupon_create_vals.append(wizard._get_coupon_values(partner))
        self.env["loyalty.card"].create(coupon_create_vals)
        return True
