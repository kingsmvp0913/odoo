from odoo import api, models, fields, _
from odoo.exceptions import ValidationError

class ResPartnerClass(models.Model):
    _name = 'res.partner.class'
    _description = 'Customer Class/Tag'
    
    name = fields.Char(string='客戶類別', required=True, translate=True)
    color = fields.Integer(string='顏色')
    
    _sql_constraints = [
        ('name_unique', 'unique (name)', '客戶類別名稱已存在，請勿重複!'),
    ]