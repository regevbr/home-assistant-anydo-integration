#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
anydo_api.client.

`Client` class.
"""

from .request import Request
from .constants import CONSTANTS
from .user import User

__all__ = ('Client')

class Client(object):
    """
    `Client` is the interface for communication with an API.

    Responsible for authentication and session management.
    """

    def __init__(self, email, password):
        """Constructor for Client."""
        self.email = email
        self.password = password
        self.user = None
        self._request = None

    def get_user(self, refresh=False):
        """Return a user object currently logged in."""
        if self._request is None:
            self._request = Request(self.__log_in)

        if not self.user or refresh:
            data = self._request.get(
                url=CONSTANTS.get('ME_URL')
            )

            data.update({'password': self.password})
            self.user = User(data_dict=data, request=self._request)

        return self.user

    def __log_in(self, request):
        """
        Authentication base on `email` and `password`.

        Return an actual session, used internally for all following requests to API.
        """
        credentials = {
            'j_username': self.email,
            'j_password': self.password,
            '_spring_security_remember_me': 'on'
        }

        headers = {'Content-Type': 'application/x-www-form-urlencoded'}

        request.post(
            url=CONSTANTS.get('LOGIN_URL'),
            headers=headers,
            data=credentials,
            response_json=False
        )

