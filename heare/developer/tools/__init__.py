from .subagent import agent
from .files import read_file, write_file, list_directory, edit_file
from .repl import run_bash_command, python_repl
from .web import web_search, safe_curl

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
]


try:
    from heare.developer.clients.plane_so import get_project_from_config
    from heare.developer.tools.issues import PLANE_TOOLS

    project = get_project_from_config()
    if project:
        ALL_TOOLS += PLANE_TOOLS
except Exception:
    pass
