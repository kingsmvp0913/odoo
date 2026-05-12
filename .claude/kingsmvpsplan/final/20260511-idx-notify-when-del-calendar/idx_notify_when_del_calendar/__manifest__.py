# -*- coding: utf-8 -*-
{
    'name': 'IDX Notify When Delete Calendar',
    'version': '14.0.1.0.0',
    'category': 'Calendar',
    'summary': 'Send cancellation email to attendees when a calendar event is deleted',
    'description': """
        When a calendar.event is deleted (and it is not an hr.leave event),
        automatically send a cancellation email with ICS CANCEL attachment
        to all attendees whose state != 'declined'.
    """,
    'author': 'IDX',
    'depends': ['calendar'],
    'data': [
        'security/ir.model.access.csv',
        'data/mail_template_data.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
    'license': 'LGPL-3',
}
