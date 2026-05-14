from odoo import models, fields, api
from odoo.exceptions import ValidationError


class LoyaltyProgram(models.Model):
    _inherit = "loyalty.program"

    program_type = fields.Selection(
        [
            ("coupons", "優惠券"),
            ("gift_card", "禮物卡"),
            ("loyalty", "會員卡"),
            ("promotion", "促銷"),
            ("ewallet", "電子錢包"),
            ("promo_code", "折扣代碼"),
            ("buy_x_get_y", "買X送Y"),
            ("next_order_coupons", "下一訂單優惠券"),
        ],
        default="coupons",
        required=True,
    )
    project_code = fields.Many2one(
        comodel_name="loyalty.program.code",
        string="專案代碼",
        ondelete="restrict",
        required=True,
        tracking=True,
    )
    head = fields.Many2one(
        string="負責人員",
        comodel_name="res.users",
        required=True,
        tracking=True,
        ondelete="restrict",
    )

    @api.constrains("program_type", "project_code", "head")
    def _check_program_constraints(self):
        for record in self:
            if not record.program_type:
                raise ValidationError("計劃類型為必填項目。")
            if not record.project_code:
                raise ValidationError("專案代碼為必填項目。")
            if not record.head:
                raise ValidationError("負責人員為必填項目。")
