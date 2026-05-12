# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    module_project_timesheet_event = fields.Boolean(string='紀錄會議工時')
    event_timesheet_project_id = fields.Many2one('project.project', string="專案")
    event_timesheet_task_id = fields.Many2one('project.task', string="任務",
                                              domain="[('project_id', '=?', event_timesheet_project_id)]")

    @api.onchange('event_timesheet_project_id')
    def _onchange_timesheet_project_id(self):
        if self.event_timesheet_project_id != self.event_timesheet_task_id.project_id:
            self.event_timesheet_task_id = False

    @api.onchange('event_timesheet_task_id')
    def _onchange_timesheet_task_id(self):
        if self.event_timesheet_task_id:
            self.event_timesheet_project_id = self.event_timesheet_task_id.project_id

    def set_values(self):
        super(ResConfigSettings, self).set_values()
        self.env['ir.config_parameter'].sudo().set_param('module_project_timesheet_event', self.module_project_timesheet_event)
        self.env['ir.config_parameter'].sudo().set_param('event_timesheet_project_id',
                                                         self.event_timesheet_project_id.id)
        self.env['ir.config_parameter'].sudo().set_param('event_timesheet_task_id', self.event_timesheet_task_id.id)

    @api.model
    def get_values(self):
        res = super(ResConfigSettings, self).get_values()

        params = self.env['ir.config_parameter'].sudo()
        module_project_timesheet_event = params.get_param('module_project_timesheet_event', default=False)
        event_timesheet_project_id = params.get_param('event_timesheet_project_id', default=False)
        event_timesheet_task_id = params.get_param('event_timesheet_task_id', default=False)

        res.update(
            module_project_timesheet_event=module_project_timesheet_event if module_project_timesheet_event else False,
            event_timesheet_project_id=int(event_timesheet_project_id) if event_timesheet_project_id else False,
            event_timesheet_task_id=int(event_timesheet_task_id) if event_timesheet_task_id else False,
        )
        return res
