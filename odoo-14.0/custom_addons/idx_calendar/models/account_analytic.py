# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class AccountAnalyticLine(models.Model):
    _inherit = 'account.analytic.line'

    event_id = fields.Many2one("calendar.event", string='會議id')

    # def unlink(self):
    #     if any(line.event_id for line in self):
    #         raise UserError(_('此工時表為會議創建時自動建立，不可於此直接刪除'))
    #     return super(AccountAnalyticLine, self).unlink()
