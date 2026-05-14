from odoo import api, fields, models, _
import logging

_logger = logging.getLogger(__name__)


class StockQuant(models.Model):
    _inherit = "stock.quant"

    alert_date = fields.Datetime(string="警示日期", related="lot_id.alert_date", store=False)
    valid_days_remaining = fields.Integer(string="剩餘有效天數", related="lot_id.valid_days_remaining", store=False)
    
    #複寫原生 訪止原生清除數量為 0 stock.quant
    @api.depends('quant_ids', 'quant_ids.quantity')
    def _compute_single_location(self):
        for lot in self:
            quants = lot.quant_ids
            lot.location_id = quants.location_id if len(quants.location_id) == 1 else False

