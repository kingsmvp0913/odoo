from odoo import api, fields, models, _
from dateutil.relativedelta import relativedelta
from datetime import date, datetime
from odoo.exceptions import UserError, AccessError
import pytz
from odoo.osv import expression
import vobject
from datetime import timedelta
import logging
import base64
_logger = logging.getLogger(__name__)
class CalendarEvent(models.Model):
    _inherit = 'calendar.event'

    def _domain_project_id(self):
        domain = [('allow_timesheets', '=', True)]
        if not self.user_has_groups('hr_timesheet.group_timesheet_manager'):
            return expression.AND([domain,
                ['|', ('privacy_visibility', '!=', 'followers'), ('allowed_internal_user_ids', 'in', self.env.user.ids)]
            ])
        return domain

    meeting_room = fields.Many2one('idx.calendar.meeting.room', string='會議室')
    meeting_room_name = fields.Char(related='meeting_room.description', string='會議室說明')
    meeting_url = fields.Char(string='會議連結')
    user_id = fields.Many2one(domain="[('active', '=', 'True')]")
    partner_ids = fields.Many2many(
        domain=[('active', '=', True), ('user_ids', '!=', False), ('user_ids.active', '!=', False)])
    color = fields.Integer(compute='_compute_color', readonly=True)
    calendar_filters = fields.Char(string='會議室或類別')
    calendar_end_time = fields.Char(string='會議結束時間', compute='_compute_calendar_end_time')
    is_chairperson = fields.Boolean(string='會議發起人', compute='_compute_is_chairperson')
    note = fields.Text(string='備註', compute='_compute_is_full_or_unavailable')
    timesheet_ids = fields.One2many('account.analytic.line', 'event_id', string="工時表")
    task_id = fields.Many2one('project.task', string='任務', domain="[('project_id.allow_timesheets', '=', True), ('project_id', '=?', project_id)]")
    project_id = fields.Many2one('project.project', string='專案', domain=_domain_project_id)

    def _get_ics_file(self):

            result = {}

            def ics_datetime(idate, allday=False):
                if idate:
                    if allday:
                        return idate
                    return idate.replace(tzinfo=pytz.timezone('UTC'))
                return False
                
            try:
                # FIXME: why isn't this in CalDAV?
                import vobject
            except ImportError:
                _logger.warning("The `vobject` Python module is not installed, so iCal file generation is unavailable. Please install the `vobject` Python module")
                return result

            for meeting in self:
                cal = vobject.iCalendar()
                # 改REQUEST後續才能修改，取消會議的時候會用到
                cal.add('method').value = 'REQUEST'
                event = cal.add('vevent')
                # 取消的時候序號要比原本大，因此固定0
                event.add('sequence').value = str(0)

                if not meeting.start or not meeting.stop:
                    raise UserError(_("First you have to specify the date of the invitation."))
                
                event.add('created').value = ics_datetime(fields.Datetime.now())
                event.add('dtstart').value = ics_datetime(meeting.start, meeting.allday)
                event.add('dtend').value = ics_datetime(meeting.stop, meeting.allday)
                event.add('summary').value = meeting.display_name 
                
                description = meeting.description or ""
                if meeting.meeting_url:
                    if description:
                        description += f"\n會議連結: {meeting.meeting_url}"
                    else:
                        description += f"會議連結: {meeting.meeting_url}"
                event.add('description').value = description

                if meeting.location:
                    event.add('location').value = meeting.location
                
                if meeting.rrule:
                    event.add('rrule').value = meeting.rrule

                if meeting.alarm_ids:
                    for alarm in meeting.alarm_ids:
                        valarm = event.add('valarm')
                        interval = alarm.interval
                        duration = alarm.duration
                        trigger = valarm.add('TRIGGER')
                        trigger.params['related'] = ["START"]
                        if interval == 'days':
                            delta = timedelta(days=duration)
                        elif interval == 'hours':
                            delta = timedelta(hours=duration)
                        elif interval == 'minutes':
                            delta = timedelta(minutes=duration)
                        trigger.value = delta
                        valarm.add('DESCRIPTION').value = alarm.name or u'Odoo'

                # Add attendees
                for attendee in meeting.attendee_ids:
                    attendee_add = event.add('attendee')
                    attendee_add.value = u'MAILTO:' + (attendee.email or u'')

                # Add organizer
                event.add('organizer').value = u'MAILTO:' + (meeting.user_id.email or u'')
                
                # Serialize calendar
                result[meeting.id] = cal.serialize().encode('utf-8')
                
                # 取代UID欄位，後續才能取消
                try:
                    import vobject
                    cal = vobject.readOne(result[meeting.id].decode('utf-8'))
                    if not cal.vevent.contents.get('uid'):
                        cal.vevent.add('uid').value = 'odoo-calendar-%d@%s' % (meeting.id, self._get_domain())
                    else:
                        cal.vevent.uid.value = 'odoo-calendar-%d@%s' % (meeting.id, self._get_domain())
                    result[meeting.id] = cal.serialize().encode('utf-8')
                except Exception:
                    _logger.warning(
                        "idx_notify_when_del_calendar: failed to inject UID into ICS for event %d",
                        meeting.id, exc_info=True,
                    )                

            return result    

    def copy(self, default=None):
        """ copy(default=None)

        Duplicate record ``self`` updating it with default values

        :param dict default: dictionary of field values to override in the
               original values of the copied record, e.g: ``{'field_name': overridden_value, ...}``
        :returns: new record

        """
        self.ensure_one()
        vals = self.with_context(active_test=False).copy_data(default)[0]

        # 複製的會議，負責人改為當下的使用者
        vals['user_id'] = self.env.user.id
        # 複製單據時，先繞過會議室時間重疊的控卡
        vals['copy'] = 'True'

        new = self.with_context(lang=None).create(vals).with_env(self.env)
        self.with_context(from_copy_translation=True).copy_translations(new, excluded=default or ())
        return new

    def _compute_color(self):
        for record in self:
            if record.meeting_room:
                record.color = record.meeting_room.color
            elif record.res_model == 'hr.leave':
                record.color = 12
            else:
                record.color = 7

    def _compute_calendar_end_time(self):
        for record in self:
            if record.meeting_room:
                if not record.allday:
                    record.calendar_end_time = str((record.stop + relativedelta(hours=+8)).hour).zfill(2) + ':' + (
                        str((record.stop + relativedelta(hours=+8)).minute)).zfill(2)
                else:
                    record.calendar_end_time = ''
            else:
                record.calendar_end_time = ''

    def _compute_is_chairperson(self):
        current_user_id = self.env.user
        for event in self:
            if current_user_id == event.user_id:
                event.is_chairperson = True
            else:
                event.is_chairperson = False

    @api.depends('partner_ids', 'start', 'duration', 'start_date', 'stop_date', 'allday', 'meeting_room')
    def _compute_is_full_or_unavailable(self):
        for event in self:
            warning_message = []
            if event.meeting_room.is_entity:
                if len(event.partner_ids) > event.meeting_room.limit:
                    warning_message.append('參會者人數超過會議室最多人數上限\n')
                attendee_event_info = ['下列參會者在此時段已有會議：']
                attendee_leave_info = ['下列參會者在此時段已休假：']
                for participant in event.partner_ids:
                    # 判斷目前會議的時段
                    if event.allday:
                        start_date = event.start_date
                        stop_date = event.stop_date
                        start_time = event.start_date + relativedelta(hours=00, minutes=00, seconds=00)
                        stop_time = event.stop_date + relativedelta(hours=23, minutes=59, seconds=59)
                        event_info = self.check_availability(event._origin.id, participant, start_date, stop_date)
                    else:
                        start_time = event.start
                        stop_time = event.stop
                        start_date = start_time.date()
                        stop_date = stop_time.date()
                        event_info = self.check_availability(event._origin.id, participant, start_time, stop_time)
                    if event_info['event']:
                        attendee_event_info.append(event_info['event'])
                    if event_info['leave']:
                        attendee_leave_info.append(event_info['leave'])
                text_block = ''
                if len(attendee_event_info) > 1:
                    warning_message.extend(attendee_event_info)
                if len(attendee_leave_info) > 1:
                    warning_message.extend(attendee_leave_info)
                for phrase in warning_message:
                    text_block += f'{phrase}\n'
                event.note = text_block
            else:
                event.note = ''
        return

    def name_get(self):
        res = []
        for event in self:
            display_name = event.name
            if event.meeting_room:
                display_name = '[' + event.meeting_room.room + ']' + event.name
            if event.res_model == 'hr.leave':
                leave_id = self.env['hr.leave'].sudo().search(
                    [('user_id', '=', event.user_id.id), ('date_from', '=', event.start), ('date_to', '=', event.stop),
                     ('state', '=', 'validate')], limit=1)
                if leave_id:
                    if 'is_act_name' not in self.env['hr.leave.type']._fields:
                        display_name = '[' + leave_id.holiday_status_id.name + ']' + event.name
                    else:
                        if leave_id.holiday_status_id.is_act_name:
                            display_name = '[' + leave_id.holiday_status_id.name + ']' + event.name
                        else:
                            display_name = '[休假]' + event.name
            res.append((event.id, display_name))
        return res

    @api.model_create_multi
    def create(self, vals_list):
        copy = False
        for val in vals_list:
            if 'copy' in val and val['copy'] == 'True':
                copy = True
                del val["copy"]

            # 複製單據時繞過檢查
            if copy:
                continue

            # 確認action是否有多傳參數，用來判斷可否在當前頁面新增會議
            flag = False
            params = self._context.get('default_no_create')
            # 判斷是否從"會議"頁面新增
            params2 = self._context.get('default_is_meeting')
            if params:
                flag = True

            # 休假審核建立的calendar.event
            check_data = self.default_get(['activity_ids', 'res_model_id', 'res_id', 'user_id', 'res_model', 'partner_ids'])
            if 'res_model' in check_data and check_data['res_model'] == 'hr.leave':
                val['calendar_filters'] = '休假'
                continue

            if params2 and not val['meeting_room']:
                raise UserError(_('「會議室」為必填欄位'))
            if 'meeting_room' in val and val['meeting_room']:
                # 確認是否從「日曆/日曆」點選進來並有選擇會議室
                if flag:
                    raise UserError(_('若要預約會議室的話，要到「會議」頁面申請'))
                room_id = self.env['idx.calendar.meeting.room'].search([('id', '=', val['meeting_room'])])
                val['calendar_filters'] = room_id.name
                # 確認此次更新需不需要檢查會議室衝突
                room_flag, start_date, stop_date, start_time, stop_time = self.is_check_meeting_time(val)
                # 確認會議起訖時間是否衝突
                if room_flag:
                    self.check_metting_room(val['meeting_room'], start_date, stop_date, start_time, stop_time)
        events = super(CalendarEvent, self).create(vals_list)
        for event in events:
            # 建立工時表
            self._event_timesheet(event)
        return events

    def write(self, vals):
        for rec in self:
            # 是否為會議
            if rec.meeting_room:
                if self.env.user != rec._origin.user_id:
                    raise AccessError(_('非會議負責人不可編輯會議：%s') % (rec.name,))
                # 確認此次更新需不需要檢查會議室衝突
                flag, start_date, stop_date, start_time, stop_time = rec.is_check_meeting_time(vals)
                # 確認會議起訖時間是否衝突
                if flag:
                    if 'meeting_room' in vals and vals['meeting_room']:
                        room = vals['meeting_room']
                    else:
                        room = rec.meeting_room.id
                    meeting_room = self.env['idx.calendar.meeting.room'].search([('id', '=', room)])
                    self.check_metting_room(room, start_date, stop_date, start_time, stop_time, rec.id)
                    # 避免write()段重複兩次，改用SQL更新資料
                    # self.calendar_filters = meeting_room.name
                    self.env.cr.execute(
                        "UPDATE calendar_event SET calendar_filters = '%s' WHERE id = '%s' " % (meeting_room.name, rec.id))

                #當參與者改變時，應刪除原先參與者的工時
                new_partner_ids = vals.get('partner_ids')
                if new_partner_ids:
                    for partner_id in self.partner_ids:
                        if partner_id.id not in new_partner_ids[0][2]:
                            users = self.env['res.users'].search([('partner_id', '=', partner_id.id)])
                            self.env['account.analytic.line'].search([('event_id', '=', self.id),('user_id', '=', users.id)]).sudo().unlink()

        event = super(CalendarEvent, self).write(vals)
        # 建立工時表
        self._event_timesheet()
        return event

    # 確認此次更新需不需要檢查會議室衝突
    def is_check_meeting_time(self, vals):
        flag = False
        start_date = ''
        stop_date = ''
        start_time = ''
        stop_time = ''
        if 'start_date' in vals or 'stop_date' in vals or 'start' in vals or \
           'stop' in vals or 'allday' in vals or 'duration' in vals or 'meeting_room' in vals:
            flag = True
            if ('allday' in vals and vals['allday']) or ('allday' not in vals and self.allday):
                start_date, stop_date, start_time, stop_time = self._allday_compute_time(vals)
            else:
                start_date, stop_date, start_time, stop_time = self._not_allday_compute_time(vals)
        return flag, start_date, stop_date, start_time, stop_time

    # 會議為整天
    def _allday_compute_time(self, vals):
        start_date = self.start_date
        stop_date = self.stop_date
        for val in vals:
            if val == 'start_date':
                start_date = datetime.strptime(vals['start_date'], '%Y-%m-%d')
            if val == 'stop_date':
                stop_date = datetime.strptime(vals['stop_date'], '%Y-%m-%d')
        start_time = start_date + relativedelta(hours=00, minutes=00, seconds=00)
        stop_time = stop_date + relativedelta(hours=23, minutes=59, seconds=59)
        return start_date, stop_date, start_time, stop_time

    # 會議非整天
    def _not_allday_compute_time(self, vals):
        start_time = self.start
        stop_time = self.stop
        for val in vals:
            if val == 'start':
                if isinstance(vals['start'], str):
                    start_time = datetime.strptime(vals['start'], '%Y-%m-%d %H:%M:%S')
                else:
                    start_time = vals['start']
            if val == 'stop':
                if isinstance(vals['stop'], str):
                    stop_time = datetime.strptime(vals['stop'], '%Y-%m-%d %H:%M:%S')
                else:
                    stop_time = vals['stop']
        start_date = start_time.date()
        stop_date = stop_time.date()
        return start_date, stop_date, start_time, stop_time

    # 取得domain，產生ICS的UID時使用domain區分
    def _get_domain(self):
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        domain = base_url.replace('https://', '').replace('http://', '').split(':')[0]
        return domain
    # 產生取消會議ICS
    def _get_cancel_ics_bytes(self, event):
        try:
            import vobject
        except ImportError:
            _logger.warning("vobject not installed; ICS CANCEL attachment skipped.")
            return None

        def ics_datetime(idate, allday=False):
            if idate:
                if allday:
                    return idate
                return idate.replace(tzinfo=pytz.timezone('UTC'))
            return False

        cal = vobject.iCalendar()
        cal.add('method').value = 'CANCEL'
        vevent = cal.add('vevent')
        vevent.add('status').value = 'CANCELLED'
        vevent.add('sequence').value = str(1)
        vevent.add('uid').value = 'odoo-calendar-%d@%s' % (event.id, self._get_domain())
        vevent.add('summary').value = event.name or ''
        now = ics_datetime(fields.Datetime.now())
        vevent.add('dtstamp').value = now
        vevent.add('created').value = now
        if event.start:
            vevent.add('dtstart').value = ics_datetime(event.start, event.allday)
        if event.stop:
            vevent.add('dtend').value = ics_datetime(event.stop, event.allday)
        if event.location:
            vevent.add('location').value = event.location
        if event.user_id and event.user_id.email:
            vevent.add('organizer').value = u'MAILTO:' + event.user_id.email
        for attendee in event.attendee_ids:
            email = attendee.email or (attendee.partner_id.email if attendee.partner_id else '')
            at = vevent.add('attendee')
            at.value = u'MAILTO:' + (email or u'')
        return cal.serialize().encode('utf-8')

    # 產生會議取消通知內容
    def _prepare_cancellation_mails(self):
        template = self.env.ref(
            'idx_notify_when_del_calendar.email_template_meeting_cancelled',
            raise_if_not_found=False,
        )
        if not template:
            _logger.warning(
                "idx_notify_when_del_calendar: template 'email_template_meeting_cancelled' not found."
            )
            return []

        mail_ids = []
        for event in self:
            # 排除休假類型
            if event.res_model == 'hr.leave':
                continue

            ics_bytes = self._get_cancel_ics_bytes(event)
            # 綁 mail.message 而非 calendar.event，防止 event 刪除後 GC 清掉附件
            ics_attachment_id = None
            if ics_bytes:
                ics_attachment_id = self.env['ir.attachment'].sudo().create({
                    'name': 'cancel.ics',
                    'datas': base64.b64encode(ics_bytes).decode('utf-8'),
                    'mimetype': 'text/calendar; charset="utf-8"; method=CANCEL',
                    'res_model': 'mail.message',
                    'res_id': 0,
                }).id

            for attendee in event.attendee_ids:
                # 排除自己本身（比對 partner_id）
                if attendee.partner_id and attendee.partner_id.id == self.env.user.partner_id.id:
                    continue
                # 已拒絕的參與者不發送取消通知
                if attendee.state == 'declined':
                    continue
                email = attendee.email or (attendee.partner_id.email if attendee.partner_id else False)
                if not email:
                    _logger.warning(
                        "calendar.event %s (id=%d): attendee %s (id=%d) has no email, skipping.",
                        event.name, event.id,
                        attendee.partner_id.name if attendee.partner_id else attendee.common_name,
                        attendee.id,
                    )
                    continue

                email_values = {}
                if ics_attachment_id:
                    email_values['attachment_ids'] = [(4, ics_attachment_id)]

                try:
                    mail_id = template.send_mail(
                        attendee.id,
                        force_send=False,
                        email_values=email_values,
                    )
                    mail_ids.append(mail_id)
                except Exception:
                    _logger.warning(
                        "calendar.event (id=%d): failed to prepare cancellation mail for %s",
                        event.id, email, exc_info=True,
                    )

        return mail_ids

    def unlink(self):
        # 產生會議取消通知內容
        mail_ids = self._prepare_cancellation_mails()
        
        # 檢驗是否為會議負責人
        if self.meeting_room:
            if self._origin.user_id:
                if self.env.user != self._origin.user_id:
                    raise AccessError(_('非會議負責人不可刪除會議：%s') % (self.name,))
            # 刪除工時表
            self._remove_timesheet_record()
        result = super(CalendarEvent, self).unlink()
        
        # 發送會議取消通知
        if mail_ids:
            self.env['mail.mail'].sudo().browse(mail_ids or []).write({'state': 'outgoing'})
        
        return result

    # 確認相同會議室的起迄時間是否有衝突
    def check_metting_room(self, meeting_room, start_date, stop_date, start_time, stop_time, id=False):
        room_id = self.env['idx.calendar.meeting.room'].search([('id', '=', meeting_room)])
        if room_id.is_entity:
            allday_event = self.env['calendar.event'].search(
                [('id', '!=', id), ('meeting_room', '=', meeting_room), ('allday', '=', True),
                 '|', '|', '|',
                 '&', ('start_date', '<', start_date), ('stop_date', '>', start_date),
                 '&', ('start_date', '<', stop_date), ('stop_date', '>', stop_date),
                 '&', ('start_date', '<=', start_date), ('stop_date', '>=', stop_date),
                 '&', ('start_date', '>=', start_date), ('stop_date', '<=', stop_date)],
                limit=1)
            # 撈非整天的會議(依起訖時間為條件)
            event = self.env['calendar.event'].search(
                [('id', '!=', id), ('meeting_room', '=', meeting_room), ('allday', '=', False),
                 '|', '|', '|',
                 '&', ('start', '<', start_time), ('stop', '>', start_time),
                 '&', ('start', '<', stop_time), ('stop', '>', stop_time),
                 '&', ('start', '<=', start_time), ('stop', '>=', stop_time),
                 '&', ('start', '>=', start_time), ('stop', '<=', stop_time),
                 ],
                limit=1)
            if allday_event or event:
                metting_room = self.env['idx.calendar.meeting.room'].search([('id', '=', meeting_room)]).name
                raise UserError(_('[%s]您要預約的會議時間與其他會議重疊，請先確認後再重新預約') % (metting_room))

    # 確認同一時段是否有會議或請假
    def check_availability(self, id, participant, start, stop):
        conflict = {'event': '', 'leave': ''}
        allday_events = self.env['calendar.event'].search(
            [('id', '!=', id),
             ('partner_ids.id', '=', participant._origin.id),
             ('meeting_room', '!=', False),
             ('allday', '=', True),
             '|', '|', '|',
             '&', ('start_date', '<', start), ('stop_date', '>', start),
             '&', ('start_date', '<', stop), ('stop_date', '>', stop),
             '&', ('start_date', '<=', start), ('stop_date', '>=', stop),
             '&', ('start_date', '>=', start), ('stop_date', '<=', stop)])
        # 撈非整天的會議(依起訖時間為條件)
        events = self.env['calendar.event'].search(
            [('id', '!=', id),
             ('partner_ids.id', '=', participant._origin.id),
             ('meeting_room', '!=', False),
             ('allday', '=', False),
             '|', '|', '|',
             '&', ('start', '<', start), ('stop', '>', start),
             '&', ('start', '<', stop), ('stop', '>', stop),
             '&', ('start', '<=', start), ('stop', '>=', stop),
             '&', ('start', '>=', start), ('stop', '<=', stop),
             ])

        # 撈休假(依起訖時間為條件)
        leaves = self.env['calendar.event'].sudo().search(
            [('id', '!=', id),
             ('partner_ids.id', '=', participant._origin.id),
             ('res_model', '=', 'hr.leave'),
             ('allday', '=', False),
             '|', '|', '|',
             '&', ('start', '<', start), ('stop', '>', start),
             '&', ('start', '<', stop), ('stop', '>', stop),
             '&', ('start', '<=', start), ('stop', '>=', stop),
             '&', ('start', '>=', start), ('stop', '<=', stop),
             ])
        if allday_events:
            for allday_event in allday_events:
                start_time = allday_event.start_date + relativedelta(hours=00, minutes=00, seconds=00)
                stop_time = allday_event.stop_date + relativedelta(hours=23, minutes=59, seconds=59)
                start_time = start_time.strftime('%Y-%m-%d %H:%M:%S')
                conflict['event'] += f'{participant.name} {start_time} ~ {stop_time}\n'

        if events:
            for event in events:
                start_time = event.start.astimezone(pytz.timezone("Asia/Taipei")).strftime('%Y-%m-%d %H:%M:%S')
                stop_time = event.stop.astimezone(pytz.timezone("Asia/Taipei")).strftime('%Y-%m-%d %H:%M:%S')
                conflict['event'] += f'{participant.name} {start_time} ~ {stop_time}\n'
        if leaves:
            for leave in leaves:
                leave_id = self.env['hr.leave'].sudo().search(
                    [('user_id', '=', leave.user_id.id), ('date_from', '=', leave.start),
                     ('date_to', '=', leave.stop), ('state', '=', 'validate')], limit=1)
                if leave_id:
                    start_time = leave_id.date_from.astimezone(pytz.timezone("Asia/Taipei")).strftime('%Y-%m-%d %H:%M:%S')
                    stop_time = leave_id.date_to.astimezone(pytz.timezone("Asia/Taipei")).strftime('%Y-%m-%d %H:%M:%S')
                    conflict['leave'] += f'{participant.name} {leave_id.holiday_status_id.name} {start_time} ~ {stop_time}\n'

        return conflict

    def _event_timesheet(self, event=False):
        if event:
            self = event

        setting = self.env['ir.config_parameter'].sudo()
        module_project_timesheet_event = setting.get_param('module_project_timesheet_event')
        if module_project_timesheet_event:
            event_timesheet_project_id = int(setting.get_param('event_timesheet_project_id'))
            event_timesheet_task_id = int(setting.get_param('event_timesheet_task_id'))
            for rec in self:
                # 休假建立的會議
                if rec.res_model == 'hr.leave':
                    continue
                if rec.project_id:
                    event_timesheet_project_id = rec.project_id.id
                    event_timesheet_task_id = rec.task_id.id
                rec._timesheet_create_event(event_timesheet_project_id, event_timesheet_task_id)
        return

    def _timesheet_create_event(self, event_timesheet_project_id, event_timesheet_task_id):
        tz_time = relativedelta(hours=8)
        start = self.start + tz_time
        duration = 0

        start_date = start.date()
        if not self.allday:
            duration = self.duration
        else:
            duration = 8

        for rec in self.partner_ids:
            user_id = self.env['res.users'].search([('partner_id', '=', rec.id)])
            employee_id = self.env['hr.employee'].search([('user_id', '=', user_id.id)])
            account_analytic_id = self.env['account.analytic.line'].sudo().search(
                [('event_id', '=', self.id), ('employee_id', '=', employee_id.id)])
            if account_analytic_id:
                self._event_timesheet_prepare_line_values(rec, event_timesheet_project_id, event_timesheet_task_id, start_date, duration, True, account_analytic_id)
            else:
                self._event_timesheet_prepare_line_values(rec, event_timesheet_project_id, event_timesheet_task_id,
                                                          start_date, duration)
        return

    # 建立或修改timesheet資料
    def _event_timesheet_prepare_line_values(self, rec, project_id, task_id, date, unit_amount, flag=False, account_analytic_id=False):
        self.ensure_one()
        user_id = self.env['res.users'].search([('partner_id', '=', rec.id)])
        employee_id = self.env['hr.employee'].search([('user_id', '=', user_id.id)])
        project_id = self.env['project.project'].search([('id', '=', project_id)])
        res = {
            'name': "%s" % (self.name),
            'project_id': project_id.id,
            'task_id': task_id,
            'account_id': project_id.analytic_account_id.id,
            'unit_amount': unit_amount,
            'user_id': user_id.id,
            'date': date,
            'event_id': self.id,
            'employee_id': employee_id.id,
            'company_id': employee_id.company_id.id}
        if flag:
            account_analytic_id.write(res)
        else:
            rec.env['account.analytic.line'].sudo().create(res)
        return

    # 刪除會議時一起刪除工時表
    def _remove_timesheet_record(self):
        timesheets = self.sudo().mapped('timesheet_ids')
        timesheets.unlink()
        return

    @api.onchange('project_id')
    def onchange_project_id(self):
        if self.project_id:
            self.task_id = ''