# -*- coding: utf-8 -*-

import logging

from odoo import api, fields, models, _
_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _inherit = 'sale.order'
    order_in_process = fields.Boolean('Orden en proceso')

    def _create_payment_transaction(self, vals):
        if self.transaction_ids:
            for tx in self.transaction_ids:
                if tx.ez_tx_id:
                    status_code, status_denom, transaction_uuid, merchant_op_id = tx.sudo()._get_status_from_request()
                    if status_code == 1111:
                        tx._set_enzona_tx_complete()
                        return False
                    elif tx.state == 'authorized':
                        tx._set_transaction_cancel()

        transaction = super(SaleOrder, self)._create_payment_transaction(vals)
        if transaction.provider_id.provider == 'en_zona':
            transaction._send_pay_order_enzona()
        return transaction

    def action_cancel(self):
        for order in self:
            if order.order_in_process:
                if order.state != 'cancel':
                    if order.transaction_ids:
                        for tx in order.transaction_ids:
                            if tx.ez_tx_id:
                                status_code, status_denom, transaction_uuid, merchant_op_id = tx.sudo()._get_status_from_request()
                                if status_code == 1111:
                                    tx._set_enzona_tx_complete()
                                    return False
            return super(SaleOrder, self).action_cancel()