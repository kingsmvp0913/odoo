from odoo import api, fields, models, _
import logging

_logger = logging.getLogger(__name__)


class IDXProductInspectType(models.Model):
    _name = "idx.product.inspect"
    _description = "檢驗別"

    name = fields.Char(string="檢驗別", required=True)
    color = fields.Integer(string="顏色", default=0)
    active = fields.Boolean(string="生效否", default=True)
