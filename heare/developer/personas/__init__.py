"""
Personas for the developer agent.

A persona consists of:
1. A system prompt
2. A set of tools (by name)

Personas are implemented as partials of the subagent run_agent method,
combined with the tool annotation.
"""

# Basic persona tools - commonly used across most personas
BASIC_TOOLS = [
    "read_file",
    "write_file",
    "list_directory",
    "run_bash_command",
    "edit_file",
    "web_search",
    "python_repl",
    "agent",
]

# Import specific personas
from .basic_agent import basic_agent  # noqa: E402
from .deep_research_agent import deep_research_agent  # noqa: E402
from .coding_agent import coding_agent  # noqa: E402

# List of all available personas
__all__ = ["basic_agent", "deep_research_agent", "coding_agent"]
