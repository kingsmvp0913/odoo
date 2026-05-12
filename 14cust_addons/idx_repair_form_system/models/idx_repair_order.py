from odoo import fields, models, api 
from datetime import datetime
from odoo.exceptions import ValidationError

class IdxRepairOrder(models.Model):
    _name = "idx.repair.order"
    _description = "維修表單"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    
    name = fields.Char(string='維修單號', required=True, copy=False, readonly=True, default=lambda self: 'New')
    receipt_user_id = fields.Many2one('res.users', string='收件人員', default=lambda self: self.env.user, tracking=True)
    partner_id = fields.Many2one('res.partner', string='送修人員', required=True, tracking=True)
    repair_date = fields.Date(string='報修日期', default=fields.Date.today, required=True, tracking=True)
    receipt_date = fields.Date(string='收件日期', tracking=True)
    is_warranty = fields.Boolean(string='保固期間內', default=False)
    repair_line_ids = fields.One2many('idx.repair.order.line', 'order_id', string='維修單明細')
    repair_amount = fields.Float(string='維修金額', readonly=True, compute='_compute_repair_amount')
    
    @api.depends('repair_line_ids.total_amount')
    def _compute_repair_amount(self):
        for order in self:
            order.repair_amount = sum(line.total_amount for line in order.repair_line_ids)
            
    # 檢查日期
    def _check_repair_date(self, vals):
        repair_date = vals.get('repair_date')
        receipt_date = vals.get('receipt_date')
        
        #字串轉date
        if isinstance(repair_date, str):
            repair_date = datetime.strptime(repair_date, '%Y-%m-%d').date()
        if isinstance(receipt_date, str):
            receipt_date = datetime.strptime(receipt_date, '%Y-%m-%d').date()

        if (repair_date and receipt_date and repair_date >= receipt_date):
            raise ValidationError('報修日期須早於收件日期') 
                    
    @api.model
    def create(self, vals):
        
        self._check_repair_date(vals)
        
        if vals.get('name', 'New') == 'New':

            # 取得流水號（每月自動 reset）
            seq = self.env['ir.sequence'].next_by_code('idx.repair.order') or '001'

            # 取得 yymm
            today = datetime.today()
            yymm = today.strftime('%y%m')

            # 組單號
            vals['name'] = f"RO-{yymm}{seq.zfill(3)}"

        return super().create(vals)
    
    def write(self, vals):
        self._check_repair_date(vals)
        return super().write(vals)
        
            
    
    
class IdxRepairOrderLine(models.Model):
    _name = 'idx.repair.order.line'
    _description = "維修單明細"
    
    order_id = fields.Many2one('idx.repair.order', string='維修單單頭', readonly=True, ondelete='cascade')
    name = fields.Char(string='維修品名', required=True)
    qty = fields.Integer(string='數量', default=1, required=True)
    amount = fields.Float(string='金額', default=0, required=True)
    total_amount = fields.Float(string='合計', compute='_compute_total_amount', readonly=True)

    @api.depends('qty', 'amount')
    def _compute_total_amount(self):
        for line in self:
            line.total_amount = line.qty * line.amount
    

    