# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'En Zona Payment Acquirer Template',
    'version': '1.0',
    "author": "Empresa de Aplicaciones Informáticas(DESOFT)",
    'website': 'https://www.desoft.cu',
    "contact": 'soporte@cmw.desoft.cu',
    'category': 'Website',
    'summary': 'Template to display QR code when payment acquirer is En Zona',
    'description': "",
    'depends': ['website_sale', 'l10n_cu_payment_en_zona'],
    'data': [
        'views/templates.xml',
        'views/sale_order.xml',
    ],
    'demo': [],
    'installable': True,
    # 'auto_install': True,
}
