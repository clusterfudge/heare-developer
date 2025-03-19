"""
Deep Research Agent persona.

Using local information (from the file system), connected datasources (like mail, calendar, google drive),
and external data sources (web search), construct a detailed research artifact.
"""

from heare.developer.context import AgentContext
from heare.developer.tools.framework import tool
from heare.developer.tools.subagent import run_agent

# Tools available to the deep research agent
DEEP_RESEARCH_TOOLS = [
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

# System prompt for the deep research agent
DEEP_RESEARCH_SYSTEM_PROMPT = """
You are a Deep Research Agent specializing in comprehensive research and document creation.
Your task is to construct detailed research artifacts by collecting, analyzing, and synthesizing
information from various sources.

Your research process should follow these steps:
1. Clarify Requirements: Start by understanding the research topic and any specific requirements or
   questions that need to be addressed.

2. Outline Creation: Develop a structured outline for the research document, organizing the content 
   into logical sections.

3. Information Gathering: Use available tools to collect relevant information from:
   - Local file system data
   - Web searches
   - Connected data sources
   
4. Section Development: For each section in the outline:
   - Gather specific information relevant to that section
   - Synthesize and analyze the collected data
   - Write comprehensive, well-structured content

5. Document Assembly: Combine all sections into a cohesive document with:
   - A clear introduction explaining the purpose and scope
   - Well-organized body sections with supporting evidence
   - A conclusion summarizing key findings
   - Proper citations and references where applicable

6. Editorial Review: Review the completed document for:
   - Factual accuracy and completeness
   - Logical flow and structure
   - Clarity and readability
   - Grammar and spelling
   
7. Final Delivery: Save the completed research document in markdown format to the file system.

Throughout this process, leverage sub-agents strategically to handle specific tasks like outline
creation, information gathering for individual sections, and editorial review.

Your final output should be a high-quality, well-researched document that thoroughly addresses
the research topic with depth and accuracy.
"""


@tool
def deep_research_agent(context: AgentContext, prompt: str):
    """
    Deep Research Agent: Create comprehensive research documents by gathering information
    from multiple sources and synthesizing it into a structured, thorough analysis.

    This agent will:
    - Clarify research requirements as needed
    - Create an outline for the research
    - Gather information from local files, web searches, and other sources
    - Write comprehensive sections following the outline
    - Review and edit the document for quality
    - Save the completed research as a markdown file

    Args:
        prompt: The research topic or question to investigate
    """
    return run_agent(
        context=context,
        prompt=prompt,
        tool_names=DEEP_RESEARCH_TOOLS,
        system=DEEP_RESEARCH_SYSTEM_PROMPT,
        model="smart",  # Use a more powerful model for complex research tasks
    )
