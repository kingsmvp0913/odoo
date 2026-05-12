import json
from urllib.parse import quote
from odoo import api, fields, models, _


class IrActionsActions(models.Model):
    _inherit = 'ir.actions.actions'

    @api.model
    def get_bindings(self, model_name):
        result = super().get_bindings(model_name)
        # Odoo 13 get_bindings sorts by id, not sequence — fix that here
        for binding_type in result:
            result[binding_type].sort(
                key=lambda a: (a.get('sequence', 5), a.get('name', ''))
            )
        return result


class ExportInvoCsv(models.Model):
    _inherit = 'account.move'

    def action_export_csv(self):
        if self.ids:
            url = '/export_invo_csv/download?ids={}'.format(
                ','.join(str(i) for i in self.ids)
            )
        else:
            domain = self.env.context.get('active_domain', [])
            url = '/export_invo_csv/download?domain={}'.format(
                quote(json.dumps(domain))
            )
        return {
            'type': 'ir.actions.act_url',
            'url': url,
            'target': 'self',
        }