# coding: utf-8

import json
import logging
import requests
import base64

from odoo import api, fields, models, _
from datetime import datetime, timedelta
from odoo.http import request
from odoo.exceptions import ValidationError
from odoo.addons.l10n_cu_payment_en_zona.controllers.main import EnZonaController
from requests.exceptions import HTTPError
from werkzeug import urls

# proxies = {"http": "http://arlette.castellanos:NatiAli2020-10@162.0.0.17:3128",
#            "https": "https://arlette.castellanos:NatiAli2020-10@162.0.0.17:3128"}

proxies = {"http": None,
           "https": None}

_logger = logging.getLogger(__name__)


class ProviderEnZona(models.Model):
    _inherit = 'payment.provider'

    code = fields.Selection(selection_add=[('en_zona', 'En Zona')], ondelete={'en_zona': 'set default'})
    en_zona_consumer_secret = fields.Char(groups='base.group_user')
    en_zona_consumer_key = fields.Char(groups='base.group_user')
    en_zona_access_token = fields.Char(readonly=True, groups='base.group_user')
    en_zona_expiration_date = fields.Datetime(readonly=True, groups='base.group_user')

    @api.onchange('state')
    def _onchange_state(self):
        self.en_zona_consumer_secret = False
        self.en_zona_consumer_key = False
        self.en_zona_access_token = False
        self.en_zona_expiration_date = False

    def get_base64(self, text):
        return str(base64.b64encode(bytes(text, "utf-8"))).__str__()

    def en_zona_token_action(self):
        do_action = self.env.context.get('do_action', False)
        consumer_secret = self.sudo().en_zona_consumer_secret
        consumer_key = self.sudo().en_zona_consumer_key
        if consumer_secret and consumer_key:
            bs4 = self.get_base64(consumer_key + ":" + consumer_secret)
            url = ''
            if self.state == 'enabled':
                url = 'https://api.enzona.net'
            elif self.state == 'test':
                url = 'https://apisandbox.enzona.net'
            else:
                raise ValidationError(_('Payment method disabled!'))
            url = url + '/token'
            s = 'Basic ' + bs4.split("'")[1]
            headers = {
                "AUTHORIZATION": s,
            }
            if do_action == 'to_get':
                data = {
                    "grant_type": "client_credentials",
                    "scope": "enzona_business_payment"
                }
            else:
                data = {
                    "grant_type": "client_credentials",
                    "scope": "enzona_business_payment"
                }
                # data = {
                #     "grant_type": "refresh_token",
                #     "refresh_token": self.en_zona_access_token
                # }
                # headers.update({"Accept": "application/json"})
            resp = requests.request(method='POST', url=url, data=data, headers=headers, proxies=proxies, verify=False)
            try:
                resp.raise_for_status()
            except HTTPError:
                _logger.error(resp.text)
                raise ValidationError(resp.reason)
            response_json = resp.json()
            expiration_date = datetime.now() + timedelta(seconds=response_json['expires_in'])
            self.write({'en_zona_access_token': response_json['access_token']})
            self.write({'en_zona_expiration_date': expiration_date})
        else:
            raise ValidationError('Please introduce consumer secret and consumer key first')

    def _validate_credentials(self):
        if self.en_zona_access_token:
            temp_date = datetime.today()
            if self.en_zona_expiration_date < temp_date:
                self.with_context({'do_action': 'to_refresh'}).en_zona_token_action()
        elif not self.en_zona_consumer_key or not self.en_zona_consumer_secret:
            raise ValidationError(_('Missing credentials, please check them out!'))
        else:
            raise ValidationError(_('Missing token, please check it out!'))

    def _get_feature_support(self):
        res = super(ProviderEnZona, self)._get_feature_support()
        res['authorize'].append('en_zona')
        return res

    def _en_zona_request(self, url, data=False, method='POST', headers=False, verify =False):
        # self.ensure_one()
        self._validate_credentials()
        if not headers:
            headers = {
                "AUTHORIZATION": "Bearer %s" % self.sudo().en_zona_access_token,
                "content-type": "application/json; charset=UTF-8",
            }
        resp = requests.request(method, url, data=data, headers=headers, proxies=proxies, verify=verify)
        if not resp.ok and not (400 <= resp.status_code < 500 and resp.json().get('error', {}).get('code')):
            try:
                resp.raise_for_status()
            except HTTPError:
                _logger.error(resp.text)
                var1 = resp.json().get('fault', {}).get('message', '')
                var2 = resp.json().get('fault', {}).get('description', '')
                var3 = resp.json().get('error', {}).get('message', '')
                en_zona_error = var1 + " " + var2 + " " + var3
                error_msg = " " + (_(en_zona_error))
                raise ValidationError(error_msg)
        return resp.json()

    @api.model
    def _get_en_zona_urls(self, state):
        """ En Zona URLS """
        en_zona_form_url = False
        if state == 'enabled':
            en_zona_form_url = 'https://api.enzona.net/payment/v1.0.0/payments'
        elif state == 'test':
            en_zona_form_url = 'https://apisandbox.enzona.net/payment/v1.0.0/payments'
        else:
            raise ValidationError(_('Payment method disabled!'))
        return en_zona_form_url

    def en_zona_get_form_action_url(self):
        self.ensure_one()
        if self.code == 'en_zona':
            return '/payment/en_zona/redirect'


class TxEnZona(models.Model):
    _inherit = 'payment.transaction'

    ez_tx_id = fields.Text(string='En Zona Transaction ID')
    ez_redirect_link = fields.Text(string='Redirect link')

    def _get_specific_rendering_values(self, processing_values):
        """ Override of payment to return Paypal-specific rendering values.

        Note: self.ensure_one() from `_get_processing_values`

        :param dict processing_values: The generic and specific processing values of the transaction
        :return: The dict of provider-specific processing values
        :rtype: dict
        """
        res = super()._get_specific_rendering_values(processing_values)
        if self.provider_code != 'en_zona':
            return res
        data  = self._send_pay_order_enzona()
        rendering_values = {
            'api_url': data,
        }
        return rendering_values


    # --------------------------------------------------
    # FORM RELATED METHODS
    # --------------------------------------------------
    @api.model
    def _en_zona_form_get_tx_from_data(self, data):
        ez_tx_id = data.get('transaction_uuid')
        if ez_tx_id:
            tx = self.env['payment.transaction'].search([('ez_tx_id', '=', ez_tx_id)])
            if not tx or len(tx) > 1:
                error_msg = 'En Zona: received data for transaction_uuid %s' % (ez_tx_id)
                if not tx:
                    error_msg += '; no order found'
                else:
                    error_msg += '; multiple order found'
                _logger.exception(error_msg)
                raise ValidationError(error_msg)
        else:
            error_msg = _('En Zona: received data with missing transaction_uuid (%s)') % (ez_tx_id)
            _logger.exception(error_msg)
            raise ValidationError(error_msg)
        return tx

    def _en_zona_form_validate(self, data):
        status = data.get('status_code')
        status_denom = data.get('status_denom')
        date = fields.Datetime.now()
        msg = 'Validation error occurred. %s, %s' %(status, status_denom)
        res = {
            'ez_tx_id': data.get('transaction_uuid'),
        }
        if status == 1111:  # Accepted (Completed) Transaction from En Zona
            msg = 'Validated En Zona payment for tx %s: set as done' % (self.reference)
            self._set_transaction_done()
            self._post_process_after_done()
            _logger.warning(msg)
            res.update(date=date, state_message=msg)
            self.write(res)
            return True

        if status == 1112:  # Canceled by platform or by the user Transaction from En Zona
            msg = 'Received canceled status for En Zona payment %s: %s, set as canceled' % (
                self.reference, status_denom)
            res.update(date=date, state_message=msg)
            _logger.warning(msg)
            self.write(res)
            return True

        _logger.warning(msg)
        self._set_transaction_error(msg)
        return False

    def _en_zona_get_tx_values(self):
        base_url = self.provider_id.get_base_url()
        sale_order = request.website.sale_get_order()

        # defining a params dict for the parameters to be sent to the API
        en_zona_tx_values = {
            'description': 'Venta de productos',
            'currency': 'CUP',
            'amount': {
                'total': "%.2f" % self.amount,
                'details': {
                    'shipping': "%.2f" % float(0),
                    'tax': "%.2f" % float(sale_order.amount_tax),
                    'discount': "%.2f" % float(0),
                    'tip': "%.2f" % float(0)
                }},
            'items': [{'name': 'Producto',
                       'description': 'Venta de productos',
                       'quantity': 1,
                       'price': "%.2f" % self.amount,
                       'tax': "%.2f" % float(0)}],
            "merchant_uuid": "1698acee117a4a13b6d914842ded9bb9",
            'merchant_op_id': str(sale_order.id).zfill(12),
            'invoice_number': sale_order.id,
            'return_url': urls.url_join(base_url, EnZonaController._return_url),
            'cancel_url': urls.url_join(base_url, EnZonaController._cancel_url),
            'terminal_id': "",
            'buyer_identity_code': ""
        }
        return en_zona_tx_values

    def _send_pay_order_enzona(self):
        en_zona_tx_values = self._en_zona_get_tx_values()
        try:
            url = self.provider_id._get_en_zona_urls(self.provider_id.state or 'enabled')
            data = json.dumps(en_zona_tx_values)
            req = self.provider_id._en_zona_request(url, data, verify=False)
        except requests.exceptions.RequestException as err:
            _logger.error(str(err))
            raise ValidationError(err)
        else:
            status_code = req['status_code']
            status_denom = req['status_denom']
            if status_code == 1113:  # Pending transaction status code
                values = {}
                ez_tx_id = req['transaction_uuid']
                response_links = req['links']
                for links in response_links:
                    if links['rel'] == 'confirm':
                        redirect_link = links['href']
                self.sudo().write({'ez_tx_id': ez_tx_id,
                               # 'state': 'authorized',
                               'ez_redirect_link': redirect_link})
                return redirect_link
            else:
                raise ValidationError(status_denom)

    def _get_to_use_url(self,transaction_uuid):  # Conforming the url to use for requesting any transaction details from En Zona
        base_url = self.provider_id._get_en_zona_urls(self.provider_id.state or 'enabled')
        to_use_url = base_url + '/' + transaction_uuid
        return to_use_url

    def _get_data_to_send(self):
        data = {}
        return data

    def _get_status_from_request(self,transaction_uuid):  # method for requesting transaction details from En Zona API Get
        to_use_url = self._get_to_use_url(transaction_uuid)
        data = self._get_data_to_send()
        response = self.provider_id._en_zona_request(to_use_url, method='GET', data=data)
        status_code = response['status_code']
        status_denom = response['status_denom']
        _logger.warning('En Zona: The transaction status is (%s)' % status_denom)  # debug
        return status_code, status_denom

    def _set_enzona_tx_complete(self,transaction_uuid):
        status_code, status_denom = self._get_status_from_request(transaction_uuid)
        if status_code == 1116:  # Confirmed Transaction from En Zona
            to_use_url = self._get_to_use_url(transaction_uuid) + '/complete'
            response = self.provider_id._en_zona_request(to_use_url, data={})
            self.sudo()._handle_notification_data('en_zona', response['status_denom'])
        elif status_code == 1111:
            response = {
                'status_code': status_code,
                'status_denom': status_denom
            }
            self.sudo()._handle_notification_data('en_zona', response['status_denom'])
        else:  # Another Transaction Failed cause from En Zona
            _logger.warning('En Zona: Another En Zona answer')
            self._set_transaction_error('En Zona: %s, %s' % (status_code, status_denom))

    def _set_transaction_cancel(self):
        status_code, status_denom = self._get_status_from_request()
        if status_code:
            if status_code in (1113, 1116):  # Pending to be Canceled or canceled by abandoned car
                to_use_url = self._get_to_use_url() + '/cancel'
                response = self.provider_id._en_zona_request(to_use_url, data={})
                res = self.sudo()._handle_notification_data('en_zona', response['status_denom'])
                if res:  # In case the form feedback return False
                    super(TxEnZona, self)._set_transaction_cancel()
            else:  # Failed Transaction from En Zona
                _logger.warning('En Zona: answered INVALID/FAIL on data verification')
                self._set_transaction_error('En Zona: %s, %s' % (status_code, status_denom))