from odoo import models, fields, api


class HrOvertimeStatisticsRecord(models.Model):
    _name = "hr.overtime.statistics.record"
    _description = "加班統計明細"
    _order = 'work_day'

    work_day = fields.Date(string='日期')
    overtime_start = fields.Datetime(string='申請日期(起)')
    overtime_end = fields.Datetime(string='申請日期(訖)')
    worked_hours = fields.Float(string='總工時')
    type = fields.Selection(string='假別', selection=[("cash", "現金"), ("leave", "補休")])
    overtime_type = fields.Char(string='加班類型')
    overtime_pay = fields.Float(string='加班費')
