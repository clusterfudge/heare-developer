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
    from heare.developer.tools.issues import PLANE_TOOLS

    ALL_TOOLS.extend(PLANE_TOOLS)
except ImportError:
    # If there's an error importing the Plane tools, just continue without them
    pass
