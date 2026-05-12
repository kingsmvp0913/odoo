from odoo import api, fields, models

class IDSUpdateInvoItemWizard(models.TransientModel):
    _name = 'idx.update.invo.item.wizard'
    _description = "更新發票品名"
        
    order_id = fields.Many2one('sale.order', string="訂單", required=True)
    line_id = fields.Many2one('sale.order.line', string='商品明細', required=True, domain="[('order_id', '=', order_id)]")
    invoice_name = fields.Char(string='發票名稱', required=True)
    
    @api.onchange('line_id')
    def onchange_line_id(self):
        for rec in self:
            if rec.line_id:
                rec.invoice_name = rec.line_id.name
        
    def write_invo_item(self):
        for rec in self:
            if rec.line_id:
                rec.line_id.write({
                    'invoice_name': rec.invoice_name,
                })

        return {'type': 'ir.actions.act_window_close'}