{
    'name': 'IDX Odoo14 HRM Interview',
    'version': '1.0.0',
    'category': 'Human Resources/HRM',
    'summary': 'HRM system',
    'description': 'Personnel management',
    'depends': ['base'],

    'data': [
        'views/hr_overtime_statistics_record.xml',
        'wizard/hr_overtime_statistics.xml',

    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}