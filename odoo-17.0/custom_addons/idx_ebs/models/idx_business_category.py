from odoo import api, fields, models
import logging

_logger = logging.getLogger(__name__)


class IDXBusinessCategory(models.Model):
    _name = "idx.business.category"
    _description = "業務類別"

    name = fields.Char(string="標籤名稱", required=True)
    active = fields.Boolean(string="生效否", default=True)