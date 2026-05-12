from odoo import models, fields, api


class meeting_room(models.Model):
    _name = 'idx.calendar.meeting.room'

    room = fields.Char(string='會議室代稱')
    name = fields.Char(string='會議室', required=True)
    description = fields.Char(string='說明')
    limit = fields.Integer(string='最多人數')
    color = fields.Integer(string='顏色')
    is_entity = fields.Boolean(string='實體會議室', default=True)




