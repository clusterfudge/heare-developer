"""
Basic Agent persona.

Using connected datasources (like mail, calendar, web search, and internal knowledge),
answer questions and take action on behalf of the user.
"""

from heare.developer.context import AgentContext
from heare.developer.tools.framework import tool
from heare.developer.tools.subagent import run_agent

# Tools available to the basic agent
BASIC_AGENT_TOOLS = [
    "read_file",
    "write_file",
    "list_directory",
    "run_bash_command",
    "edit_file",
    "web_search",
    "safe_curl",
    "python_repl",
    "agent",
]

# System prompt for the basic agent
BASIC_AGENT_SYSTEM_PROMPT = """
You are a helpful assistant that can answer questions and take actions on behalf of the user.
You have access to various tools that allow you to interact with the user's environment,
search the web, and process information.

When answering questions:
- Use available tools to gather information needed to provide accurate responses
- Break complex tasks into manageable steps
- Provide clear, concise explanations
- When appropriate, show your work and reasoning

When taking actions:
- Confirm what actions you're taking and why
- Be transparent about what you're doing
- When using tools that modify the environment (like writing files), be cautious and confirm
  intentions when appropriate

Always aim to be helpful, accurate, and respectful of the user's time and resources.
"""


@tool
def basic_agent(context: AgentContext, prompt: str):
    """
    Basic Agent: Answer questions and take action on behalf of the user using connected
    data sources like web search and local files.

    This agent can:
    - Search the web for information
    - Access and manipulate files
    - Run basic commands
    - Process information using Python
    - Answer questions based on available information

    Args:
        prompt: The question or request from the user
    """
    return run_agent(
        context=context,
        prompt=prompt,
        tool_names=BASIC_AGENT_TOOLS,
        system=BASIC_AGENT_SYSTEM_PROMPT,
    )
