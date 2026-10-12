# -*- coding: utf-8 -*-

{
    'name': 'En Zona Payment Acquirer',
    'category': 'Accounting',
    'summary': 'Payment Acquirer: En Zona Implementation',
    'version': '1.0',
    'description': """En Zona Payment Acquirer""",
    'depends': ['payment'],
    'data': [
        'views/payment_views.xml',
        'views/account_move_views.xml',
        'views/payment_enzona_templates.xml',
        'data/payment_acquirer_data.xml',
    ],
    'installable': True,
}
