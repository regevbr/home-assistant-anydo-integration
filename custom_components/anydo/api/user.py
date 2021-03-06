#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
`anydo_api.user`.

`User` class.
"""

from . import errors
from .category import Category
from .constants import CONSTANTS
from .resource import Resource
from .task import Task
from .label import Label

__all__ = ('User')

class User(Resource):
    """
    `User` is the class representing User object.

    It wraps user-related JSON into class instances and
    responsible for user management.
    """

    _endpoint = CONSTANTS.get('ME_URL')
    _reserved_attrs = ('data_dict', 'request_obj', 'is_dirty')
    __alternate_endpoint = CONSTANTS.get('USER_URL')

    def __init__(self, data_dict, request):
        """Constructor for User."""
        super(User, self).__init__(data_dict)
        self.request_obj = request
        self.categories_list = None
        self.tasks_list = None
        self._pending_tasks = None
        self.labels_list = None

    def save(self, alternate_endpoint=None):
        """
        Push updated attributes to the server.

        If nothing was changed we don't hit the API.
        """
        super(User, self).save(alternate_endpoint=self.get_endpoint())

    def request(self):
        """Shortcut to retrieve object request for requests."""
        return self.request_obj

    def destroy(self, alternate_endpoint=None):
        """
        Hit the API to destroy the user.

        Pass a changed alternate endpoint as it is different from the class one.
        """
        super(User, self).destroy(alternate_endpoint=self.__alternate_endpoint)

    delete = destroy

    def refresh(self, alternate_endpoint=None):
        """
        Reload resource data from remote API.

        Pass a changed alternate endpoint as it is different from the class one.
        """
        super(User, self).refresh(alternate_endpoint=self.get_endpoint())

    # pylint: disable=too-many-arguments
    def tasks(self,
              refresh=False,
              include_deleted=False,
              include_done=False,
              include_checked=True,
              include_unchecked=True):
        """Return a remote or cached task list for user."""
        if not self.tasks_list or refresh:
            params = {
                'includeDeleted': str(include_deleted).lower(),
                'includeDone': str(include_done).lower(),
            }

            tasks_data = self.request().get(
                url=CONSTANTS.get('TASKS_URL'),
                params=params
            )

            self.tasks_list = [Task(data_dict=task, user=self) for task in tasks_data]

        return Task.filter_tasks(self.tasks_list,
                                 include_deleted=include_deleted,
                                 include_done=include_done,
                                 include_checked=include_checked,
                                 include_unchecked=include_unchecked)

    def categories(self, refresh=False, include_deleted=False):
        """Return a remote or cached categories list for user."""
        if not self.categories_list or refresh:
            params = {
                'includeDeleted': str(include_deleted).lower(),
            }

            categories_data = self.request().get(
                url=CONSTANTS.get('CATEGORIES_URL'),
                params=params
            )

            self.categories_list = [
                Category(data_dict=category, user=self) for category in categories_data
            ]

        result = self.categories_list
        if not include_deleted:
            result = [cat for cat in result if not cat['isDeleted']]

        return result

    def labels(self, refresh=False, include_deleted=False):
        """Return a remote or cached labels list for user."""
        if not self.labels_list or refresh:
            params = {
                'includeDeleted': str(include_deleted).lower(),
            }

            payload = {
                "models": {"label": {
                        "items": [],
                        "config": {
                            "includeDone": "false",
                            "includeDeleted": str(include_deleted).lower()
                        }
                }}
            }

            labels_data = self.request().post(
                url=CONSTANTS.get('SYNC_URL'),
                params=params,
                json=payload
            )['models']['label']['items']
            self.labels_list = [
                Label(data_dict=label, user=self) for label in labels_data
            ]

        result = self.labels_list
        if not include_deleted:
            result = [label for label in result if not label['isDeleted']]

        return result

    def add_task(self, task):
        """Add new task into internal storage."""
        if not self.tasks_list:
            self.tasks()
        if self.tasks_list:
            self.tasks_list.append(task)
        else:
            self.tasks_list = [task]

    def add_category(self, category):
        """Add new category into internal storage."""
        if self.categories_list:
            self.categories_list.append(category)
        else:
            self.categories_list = [category]

    def default_category(self):
        """Return default category for user if exist."""
        return next((cat for cat in self.categories() if cat.isDefault), None)

    def pending_tasks(self, refresh=False):
        """
        Return a list of dicts representing a pending task that was shared with current user.

        Empty list otherwise.
        """
        if not self._pending_tasks or refresh:
            response_obj = self.request().get(
                url=self.get_endpoint() + '/pending'
            )

            self._pending_tasks = response_obj['pendingTasks']

        return self._pending_tasks or []

    def pending_tasks_ids(self, refresh=False):
        """
        Return a list of pending tasks ids shared with user.

        Empty list otherwise.
        """
        return [task['id'] for task in self.pending_tasks(refresh=refresh)]

    def approve_pending_task(self, pending_task_id=None, pending_task=None):
        """
        Approve pending task via API call.

        Accept pending_task_id or pending_task dict (in format of pending_tasks.
        """
        task_id = pending_task_id or pending_task['id']
        if not task_id:
            raise errors.ModelAttributeError(
                'Eather :pending_task_id or :pending_task argument is required.'
            )

        response_obj = self.request().post(
            url=self.get_endpoint() + '/pending/' + task_id + '/accept'
        )

        return response_obj

    @staticmethod
    def required_attributes():
        """
        Return a set of required fields for valid user creation.

        This tuple is checked to prevent unnecessary API calls.
        """
        return {'name', 'email', 'password'}
