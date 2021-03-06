from __future__ import print_function

import json
import logging

from .stream import MarketStream, OrderStream


class BaseListener(object):

    def __init__(self):
        self.market_stream = None
        self.order_stream = None

    def register_stream(self, unique_id, operation):
        if operation == 'authentication':
            logging.info('[Listener: %s]: %s' % (unique_id, operation))

        elif operation == 'marketSubscription':
            if self.market_stream is not None:
                logging.warning('[Listener: %s]: marketSubscription stream already registered, replacing data' %
                                unique_id)
            self.market_stream = self._add_stream(unique_id, operation)

        elif operation == 'orderSubscription':
            if self.order_stream is not None:
                logging.warning('[Listener: %s]: orderSubscription stream already registered, replacing data' %
                                unique_id)
            self.order_stream = self._add_stream(unique_id, operation)

    def on_data(self, raw_data):
        print(raw_data)

    def _add_stream(self, unique_id, operation):
        print('Register: %s %s' % (operation, unique_id))

    def __str__(self):
        return '<BaseListener>'

    def __repr__(self):
        return str(self)


class StreamListener(BaseListener):
    """Stream listener, processes results from socket,
    holds a market and order stream which hold
    market_book caches
    """

    def __init__(self, output_queue=None):
        super(StreamListener, self).__init__()
        self.output_queue = output_queue

    def on_data(self, raw_data):
        """Called when raw data is received from connection.
        Override this method if you wish to manually handle
        the stream data

        :param raw_data: Received raw data
        :return: Return False to stop stream and close connection
        """
        try:
            data = json.loads(raw_data)
        except ValueError:
            logging.error('value error: %s' % raw_data)
            return
        unique_id = data.get('id')

        if self._error_handler(data, unique_id):
            return False

        operation = data.get('op')
        if operation == 'connection':
            self._on_connection(data, unique_id)
        elif operation == 'status':
            self._on_status(data, unique_id)
        elif operation == 'mcm' or operation == 'ocm':
            self._on_change_message(data, unique_id)

    def _on_connection(self, data, unique_id):
        """Called on collection operation

        :param data: Received data
        """
        self.connection_id = data.get('connectionId')
        logging.info('[Connect: %s]: connection_id: %s' % (unique_id, self.connection_id))

    @staticmethod
    def _on_status(data, unique_id):
        """Called on status operation

        :param data: Received data
        """
        status_code = data.get('statusCode')
        logging.info('[Subscription: %s]: %s' % (unique_id, status_code))

    def _on_change_message(self, data, unique_id):
        change_type = data.get('ct', 'UPDATE')
        operation = data.get('op')

        if operation == 'mcm':
            stream = self.market_stream
        else:
            stream = self.order_stream

        logging.debug('[Subscription: %s]: %s: %s' % (unique_id, change_type, data))

        if change_type == 'SUB_IMAGE':
            stream.on_subscribe(data)
        elif change_type == 'RESUB_DELTA':
            stream.on_resubscribe(data)
        elif change_type == 'HEARTBEAT':
            stream.on_heartbeat(data)
        elif change_type == 'UPDATE':
            stream.on_update(data)

    def _add_stream(self, unique_id, stream_type):
        if stream_type == 'marketSubscription':
            return MarketStream(unique_id, self.output_queue)
        elif stream_type == 'orderSubscription':
            return OrderStream(unique_id, self.output_queue)

    @staticmethod
    def _error_handler(data, unique_id):
        """Called when data first received

        :param data: Received data
        :param unique_id: Unique id
        :return: True if error present
        """
        status_code = data.get('statusCode')
        connection_closed = data.get('connectionClosed')
        if status_code == 'FAILURE':
            logging.error('[Subscription: %s] %s: %s' %
                          (unique_id, data.get('errorCode'), data.get('errorMessage')))
            if connection_closed:
                return True

    def __str__(self):
        return '<StreamListener>'
