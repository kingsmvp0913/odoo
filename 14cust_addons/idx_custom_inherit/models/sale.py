from odoo import api, fields, models, _

class SaleOrder(models.Model):
    _inherit = 'sale.order'
    reply_date = fields.Date(string='客戶回覆日期')
    # 測試資料型別錯誤，先註解掉
    # client_order_ref = fields.Integer()
    
    related_sale_ids = fields.One2many(
        'idx.sale.related',
        'sale_id',
        string='相關人員'
    )
    
    def open_update_invo_wizard(self):
        action = self.env.ref('idx_custom_inherit.idx_update_invo_item_wizard').read()[0]
        action['context'] = {
            'default_order_id': self.id
        }
        return action
            
    name_and_customer = fields.Char(string='訂單名稱與客戶名稱', compute='combine_name_and_customer');
    def combine_name_and_customer(self):
        for order in self:
            order.name_and_customer = f'{order.name} - {order.partner_id.name}'
            
    def name_get(self):
        result = []        
        for rec in self:
            name = f'{rec.name} - {rec.partner_id.name}'
            result.append((rec.id, name))
        return result            
    
    @api.model
    def create(self, vals):
        # 如果有帶入公司ID的話先切換
        if 'company_id' in vals:
            self = self.with_company(vals['company_id'])
        # 如果是新增的話產生編號
        if vals.get('name', _('New')) == _('New'):
            seq_date = None
            if 'date_order' in vals:
                seq_date = fields.Datetime.context_timestamp(self, fields.Datetime.to_datetime(vals['date_order']))
            vals['name'] = self.env['ir.sequence'].next_by_code('sale.order', sequence_date=seq_date) or _('New')

        # Makes sure partner_invoice_id', 'partner_shipping_id' and 'pricelist_id' are defined
        if any(f not in vals for f in ['partner_invoice_id', 'partner_shipping_id', 'pricelist_id']):
            partner = self.env['res.partner'].browse(vals.get('partner_id'))
            addr = partner.address_get(['delivery', 'invoice'])
            vals['partner_invoice_id'] = vals.setdefault('partner_invoice_id', addr['invoice'])
            vals['partner_shipping_id'] = vals.setdefault('partner_shipping_id', addr['delivery'])
            vals['pricelist_id'] = vals.setdefault('pricelist_id', partner.property_product_pricelist.id)
        result = super(SaleOrder, self).create(vals)
        return result
        
    # 報修單上的相關人員
    def open_related_lines(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("idx_custom_inherit.action_idx_custom_inherit_related")
        action['domain'] = [
            ('sale_id', '=', self.id)
        ]
        action['context'] = {'default_sale_id': self.id}
        return action   



class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'
    invoice_name = fields.Char(string='發票名稱', required=True) 
    
    @api.onchange('product_id')
    def onchange_product_id(self):
        for rec in self:
            if rec.product_id:
                rec.invoice_name = rec.product_id.name

class IDXSaleRelated(models.Model):
    _name = 'idx.sale.related'
    _description = "相關人員"

    sale_id = fields.Many2one('sale.order', string='報價單', required=True)
    user_id = fields.Many2one('res.users', string='相關人員')
