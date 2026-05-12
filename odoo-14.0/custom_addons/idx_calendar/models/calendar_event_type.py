from odoo import api, fields, models, _


class CalendarEventType(models.Model):
    _inherit = 'calendar.event.type'
    _order = 'sequence'

    sequence = fields.Integer(string='顯示順序')
    active = fields.Boolean(default=True)