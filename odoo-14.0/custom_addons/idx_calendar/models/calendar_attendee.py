from odoo import api, fields, models, _
from odoo.exceptions import UserError
import pytz
from datetime import timedelta
import vobject
class Attendee(models.Model):
    _inherit = 'calendar.attendee'

    def _notify_attendees(self, ics_files, mail_template, rendering_context, force_send):
        # mail作者與收件人相同的話會跳過發信，抓第一筆res.partner資料來設為mail作者
        author_id = self.env['res.partner'].search([('active', '=', True)], order='id ASC', limit=1).id
        for attendee in self:
            if attendee.email and attendee.partner_id != self.env.user.partner_id:
                # FIXME: is ics_file text or bytes?
                event_id = attendee.event_id.id
                ics_file = ics_files.get(event_id)

                attachment_values = []
                if ics_file:
                    attachment_values = attendee._prepare_notification_attachment_values(ics_file)
                try:
                    body = mail_template.with_context(rendering_context)._render_field(
                        'body_html',
                        attendee.ids,
                        compute_lang=True,
                        post_process=True)[attendee.id]
                except UserError:  # TO BE REMOVED IN MASTER
                    body = mail_template.sudo().with_context(rendering_context)._render_field(
                        'body_html',
                        attendee.ids,
                        compute_lang=True,
                        post_process=True)[attendee.id]
                subject = mail_template.with_context(safe=True)._render_field(
                    'subject',
                    attendee.ids,
                    compute_lang=True)[attendee.id]
                attendee.event_id.with_context(no_document=True).message_notify(
                    email_from=attendee.event_id.user_id.email_formatted or self.env.user.email_formatted,
                    author_id=author_id,
                    body=body,
                    subject=subject,
                    partner_ids=attendee.partner_id.ids,
                    email_layout_xmlid='mail.mail_notification_light',
                    attachment_ids=attachment_values,
                    force_send=force_send)
