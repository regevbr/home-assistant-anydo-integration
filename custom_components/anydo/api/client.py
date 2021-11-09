#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
anydo_api.client.

`Client` class.
"""

import requests

from . import request
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

    def get_user(self, refresh=False):
        """Return a user object currently logged in."""
        if not self.user or refresh:
            session = self.__log_in()
            data = request.get(
                url=CONSTANTS.get('ME_URL'),
                session=session
            )

            data.update({'password': self.password})
            self.user = User(data_dict=data, session=session)

        return self.user

    def __log_in(self):
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
        session = requests.Session()

        request.post(
            url=CONSTANTS.get('LOGIN_URL'),
            session=session,
            headers=headers,
            data=credentials,
            response_json=False
        )

        return session

