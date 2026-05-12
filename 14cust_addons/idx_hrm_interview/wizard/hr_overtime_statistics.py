from odoo import api, fields, models


class HrOvertimeStatisticsWizard(models.TransientModel):
    _name = "hr.overtime.statistics.wizard"
    _description = '加班統計表'

    date_start = fields.Date(string='開始日期')
    date_end = fields.Date(string='結束日期')

    def overtime_statistics_check(self):
        print('test')

