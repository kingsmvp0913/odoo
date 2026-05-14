from odoo import api, models, fields, _

class SaleOrderWfDelivery(models.Model):
    _name = 'sale.order.wf.delivery'
    _description = "WF出貨歷程"
    _order = 'wf_delivery_date desc'
    
    order_id = fields.Many2one(
        comodel_name="sale.order",
        string="銷售訂單",
        ondelete="cascade",
        index=True,
    )
    wf_delivery_type = fields.Char(string="WF出貨單別")
    wf_delivery_number = fields.Char(string="WF出貨單號")
    wf_delivery_date = fields.Date(string="WF出貨日期")

    @api.depends('wf_delivery_type', 'wf_delivery_number')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = f"{rec.wf_delivery_type or ''}-{rec.wf_delivery_number or ''}"
    
    
    
    