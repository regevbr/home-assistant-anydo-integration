#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
`anydo_api.label`.
`Label` class.
"""

from .constants import CONSTANTS
from .resource import Resource

__all__ = ('Label')

class Label(Resource):
    """
    `Tag` is the class representing user tag object
    It allows access of tag based objects
    """

    _endpoint = CONSTANTS.get('SYNC_URL')
    _reserved_attrs = ('user', 'data_dict', "is_dirty")

    def __init__(self, data_dict, user):
        "Constructor for Task"
        super(Label, self).__init__(data_dict)
        self.user = user

    def request(self):
        """Shortcut to retrive request session for requests."""
        return self.user.request()

    def tasks(self):
        """Return a list of the user tasks that belongs to selected label."""
        tasks = self.user.tasks()
        tasks = [task for task in tasks if task['labels'] is not None]
        return [task for task in tasks if self.id in task['labels']]