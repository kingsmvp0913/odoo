{
    'name': 'IDX Custom Invoice Export',
    'summary': 'inherit account',
    'description': '發票匯出財政部csv格式',
    'author': 'Ideaxpress',
    'version': '13.0.0.2',
    'website': 'https://ideaxpress.biz',
    'category': 'IDX',
    'depends': ['account', 'web'],
    'data': [
        'data/server_action.xml',
        'views/assets.xml',
    ],
    'qweb': [
        'static/src/xml/export_invo_csv.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}
