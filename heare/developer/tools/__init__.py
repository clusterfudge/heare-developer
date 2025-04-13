from .subagent import agent
from .files import read_file, write_file, list_directory, edit_file
from .repl import run_bash_command, python_repl
from .web import web_search, safe_curl
from .gcal import (
    calendar_setup,
    calendar_list_events,
    calendar_create_event,
    calendar_delete_event,
    calendar_search,
    calendar_list_calendars,
)
from .gmail import (
    gmail_search,
    gmail_read,
    gmail_send,
    gmail_read_thread,
    find_emails_needing_response,
)

ALL_TOOLS = [
    read_file,
    write_file,
    list_directory,
    run_bash_command,
    edit_file,
    web_search,
    agent,
    safe_curl,
    python_repl,
    gmail_search,
    gmail_read,
    gmail_send,
    gmail_read_thread,
    find_emails_needing_response,
    calendar_list_events,
    calendar_create_event,
    calendar_delete_event,
    calendar_search,
    calendar_setup,
    calendar_list_calendars,
]


try:
    from heare.developer.clients.plane_so import get_project_from_config
    from heare.developer.tools.issues import PLANE_TOOLS

    project = get_project_from_config()
    if project:
        ALL_TOOLS += PLANE_TOOLS
except Exception:
    pass

# try:
#     from ..personas import basic_agent, coding_agent, deep_research_agent
#
#     ALL_TOOLS += [basic_agent, coding_agent, deep_research_agent]
# except Exception as e:
#     print(f"Error importing personas: {repr(e)}")
