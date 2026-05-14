import logging
from odoo import models, fields


class LogisticsCache(models.TransientModel):
    _name = "logistics.cache"
    _description = "物流暫存"
    _order = "create_date desc"

    uuid = fields.Char(string="UUID", required=True)
    carrier = fields.Char(string="物流", required=True)
    carrier_number = fields.Char(string="物流編號", required=True)
    carrier_type = fields.Char(string="物流狀態")
    fetch_message = fields.Text(string="物流api執行後，儲存通知訊息")
