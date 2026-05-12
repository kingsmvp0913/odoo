from odoo import api, fields, models
from odoo.exceptions import UserError

class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'
    
    # 客製欄位
    is_repair = fields.Boolean(string='維修', default=False)
    # 只有詢價單、採購訂單才能編輯
    is_repair_readonly = fields.Boolean(compute='_compute_is_repair_readonly')
    def _compute_is_repair_readonly(self):
        for order in self:
            order.is_repair_readonly = order.state not in ['draft', 'purchase']
    
    partner_email = fields.Char(string='供應商email', related='partner_id.email')
    inquiry_date = fields.Date(string='詢價日期')

    # 客製邏輯
    @api.model
    def create(self, vals):
        # 詢價日期預設訂單截止日期，如果還是沒有的話抓今天
        default_date = vals.get('date_order') or fields.Datetime.now()
        default_date = fields.Date.to_date(default_date)
        vals['inquiry_date'] = vals.get('inquiry_date') or default_date

        return super().create(vals)
    
    def button_cancel(self):
        for order in self:
            if order.is_repair == True:
                raise UserError('採購單已有開立發票，不可取消')
        return super().button_cancel()
    