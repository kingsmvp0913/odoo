{
    'name': 'IDX Odoo14 calendar',
    'version': '1.0',
    'category': 'Productivity/Calendar',
    'summary': '',
    'description': '',
    'depends': ['base', 'calendar', 'hr_timesheet'],

    'data': [
        'security/security.xml',

        'data/mail_data.xml',

        'views/meeting_room.xml',
        'views/calendar_event.xml',
        'views/calendar_views.xml',
        'views/view_action.xml',
        'views/view_menu.xml',
        'views/calendar_templates.xml',
        'views/res_config_settings_views.xml',

        'security/ir.model.access.csv',
        
        'data/cancel_mail_template.xml', 
    ],

    'qweb': [
        "static/src/xml/idx_calendar.xml",
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}
