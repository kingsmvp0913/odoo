from odoo import api, models, fields, _
from odoo.exceptions import ValidationError

class RelatedCompany(models.Model):
    _name = 'related.company'
    _description = '關係公司'
    
    name = fields.Char(string='關係公司', required=True, translate=True)
    color = fields.Integer(string='顏色')
    
    _sql_constraints = [
        ('name_unique', 'unique (name)', '關係公司名稱已存在，請勿重複!'),
    ]