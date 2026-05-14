from odoo import api, fields, models
import logging

_logger = logging.getLogger(__name__)


class IDXProductCatrgory(models.Model):
    _name = "idx.product.category"
    _description = "商品類別"

    name = fields.Char(string="標籤名稱", required=True)
    active = fields.Boolean(string="生效否", default=True)