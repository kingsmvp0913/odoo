from odoo import api, fields, models
import logging

_logger = logging.getLogger(__name__)


class IDXEcommerceWarehouse(models.Model):
    _name = "idx.ecommerce.warehouse"
    _rec_name = 'code'
    _rec_names_search = ['code']
    _description = "電子商務倉庫"

    name = fields.Char(string="倉庫名稱", required=True)
    code = fields.Char(string="倉庫代號", required=True)
    active = fields.Boolean(string="生效否", default=True)