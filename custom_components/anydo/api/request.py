#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
anydo_api.request.

Helper functions for HTTP API calls.
Wrapped `requests` methods with default headers and options.
"""

import requests

from . import errors

__all__ = ('Request')

class Request():
    _SERVER_ERRORS = range(500, 600)

    def __init__(self, login):
        self._login = login
        self._session = None

    def _generate_session(self):
        self._session = requests.Session()
        self._login(self)

    def get(self, url, **options):
        """Simple GET request wrapper."""
        return self._base_request(method='get', url=url, **options)

    def post(self, url, **options):
        """Simple POST request wrapper."""
        return self._base_request(method='post', url=url, **options)

    def put(self, url, **options):
        """Simple PUT request wrapper."""
        return self._base_request(method='put', url=url, **options)

    def delete(self, url, **options):
        """Simple DELETE request wrapper."""
        return self._base_request(method='delete', url=url, **options)

    def _base_request(self, method, url, **options):
        """
        Base request wrapper.

        Make request according to the `method` passed, with default options applied.
        Forward other arguments into `request` object from the `request` library.
        """

        if self._session is None:
            self._generate_session()

        session_refreshed = options.pop('_session_refreshed') if '_session_refreshed' in options else False

        response_json = options.pop('response_json') if 'response_json' in options else True

        request_arguments = Request._prepare_request_arguments(**options)

        if method == 'get':
            adapter = requests.packages.urllib3.util.Retry(total=2, status_forcelist=Request._SERVER_ERRORS)

            self._session.mount('http://', requests.adapters.HTTPAdapter(max_retries=adapter))
            self._session.mount('https://', requests.adapters.HTTPAdapter(max_retries=adapter))

        response = getattr(self._session, method)(url, **request_arguments)
        self._session.close()

        try:
            Request._check_response_for_errors(response)
        except errors.UnauthorizedError as error:
            if session_refreshed:
                raise error
            self._session = self._generate_session()
            return self._base_request(method=method, url=method, _session_refreshed=True, **options)

        if response_json and method != 'delete':
            return response.json()

        return response

    @staticmethod
    def _prepare_request_arguments(**options):
        """Return a dict representing default request arguments."""
        options = options.copy()

        headers = {
            'Content-Type'   : 'application/json',
            'Accept'         : 'application/json',
            'Accept-Encoding': 'deflate',
        }

        params = options.pop('params') if 'params' in options else ''
        timeout = options.pop('timeout') if 'timeout' in options else 5 # don't hung the client to long

        if 'headers' in options:
            headers.update(options.pop('headers'))

        request_arguments = {
            'headers': headers,
            'params' : params,
            'timeout': timeout,
        }

        request_arguments.update(options)
        return request_arguments

    @staticmethod
    def _check_response_for_errors(response):
        """Raise and exception in case of HTTP error during API call, mapped to custom errors."""
        # bug in PyLint, seems not merged in 1.5.5 yet https://github.com/PyCQA/pylint/pull/742
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as error:
            if response.status_code == 400:
                client_error = errors.BadRequestError(response.content)
            elif response.status_code == 401:
                client_error = errors.UnauthorizedError(response.content)
            elif response.status_code == 409:
                client_error = errors.ConflictError(response.content)
            else:
                client_error = errors.InternalServerError(error)
            # should we skip original cause of exception or not?
            client_error.__cause__ = None
            raise client_error
