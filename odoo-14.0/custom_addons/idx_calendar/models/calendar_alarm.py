from odoo import api, fields, models, _


class CalendarAlarm(models.Model):
    _inherit = 'calendar.alarm'
    _order = 'sequence'

    sequence = fields.Integer(string='顯示順序')