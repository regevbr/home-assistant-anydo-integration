"""Support for Any.do task management (https://www.any.do/)."""
from __future__ import annotations

from datetime import datetime, timedelta
import logging

import voluptuous as vol

from homeassistant.components.calendar import PLATFORM_SCHEMA, CalendarEventDevice
from homeassistant.const import CONF_ID, CONF_NAME, CONF_USERNAME, CONF_PASSWORD
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.template import DATE_STR_FORMAT
from homeassistant.util import dt

from .api.client import Client
from .api.task import Task

from .const import (
    ALL_DAY,
    ALL_TASKS,
    COMPLETED,
    CONF_EXTRA_LISTS,
    CONF_LIST_DUE_DATE,
    CONF_LIST_TAG_WHITELIST,
    CONF_LIST_WHITELIST,
    CONTENT,
    DATETIME,
    DESCRIPTION,
    DOMAIN,
    DUE_DATE,
    DUE_TODAY,
    END,
    ID,
    LIST_ID,
    LIST_NAME,
    NAME,
    NOTES,
    OVERDUE,
    OWNER,
    SERVICE_NEW_TASK,
    START,
    SUMMARY,
    TAGS,
)

_LOGGER = logging.getLogger(__name__)

NEW_TASK_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required(CONTENT): cv.string,
        vol.Optional(NOTES): cv.string,
        vol.Optional(LIST_NAME): vol.All(cv.string),
        vol.Optional(TAGS): cv.ensure_list_csv,
        vol.Optional(OWNER): cv.string,
        vol.Exclusive(DUE_DATE, "due_date"): cv.string,
    }
)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_EXTRA_LISTS, default=[]): vol.All(
            cv.ensure_list,
            vol.Schema(
                [
                    vol.Schema(
                        {
                            vol.Required(CONF_NAME): cv.string,
                            vol.Optional(CONF_LIST_DUE_DATE): vol.Coerce(int),
                            vol.Optional(CONF_LIST_WHITELIST, default=[]): vol.All(
                                cv.ensure_list, [vol.All(cv.string)]
                            ),
                            vol.Optional(
                                CONF_LIST_TAG_WHITELIST, default=[]
                            ): vol.All(cv.ensure_list, [vol.All(cv.string)]),
                        }
                    )
                ]
            ),
        ),
    }
)

SCAN_INTERVAL = timedelta(minutes=15)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Any.do platform."""
    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)

    # Look up IDs based on (lowercase) names.
    list_id_lookup = {}
    tag_id_lookup = {}

    api = Client(email=username, password=password)
    user = api.get_user()

    # Setup devices:
    # Grab all lists.
    lists = user.categories()

    # Grab all tags
    tags = user.labels()

    # Add all Any.do defined lists.
    list_devices = []
    for list in lists:
        # List is an object, not a dict!
        # Because of that, we convert what we need to a dict.
        list_data = {CONF_NAME: list[NAME], CONF_ID: list[ID]}
        list_devices.append(AnydoListDevice(list_data, tags, api))
        # Cache the names so we can easily look up name->ID.
        list_id_lookup[list[NAME].lower()] = list[ID]

    # Cache all tag names
    for tag in tags:
        tag_id_lookup[tag[NAME].lower()] = tag[ID]

    # Check config for more lists.
    extra_lists = config[CONF_EXTRA_LISTS]
    for list in extra_lists:
        # Special filter: By date
        list_due_date = list.get(CONF_LIST_DUE_DATE)

        # Special filter: By tag
        tag_filter = list[CONF_LIST_TAG_WHITELIST]

        # Special filter: By name
        # Names must be converted into IDs.
        list_name_filter = list[CONF_LIST_WHITELIST]
        list_id_filter = [
            list_id_lookup[list_name.lower()]
            for list_name in list_name_filter
        ]

        # Create the custom list and add it to the devices array.
        list_devices.append(
            AnydoListDevice(
                list,
                tags,
                api,
                list_due_date,
                tag_filter,
                list_id_filter,
            )
        )

    for device in list_devices:
        device.update()

    add_entities(list_devices)

    def handle_new_task(call):
        """Call when a user creates a new Any.do Task from Home Assistant."""
        list_name = call.data[LIST_NAME]
        list_id = list_id_lookup[list_name.lower()]

        args = {
            'user': api.get_user(),
            'title': call.data[CONTENT],
            'categoryId': list_id,
            'repeatingMethod': 'TASK_REPEAT_OFF',
        }

        if NOTES in call.data:
            args['note'] = call.data[NOTES]

        if TAGS in call.data:
            args['labels'] = [tag_id_lookup[tag.lower()] for tag in call.data[TAGS]]

        if OWNER in call.data:
            args['assignedTo'] = call.data[OWNER]

        if DUE_DATE in call.data:
            due_date = dt.parse_datetime(call.data[DUE_DATE])
            if due_date is None:
                due = dt.parse_date(call.data[DUE_DATE])
                due_date = datetime(due.year, due.month, due.day)
            # Format it in the manner Any.do expects
            due_date = dt.as_utc(due_date)
            args['dueDate'] = int(datetime.timestamp(due_date) * 1000)
            args['alert'] = {
                "type": "OFFSET",
                "offset": 0,
                "customTime": 0,
                "repeatEndType": "REPEAT_END_NEVER",
            }

        # Create the task
        Task.create(**args)

        _LOGGER.debug("Created Any.do task: %s", call.data[CONTENT])

    hass.services.register(
        DOMAIN, SERVICE_NEW_TASK, handle_new_task, schema=NEW_TASK_SERVICE_SCHEMA
    )


def _parse_due_date(timestamp) -> datetime | None:
    """Parse the due date dict into a datetime object."""
    if timestamp == 0:
        return None
    return datetime.fromtimestamp(timestamp / 1000, dt.UTC)


class AnydoListDevice(CalendarEventDevice):
    """A device for getting the next Task from a Any.do list."""

    def __init__(
        self,
        data,
        tags,
        api,
        due_date_days=None,
        whitelisted_tags=None,
        whitelisted_lists=None,
    ):
        """Create the Any.do Calendar Event Device."""
        self.data = AnydoListData(
            data,
            tags,
            api,
            due_date_days,
            whitelisted_tags,
            whitelisted_lists,
        )
        self._cal_data = {}
        self._name = data[CONF_NAME]

    @property
    def event(self):
        """Return the next upcoming event."""
        return self.data.event

    @property
    def name(self):
        """Return the name of the entity."""
        return self._name

    def update(self):
        """Update all Any.do Calendars."""
        self.data.update()
        # Set Any.do-specific data that can't easily be grabbed
        self._cal_data[ALL_TASKS] = [
            task[SUMMARY] for task in self.data.all_list_tasks
        ]

    async def async_get_events(self, hass, start_date, end_date):
        """Get all events in a specific time frame."""
        return await self.data.async_get_events(hass, start_date, end_date)

    @property
    def extra_state_attributes(self):
        """Return the device state attributes."""
        if self.data.event is None:
            # No tasks, we don't REALLY need to show anything.
            return None

        return {
            DUE_TODAY: self.data.event[DUE_TODAY],
            OVERDUE: self.data.event[OVERDUE],
            ALL_TASKS: self._cal_data[ALL_TASKS],
            TAGS: self.data.event[TAGS],
            OWNER: self.data.event[OWNER],
            NOTES: self.data.event[NOTES],
        }


class AnydoListData:
    """
    Class used by the Task Device service object to hold all Any.do Tasks.

    This is analogous to the GoogleCalendarData found in the Google Calendar
    component.

    Takes an object with a 'name' field and optionally an 'id' field (either
    user-defined or from the Any.do API), a Any.do API token, and an optional
    integer specifying the latest number of days from now a task can be due (7
    means everything due in the next week, 0 means today, etc.).

    This object has an exposed 'event' property (used by the Calendar platform
    to determine the next calendar event) and an exposed 'update' method (used
    by the Calendar platform to poll for new calendar events).

    The 'event' is a representation of a Any.do Task, with defined parameters
    of 'due_today' (is the task due today?), 'all_day' (does the task have a
    due date?), 'task_tags' (all tags assigned to the task), 'message'
    (the content of the task, e.g. 'Fetch Mail'), 'description' (a URL pointing
    to the task on the Any.do website), 'end_time' (what time the event is
    due), 'start_time' (what time this event was last updated), 'overdue' (is
    the task past its due date?), and 'all_tasks' (all tasks in this
    list, sorted by how important they are).

    'offset_reached', 'location', and 'friendly_name' are defined by the
    platform itself, but are not used by this component at all.

    The 'update' method polls the Any.do API for new lists/tasks, as well
    as any updates to current lists/tasks. This occurs every SCAN_INTERVAL minutes.
    """

    def __init__(
        self,
        list_data,
        tags,
        api,
        due_date_days=None,
        whitelisted_tags=None,
        whitelisted_lists=None,
    ):
        """Initialize an Any.do list."""
        self.event = None

        self._api = api
        self._name = list_data[CONF_NAME]
        # If no ID is defined, fetch all tasks.
        self._id = list_data.get(CONF_ID)

        # All tags the user has defined, for easy lookup.
        self._tags = tags
        # Not tracked: order, indent, comment_count.

        self.all_list_tasks = []

        # The days a task can be due (for making lists of everything
        # due today, or everything due in the next week, for example).
        if due_date_days is not None:
            self._due_date_days = timedelta(days=due_date_days)
        else:
            self._due_date_days = None

        # Only tasks with one of these tags will be included.
        if whitelisted_tags is not None:
            self._tag_whitelist = whitelisted_tags
        else:
            self._tag_whitelist = []

        # This list includes only lists with these names.
        if whitelisted_lists is not None:
            self._list_id_whitelist = whitelisted_lists
        else:
            self._list_id_whitelist = []

    def create_anydo_task(self, data):
        """
        Create a dictionary based on a Task passed from the Any.do API.

        Will return 'None' if the task is to be filtered out.
        """
        task = {}
        # Fields are required to be in all returned task objects.
        task[SUMMARY] = data["title"]
        task[NOTES] = data["note"]
        task[OWNER] = data["assignedTo"]
        task[COMPLETED] = data["status"] == "CHECKED"
        task[DESCRIPTION] = f"https://desktop.any.do/agenda/tasks/{data[ID]}"

        # All task tags (optional parameter).
        if data["labels"]:
            task[TAGS] = [
                tag[NAME].lower() for tag in self._tags if tag[ID] in data["labels"]
            ]
        else:
            task[TAGS] = []

        if self._tag_whitelist and (
            not any(tag in task[TAGS] for tag in self._tag_whitelist)
        ):
            # We're not on the whitelist, return invalid task.
            return None

        # Due dates (optional parameter).
        # The due date is the END date -- the task cannot be completed
        # past this time.
        # That means that the START date is the earliest time one can
        # complete the task.
        # Generally speaking, that means right now.
        task[START] = dt.utcnow()
        if data["dueDate"] and data["dueDate"] != 0:
            task[END] = _parse_due_date(data["dueDate"])

            if self._due_date_days is not None and (
                task[END] > dt.utcnow() + self._due_date_days
            ):
                # This task is out of range of our due date;
                # it shouldn't be counted.
                return None

            task[DUE_TODAY] = task[END].date() == datetime.today().date()

            # Special case: Task is overdue.
            if task[END] <= task[START]:
                task[OVERDUE] = True
                # Set end time to the current time plus 1 hour.
                # We're pretty much guaranteed to update within that 1 hour,
                # so it should be fine.
                task[END] = task[START] + timedelta(hours=1)
            else:
                task[OVERDUE] = False
        else:
            # If we ask for everything due before a certain date, don't count
            # things which have no due dates.
            if self._due_date_days is not None:
                return None

            # Define values for tasks without due dates
            task[END] = None
            task[ALL_DAY] = True
            task[DUE_TODAY] = False
            task[OVERDUE] = False

        # Not tracked: id, comments, list_id order, indent, recurring.
        return task

    @staticmethod
    def select_best_task(list_tasks):
        """
        Search through a list of events for the "best" event to select.

        The "best" event is determined by the following criteria:
          * A proposed event must not be completed
          * A proposed event must have an end date (otherwise we go with
            the event at index 0, selected above)
          * A proposed event must be on the same day or earlier as our
            current event
          * If a proposed event is an earlier day than what we have so
            far, select it
          * If a proposed event is on the same day as our current event,
            select it
          * If a proposed event is on the same day as our current event,
            but is due earlier in the day, select it
        """
        # Start at the end of the list, so if tasks don't have a due date
        # the newest ones are the most important.

        event = list_tasks[-1]

        for proposed_event in list_tasks:
            if event == proposed_event:
                continue

            if proposed_event[COMPLETED]:
                # Event is complete!
                continue

            if proposed_event[END] is None:
                # No end time:
                if event[END] is None:
                    # They also have no end time,
                    event = proposed_event
                continue

            if event[END] is None:
                # We have an end time, they do not.
                event = proposed_event
                continue

            if proposed_event[END].date() > event[END].date():
                # Event is too late.
                continue

            if proposed_event[END].date() < event[END].date():
                # Event is earlier than current, select it.
                event = proposed_event
                continue

            if proposed_event[END] < event[END]:
                event = proposed_event
                continue

        return event

    async def async_get_events(self, hass, start_date, end_date):
        """Get all tasks in a specific time frame."""

        def get_list_task_data():
            user = self._api.get_user()

            if self._id is None:
                return [
                    task
                    for task in user.tasks()
                    if not self._list_id_whitelist
                       or task[LIST_ID] in self._list_id_whitelist
                ]
            else:
                return [task for task in user.tasks() if task[LIST_ID] == self._id]

        list_task_data = await hass.async_add_executor_job(get_list_task_data)

        events = []
        for task in list_task_data:
            if not task["dueDate"] or task["dueDate"] == 0:
                continue
            due_date = _parse_due_date(task["dueDate"])
            if not due_date:
                continue
            midnight = dt.as_utc(
                dt.parse_datetime(
                    due_date.strftime("%Y-%m-%d")
                    + "T00:00:00Z"
                )
            )

            if start_date < due_date < end_date:
                if due_date == midnight:
                    # If the due date has no time data, return just the date so that it
                    # will render correctly as an all day event on a calendar.
                    due_date_value = due_date.strftime("%Y-%m-%d")
                else:
                    due_date_value = due_date.isoformat()
                event = {
                    "uid": task["id"],
                    "title": task["title"],
                    "start": due_date_value,
                    "end": due_date_value,
                    "allDay": True,
                    "summary": task["title"],
                }
                events.append(event)
        return events

    def update(self):
        """Get the latest data."""
        user = self._api.get_user(refresh=True)
        if self._id is None:
            list_task_data = [
                task
                for task in user.tasks()
                if not self._list_id_whitelist
                or task[LIST_ID] in self._list_id_whitelist
            ]
        else:
            list_task_data = [task for task in user.tasks() if task[LIST_ID] == self._id]

        # If we have no data, we can just return right away.
        if not list_task_data:
            _LOGGER.debug("No data for %s", self._name)
            self.event = None
            return

        # Keep an updated list of all tasks in this list.
        list_tasks = []

        for task in list_task_data:
            anydo_task = self.create_anydo_task(task)
            if anydo_task is not None:
                # A None task means it is invalid for this list
                list_tasks.append(anydo_task)

        if not list_tasks:
            # We had no valid tasks
            _LOGGER.debug("No valid tasks for %s", self._name)
            self.event = None
            return

        # Make sure the task collection is reset to prevent an
        # infinite collection repeating the same tasks
        self.all_list_tasks.clear()

        # Organize the best tasks (so users can see all the tasks
        # they have, organized)
        while list_tasks:
            best_task = self.select_best_task(list_tasks)
            _LOGGER.debug("Found Any.do Task: %s", best_task[SUMMARY])
            list_tasks.remove(best_task)
            self.all_list_tasks.append(best_task)

        self.event = self.all_list_tasks[0]

        # Convert datetime to a string again
        if self.event is not None:
            if self.event[START] is not None:
                self.event[START] = {
                    DATETIME: self.event[START].strftime(DATE_STR_FORMAT)
                }
            if self.event[END] is not None:
                self.event[END] = {DATETIME: self.event[END].strftime(DATE_STR_FORMAT)}
            else:
                # Home Assistant gets cranky if a calendar event never ends
                # Let's set our "due date" to tomorrow
                self.event[END] = {
                    DATETIME: (datetime.utcnow() + timedelta(days=1)).strftime(
                        DATE_STR_FORMAT
                    )
                }
        _LOGGER.debug("Updated %s", self._name)
