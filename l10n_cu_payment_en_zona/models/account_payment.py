# coding: utf-8

import json
import logging
import requests

from odoo import api, fields, models, _
from datetime import date
from odoo.exceptions import ValidationError
_logger = logging.getLogger(__name__)
MAP_INVOICE_TYPE_PARTNER_TYPE = {
    'out_invoice': 'customer',
    'out_refund': 'customer',
    'out_receipt': 'customer',
    'in_invoice': 'supplier',
    'in_refund': 'supplier',
    'in_receipt': 'supplier',
}


class AccountMoveEnZona(models.Model):
    _inherit = 'account.move'

    payment_with_en_zona = fields.Boolean('Payment with En Zona', compute='_compute_payment_with_en_zona')

    def action_en_zona_invoice_register_payment(self):
        for move in self:
            for tx in move.reversed_entry_id.transaction_ids:
                if tx.provider_id.code == 'en_zona' and tx.state == 'done':
                    url = tx._get_to_use_url() + "/refund"
                    data = {
                        'amount': {
                            'total': "%.2f" % move.amount_total,
                        },
                        'description': "Devolución de productos"
                    }
                    try:
                        req = tx.provider_id._en_zona_request(url, json.dumps(data))
                    except requests.exceptions.RequestException as err:
                        _logger.error(str(err))
                        raise ValidationError(err)
                    if req['transaction_status_code'] == '1111':  # refund accepted code from En Zona
                        _logger.warning('Refund Transaction accepted by En Zona')
                        payment = self.env['account.payment'].create(move._prepare_payment_vals())
                        payment.post()
                    else:
                        raise ValidationError(req['transaction_denom'])

    def _prepare_payment_vals(self):
        '''Create the payment values.
        :return: The payment values as a dictionary.
        '''
        amount = self.env['account.payment']._compute_payment_amount(self, self.currency_id, self.journal_id, date
                                                                     .today())
        values = {
            'journal_id': self.journal_id.id,
            'payment_method_id': 3,
            'payment_date': date.today(),
            'communication': " ".join(self.invoice_payment_ref or self.ref or self.name),
            'invoice_ids': [(6, 0, [self.id])],
            'payment_type': ('inbound' if amount > 0 else 'outbound'),
            'amount': abs(amount),
            'currency_id': self.currency_id.id,
            'partner_id': self.commercial_partner_id.id,
            'partner_type': MAP_INVOICE_TYPE_PARTNER_TYPE[self.type],
        }
        return values

    def _compute_payment_with_en_zona(self):
        for rec in self:
            rec.payment_with_en_zona = False
            if rec.type == 'out_refund':
                if rec.reversed_entry_id.transaction_ids.filtered(lambda tx: tx.state == 'done' and tx.ez_tx_id):
                    rec.payment_with_en_zona = True