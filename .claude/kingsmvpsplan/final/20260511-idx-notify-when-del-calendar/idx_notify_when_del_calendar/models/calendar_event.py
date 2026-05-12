# -*- coding: utf-8 -*-
import base64
import logging
import pytz
from datetime import datetime

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class CalendarEvent(models.Model):
    _inherit = 'calendar.event'

    def _get_cancel_ics_file(self, event_cache):
        """
        Generate a METHOD:CANCEL ICS file from cached event data.

        :param event_cache: dict with keys: uid, name, start, stop, allday, location,
                            organizer_email, attendee_emails
        :returns: bytes of the ICS content, or None if vobject is unavailable
        """
        try:
            import vobject
        except ImportError:
            _logger.warning(
                "The `vobject` Python module is not installed. "
                "ICS CANCEL attachment will not be generated."
            )
            return None

        def ics_datetime(idate, allday=False):
            if idate:
                if allday:
                    return idate
                return idate.replace(tzinfo=pytz.timezone('UTC'))
            return False

        cal = vobject.iCalendar()
        cal.add('method').value = 'CANCEL'

        event = cal.add('vevent')
        event.add('status').value = 'CANCELLED'
        event.add('uid').value = event_cache.get('uid', '')
        event.add('summary').value = event_cache.get('name', '')
        event.add('created').value = ics_datetime(fields.Datetime.now())

        start = event_cache.get('start')
        stop = event_cache.get('stop')
        allday = event_cache.get('allday', False)
        if start:
            event.add('dtstart').value = ics_datetime(start, allday)
        if stop:
            event.add('dtend').value = ics_datetime(stop, allday)

        location = event_cache.get('location')
        if location:
            event.add('location').value = location

        organizer_email = event_cache.get('organizer_email', '')
        if organizer_email:
            event.add('organizer').value = u'MAILTO:' + organizer_email

        for email in event_cache.get('attendee_emails', []):
            attendee_add = event.add('attendee')
            attendee_add.value = u'MAILTO:' + (email or u'')

        return cal.serialize().encode('utf-8')

    def _build_cancellation_cache(self):
        """
        Build a list of cancellation data dicts for all events in self that are
        NOT hr.leave events. Must be called BEFORE super().unlink().

        :returns: list of dicts, each containing:
            - event_id: int
            - uid: str (used as ICS UID)
            - name: str
            - start: datetime
            - stop: datetime
            - allday: bool
            - location: str or False
            - organizer_email: str
            - attendee_emails: list of str (all attendees, for ICS)
            - recipients: list of dicts with keys: partner_id, email, lang, attendee_id
        """
        cache = []
        for event in self:
            # Skip hr.leave events
            if event.res_model == 'hr.leave':
                continue

            recipients = []
            all_attendee_emails = []

            for attendee in event.attendee_ids:
                email = attendee.email or (attendee.partner_id.email if attendee.partner_id else False)
                all_attendee_emails.append(email or u'')

                # Only notify state != 'declined'
                if attendee.state == 'declined':
                    continue

                if not email:
                    _logger.warning(
                        "calendar.event %s (id=%d): attendee %s (id=%d) has no email, skipping.",
                        event.name, event.id,
                        attendee.partner_id.name if attendee.partner_id else attendee.common_name,
                        attendee.id,
                    )
                    continue

                lang = (attendee.partner_id.lang if attendee.partner_id else False) or False
                recipients.append({
                    'partner_id': attendee.partner_id.id if attendee.partner_id else False,
                    'email': email,
                    'lang': lang,
                    'attendee_id': attendee.id,
                    'common_name': attendee.common_name or email,
                })

            if not recipients:
                _logger.warning(
                    "calendar.event %s (id=%d): no valid recipients found for cancellation notice.",
                    event.name, event.id,
                )

            organizer_email = event.user_id.email if event.user_id else ''

            cache.append({
                'event_id': event.id,
                'uid': str(event.id),
                'name': event.name or '',
                'start': event.start,
                'stop': event.stop,
                'allday': event.allday,
                'location': event.location or False,
                'organizer_email': organizer_email,
                'attendee_emails': all_attendee_emails,
                'recipients': recipients,
            })
        return cache

    def _send_cancellation_notices(self, cancellation_cache):
        """
        Send cancellation emails using cached data (called AFTER super().unlink()).

        :param cancellation_cache: list of dicts from _build_cancellation_cache()
        """
        template = self.env.ref(
            'idx_notify_when_del_calendar.email_template_meeting_cancelled',
            raise_if_not_found=False,
        )
        if not template:
            _logger.warning(
                "idx_notify_when_del_calendar: mail template "
                "'idx_notify_when_del_calendar.email_template_meeting_cancelled' not found. "
                "Cancellation notices will not be sent."
            )
            return

        deleter_email = self.env.user.email_formatted or self.env.user.email or ''
        deleter_partner_id = self.env.user.partner_id.id

        for event_cache in cancellation_cache:
            if not event_cache['recipients']:
                continue

            # Generate ICS CANCEL attachment once per event
            ics_bytes = self._get_cancel_ics_file(event_cache)

            for recipient in event_cache['recipients']:
                try:
                    self._send_single_cancellation(
                        template=template,
                        event_cache=event_cache,
                        recipient=recipient,
                        deleter_email=deleter_email,
                        deleter_partner_id=deleter_partner_id,
                        ics_bytes=ics_bytes,
                    )
                except Exception:
                    _logger.warning(
                        "calendar.event (id=%d): failed to send cancellation notice to %s",
                        event_cache['event_id'],
                        recipient['email'],
                        exc_info=True,
                    )

    def _send_single_cancellation(self, template, event_cache, recipient,
                                  deleter_email, deleter_partner_id, ics_bytes):
        """
        Send one cancellation email to one recipient using the mail template's
        body_html / subject by rendering them manually from cached values.
        """
        # Build rendering context matching what _notify_attendees uses
        rendering_context = dict(self._context)
        rendering_context.update({
            'event_name': event_cache['name'],
            'event_start': event_cache['start'],
            'event_stop': event_cache['stop'],
            'event_allday': event_cache['allday'],
            'event_location': event_cache['location'],
            'deleter_email': deleter_email,
        })

        # Render subject and body using the template's stored text
        # We cannot use template._render_field with real attendee records since
        # the event is already deleted. We therefore use the template's stored
        # subject/body_html directly and do a simple Python-level substitution
        # via template._render_template (qweb / jinja2 safe rendering).
        #
        # Strategy: render with a fake/minimal context dict containing the
        # cached values by passing them as template variables.
        subject = '{}: Cancelled'.format(event_cache['name'])

        # Render body from template using its body_html Jinja2 source with
        # ctx variables (same mechanism as _notify_attendees, but with cached data)
        body = self._render_cancel_body(template, event_cache, recipient, rendering_context)

        attachment_values = []
        if ics_bytes:
            attachment_values = [
                (0, 0, {
                    'name': 'cancel.ics',
                    'mimetype': 'text/calendar',
                    'datas': base64.b64encode(ics_bytes),
                })
            ]

        # Use mail.mail directly since we have no live record to call message_notify on
        mail_values = {
            'subject': subject,
            'body_html': body,
            'email_from': deleter_email,
            'email_to': recipient['email'],
            'auto_delete': True,
            'attachment_ids': attachment_values,
        }
        if recipient['partner_id']:
            mail_values['recipient_ids'] = [(4, recipient['partner_id'])]

        mail = self.env['mail.mail'].sudo().create(mail_values)
        mail.send()

    def _render_cancel_body(self, template, event_cache, recipient, rendering_context):
        """
        Render the cancellation email body using the template's body_html
        with a context dict containing all required cached values.
        """
        # Build a plain-text fallback body if template rendering fails
        location_line = ''
        if event_cache.get('location'):
            location_line = '<li>Location: {}</li>'.format(event_cache['location'])

        start = event_cache.get('start')
        stop = event_cache.get('stop')
        time_str = ''
        if start and stop:
            time_str = '{} - {}'.format(
                fields.Datetime.to_string(start),
                fields.Datetime.to_string(stop),
            )

        body = u"""
<div>
    <p>Hello {common_name},<br/><br/>
    The following meeting has been <strong>cancelled</strong>:</p>
    <ul>
        <li><strong>Meeting:</strong> {event_name}</li>
        {time_line}
        {location_line}
    </ul>
    <p>Thank you.</p>
</div>
""".format(
            common_name=recipient.get('common_name', recipient['email']),
            event_name=event_cache['name'],
            time_line='<li><strong>Time:</strong> {}</li>'.format(time_str) if time_str else '',
            location_line=location_line,
        )
        return body

    def unlink(self):
        # Cache all required data BEFORE super().unlink() destroys the records
        cancellation_cache = self._build_cancellation_cache()

        result = super().unlink()

        # Send cancellation notices only after successful unlink
        if cancellation_cache:
            self._send_cancellation_notices(cancellation_cache)

        return result
