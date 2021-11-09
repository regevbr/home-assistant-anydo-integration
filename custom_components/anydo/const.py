"""Constants for the Any.do component."""
CONF_EXTRA_LISTS = "custom_lists"
CONF_LIST_DUE_DATE = "due_date_days"
CONF_LIST_TAG_WHITELIST = "tags"
CONF_LIST_WHITELIST = "include_lists"

# Calendar Platform: Does this calendar event last all day?
ALL_DAY = "all_day"
# Attribute: All tasks in this list
ALL_TASKS = "all_tasks"
# Any.do API: "Completed" flag -- 1 if complete, else 0
CHECKED = "checked"
# Attribute: Is this task complete?
COMPLETED = "completed"
# Any.do API: What is this task about?
# Service Call: What is this task about?
CONTENT = "content"
# Any.do API: What is this task notes?
# Service Call: What is this task notes?
NOTES = "notes"
# Any.do API: What is this task owner?
# Service Call: What is this task owner?
OWNER = "owner"
# Calendar Platform: Get a calendar event's description
DESCRIPTION = "description"
# Calendar Platform: Used in the '_get_date()' method
DATETIME = "dateTime"
DUE = "due"
# Attribute: When is this task due?
# Service Call: When is this task due?
DUE_DATE = "due_date"
# Service Call: When should user be reminded of this task?
REMINDER_DATE = "reminder_date"
# Attribute: Is this task due today?
DUE_TODAY = "due_today"
# Calendar Platform: When a calendar event ends
END = "end"
# Any.do API: Look up a List/Tag/Task ID
ID = "id"
# Any.do API: Fetch all tags
# Service Call: What are the tag attached to this task?
TAGS = "tags"
# Any.do API: "Name" value
NAME = "name"
# Attribute: Is this task overdue?
OVERDUE = "overdue"
# Any.do API: Look up the list ID a Task belongs to
LIST_ID = "list_id"
# Service Call: What list do you want a Task added to?
LIST_NAME = "list"
# Any.do API: Fetch all lists
LISTS = "lists"
# Calendar Platform: When does a calendar event start?
START = "start"
# Calendar Platform: What is the next calendar event about?
SUMMARY = "summary"
# Any.do API: Fetch all Tasks
TASKS = "items"

DOMAIN = "anydo"

SERVICE_NEW_TASK = "new_task"
