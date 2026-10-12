# -*- coding: utf-8 -*-

import logging
import pprint
import werkzeug

from odoo import fields, http, _
from odoo.exceptions import ValidationError
from odoo.http import request

_logger = logging.getLogger(__name__)


class EnZonaController(http.Controller):
    _return_url = '/payment/en_zona/return'
    _cancel_url = '/payment/en_zona/cancel'

    def _get_actual_tx(self, **post):
        return request.env['payment.transaction'].sudo().search([('ez_tx_id', '=', post.get('transaction_uuid'))])

    def en_zona_validate_return(self,**post):
        try:
            tx = self._get_actual_tx(**post)
            tx._set_enzona_tx_complete(post.get('transaction_uuid'))
        except ValidationError as e:
            _logger.exception('Unable to validate the En Zona payment, %s' % (e.name))
            tx._set_transaction_error(e.name)

    def en_zona_validate_cancel(self, **post):
        try:
            tx = self._get_actual_tx(**post)
            tx._set_transaction_cancel()
        except ValidationError as e:
            _logger.exception('Unable to validate the En Zona payment, %s' % (e.name))
            tx._set_transaction_error(e.name)

    @http.route(['/payment/en_zona/return'], type='http', auth='public', csrf=False)
    def en_zona_return(self, **kwargs):
        transaction_uuid = kwargs.get('transaction_uuid')  # Ej: "209d82df2b3f4ede8ca1c2a9bea67db5"
        user_uuid = kwargs.get('user_uuid')  # Ej: "3e8c4fc4515f4ed784f63d65c4b0039e"

        _logger.info(f"Transaction UUID: {transaction_uuid}, User UUID: {user_uuid}")
        _logger.warning('Beginning En Zona confirmation process with post data %s', pprint.pformat(kwargs))  # debug
        self.en_zona_validate_return(**kwargs)
        return werkzeug.utils.redirect('/shop/confirmation')

    @http.route(['/payment/en_zona/cancel'], type='http', auth='public', csrf=False)
    def en_zona_cancel(self, **kwargs):
        _logger.warning('Beginning En Zona cancel process with post data %s', pprint.pformat(kwargs))  # debug
        self.en_zona_validate_cancel(**kwargs)
        return werkzeug.utils.redirect('/shop/confirmation')

    @http.route(['/payment/en_zona/redirect'], type='http', auth='public', csrf=False)
    def en_zona_redirect(self, **kwargs):
        _logger.warning('Redirecting to En Zona Confirmation Link')  # debug
        tx = request.env['payment.transaction'].sudo().search([('reference', '=', kwargs['reference'])])
        ez_redirect_link = tx.ez_redirect_link
        return werkzeug.utils.redirect(ez_redirect_link)