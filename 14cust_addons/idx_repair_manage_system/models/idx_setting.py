from odoo import api, fields, models
import requests

class service_setting(models.TransientModel):
    _inherit = "res.config.settings"

    line_notification = fields.Boolean(string='LINE通知', copy=False)
   
    def set_values(self):
        res = super(service_setting, self).set_values()
        self.env['ir.config_parameter'].set_param('e_service.line_notification', self.line_notification)
        return res

    @api.model
    def get_values(self):
        res = super(service_setting, self).get_values()
        sudo = self.env['ir.config_parameter'].sudo()
        note = sudo.get_param('e_service.line_notification')

        res.update(
            line_notification=note
        )
        return res

