"""
CLI tools for issue tracking with Plane.so
Provides CLI tools to initialize and work with issue tracking.
"""

import json
import os

import requests
import yaml
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
import sys
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table
from rich import box


console = Console()

CONFIG_DIR = os.path.expanduser("~/.config/hdev")
CONFIG_FILE = os.path.join(CONFIG_DIR, "issues.yml")


def ensure_config_dir():
    """Ensure the config directory exists."""
    os.makedirs(CONFIG_DIR, exist_ok=True)


def read_config() -> Dict[str, Any]:
    """Read the issue tracking configuration."""
    if not os.path.exists(CONFIG_FILE):
        return {"workspaces": {}, "projects": {}}

    with open(CONFIG_FILE, "r") as f:
        return yaml.safe_load(f) or {"workspaces": {}, "projects": {}}


def write_config(config: Dict[str, Any]):
    """Write the issue tracking configuration."""
    ensure_config_dir()

    # Create the directory for the file if it doesn't exist
    os.makedirs(os.path.dirname(str(CONFIG_FILE)), exist_ok=True)

    # Write the config to the file
    with open(str(CONFIG_FILE), "w") as f:
        yaml.dump(config, f, default_flow_style=False)

    # Print the configuration (helps with debugging)
    console.print(yaml.dump(config, default_flow_style=False))


def get_git_repo_name() -> Optional[str]:
    """Get the repository name from git if available."""
    try:
        # Get the remote URL
        remote_url = subprocess.check_output(
            ["git", "config", "--get", "remote.origin.url"],
            text=True,
            stderr=subprocess.PIPE,
        ).strip()

        # Extract repo name from URL (handles both HTTPS and SSH formats)
        if remote_url.endswith(".git"):
            remote_url = remote_url[:-4]

        repo_name = os.path.basename(remote_url)
        return repo_name
    except subprocess.CalledProcessError:
        # Not a git repository or no remote
        return None
    except Exception:
        return None


def get_current_dir_name() -> str:
    """Get the current directory name."""
    return os.path.basename(os.path.abspath(os.curdir))


def get_project_from_config(
    repo_name: str | None = None, cwd: Path | None = None
) -> dict | None:
    config = read_config()
    repo_name = repo_name or get_git_repo_name()
    cwd = cwd or str(Path.cwd())
    result = None
    if "projects" not in config:
        return result
    if repo_name and repo_name in config["projects"]:
        result = config["projects"][repo_name]
    elif cwd in config["projects"]:
        result = config["projects"][cwd]

    result["api_key"] = config["workspaces"][result["workspace"]]
    return result


def _get_plane_api_key() -> str:
    """
    Get the Plane.so API key from environment variables or from the ~/.plane-secret file.

    Returns:
        str: The API key for Plane.so

    Raises:
        ValueError: If API key is not found
    """
    # Check environment variable first
    project_config = get_project_from_config()
    api_key = project_config.get("api_key")

    # If still no API key, raise an error
    if not api_key:
        raise ValueError(
            "Plane API key not found. Please set PLANE_API_KEY environment variable or create ~/.plane-secret file."
        )

    return api_key


def _get_plane_headers(api_key: str = None) -> Dict[str, str]:
    """
    Get headers for Plane.so API requests including the API key.

    Returns:
        Dict[str, str]: Headers dictionary with API key
    """
    if not api_key:
        api_key = _get_plane_api_key()
    return {
        "x-api-key": api_key,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def _make_plane_request(
    method: str,
    endpoint: str,
    data: Optional[Dict[str, Any]] = None,
    params: Optional[Dict[str, Any]] = None,
    api_key: str = None,
) -> Dict[str, Any]:
    """
    Make a request to the Plane.so API.

    Args:
        method: HTTP method (GET, POST, PATCH, DELETE)
        endpoint: API endpoint (should start with /)
        data: Optional request body data
        params: Optional URL parameters
        headers: Optional custom headers (if not provided, will use default headers)

    Returns:
        Dict[str, Any]: Response from the API

    Raises:
        Exception: If the request fails
    """
    base_url = "https://api.plane.so"  # Base URL for Plane.so API
    url = f"{base_url}{endpoint}"

    response = None
    try:
        response = requests.request(
            method=method,
            url=url,
            headers=_get_plane_headers(api_key=api_key),
            json=data if data else None,
            params=params if params else None,
        )

        response.raise_for_status()

        if response.text:
            return response.json()
        return {}

    except requests.exceptions.RequestException as e:
        error_msg = f"Error making request to Plane.so API: {str(e)}"
        try:
            if response and response.text:
                error_details = response.json()
                error_msg = f"{error_msg}. Details: {json.dumps(error_details)}"
        except Exception:
            raise

        raise Exception(error_msg)


def print_message(message: str):
    """Print a message to the console."""
    console.print(message)


def interactive_select(
    options: List[Tuple[str, Any]], title: str = "Select an option"
) -> Tuple[str, Any]:
    """Create an interactive selector for options.

    Args:
        options: List of (display_text, value) tuples
        title: Title for the selector

    Returns:
        Selected (display_text, value) tuple
    """
    if not options:
        console.print("[bold red]No options available[/bold red]")
        sys.exit(1)

    table = Table(box=box.ROUNDED, title=title)
    table.add_column("#", style="cyan")
    table.add_column("Option", style="green")

    for i, (text, _) in enumerate(options, 1):
        table.add_row(str(i), text)

    # Display the options
    console.print(table)

    # Get user selection
    choice = Prompt.ask(
        "Enter your selection",
        choices=[str(i) for i in range(1, len(options) + 1)],
        show_choices=False,
    )

    if not choice:
        console.print("[bold red]Operation canceled[/bold red]")
        sys.exit(1)

    selected_idx = int(choice) - 1
    return options[selected_idx]


def config_issues(
    user_input: str = "", tool_result_buffer: List[dict] = None, **kwargs
):
    """Configure issue tracking for a project.

    This can be invoked either via the slash command /config issues or
    via the command line as heare-developer config issues.

    It initializes or updates the configuration for issue tracking by writing
    to ~/.config/hdev/issues.yml.
    """
    tool_result_buffer = tool_result_buffer or []

    # Display help if just "config" is used
    if user_input.strip() == "config":
        print_message(
            "Usage: /config [type]\n\n"
            "Examples:\n"
            "  /config issues - Configure issue tracking\n"
        )
        return

    # Check if we're handling a specific subcommand of config
    config = read_config()

    # Initialize empty dictionaries if they don't exist
    if not config.get("workspaces"):
        config["workspaces"] = {}

    if not config.get("projects"):
        config["projects"] = {}

    selected_workspace = workspace_selection_flow(config)

    # Get workspace projects from Plane API
    try:
        api_key = config["workspaces"][selected_workspace]
        project_name = project_selection_flow(config, selected_workspace, api_key)

        print_message("Issue tracking initialized successfully!")

        # Pretty print the config
        console.print(
            Panel(
                yaml.dump(config, default_flow_style=False),
                title="Current configuration (~/.config/hdev/issues.yml)",
                border_style="green",
            )
        )

        # Add config summary to tool result buffer
        result_message = f"Issue tracking configured successfully for project '{project_name}' in workspace '{selected_workspace}'."
        tool_result_buffer.append({"role": "user", "content": result_message})

    except Exception as e:
        print_message(f"Error initializing issue tracking: {str(e)}")


def workspace_selection_flow(config):
    # Present any configured workspaces and option to create a new one
    workspace_choices = [
        (workspace, workspace) for workspace in config["workspaces"].keys()
    ]
    # Always add option to create a new workspace
    workspace_choices.append(("Create a new workspace", "new"))

    def _create_workspace_dialog():
        # Create a new workspace
        slug = Prompt.ask("Enter workspace slug")
        _api_key = Prompt.ask(
            "Enter Plane.so API key for this workspace", password=True
        )

        config["workspaces"][slug] = _api_key
        write_config(config)
        print_message(f"Added workspace '{slug}' to configuration.")
        return slug

    # If we have existing workspaces, let the user select one or create a new one
    if config["workspaces"]:
        selected_workspace_text, selected_workspace = interactive_select(
            workspace_choices,
            title="[bold blue]Select a workspace or create a new one[/bold blue]",
        )

        if selected_workspace == "new":
            selected_workspace = _create_workspace_dialog()
    else:
        # No workspaces configured, prompt to add one
        print_message("No workspaces configured. Let's add one first.")
        selected_workspace = _create_workspace_dialog()
    return selected_workspace


def project_selection_flow(config, workspace_slug, api_key):
    """Select a project from the workspace or create a new one.

    Args:
        config: The configuration dictionary
        workspace_slug: The selected workspace slug
        api_key: The API key for the workspace

    Returns:
        str: The name of the selected or created project
    """
    # Get projects from the workspace
    workspace_projects = get_workspace_projects(workspace_slug, api_key)

    # Get default project name suggestion
    default_name = get_git_repo_name() or get_current_dir_name()

    # Create list of projects for selection
    project_choices = []
    for project in workspace_projects:
        project_name = project.get("name")
        project_id = project.get("id")
        choice_name = f"{project_name} ({project_id})"

        # Check if this is our suggested default
        if default_name and default_name.lower() == project_name.lower():
            # Put a marker next to the suggested default
            choice_name = f"{project_name} ({project_id}) [suggested]"
            # Move to the top of the list
            project_choices.insert(0, (choice_name, project))
        else:
            project_choices.append((choice_name, project))

    # Add option to create a new project
    project_choices.append(("Create a new project", "new"))

    # Prompt user to select a project
    selected_project_text, selected_project = interactive_select(
        project_choices, title="[bold blue]Select a project[/bold blue]"
    )

    def _create_project_dialog():
        # Create a new project
        new_project_name = Prompt.ask("Enter project name", default=default_name)
        display_name = Prompt.ask(
            "Enter display name (optional)", default=new_project_name
        )

        new_project_id = create_new_project(workspace_slug, api_key, new_project_name)

        if new_project_id:
            print_message(
                f"Created new project '{new_project_name}' with ID: {new_project_id}"
            )

            # Add to config
            config["projects"][new_project_name] = {
                "_id": new_project_id,
                "name": display_name,
                "workspace": workspace_slug,
            }
            write_config(config)
            print_message(f"Added project '{new_project_name}' to configuration.")
            return new_project_name
        else:
            print_message("Failed to create new project.")
            sys.exit(1)

    if selected_project == "new":
        return _create_project_dialog()
    else:
        # Use existing project
        project_name = selected_project.get("name")
        project_id = selected_project.get("id")

        # Ask for a display name (optional)
        display_name = Prompt.ask("Enter display name (optional)", default=project_name)

        # Add to config
        config["projects"][project_name] = {
            "_id": project_id,
            "name": display_name,
            "workspace": workspace_slug,
        }
        write_config(config)
        print_message(f"Added project '{project_name}' to configuration.")
        return project_name


def issues(user_input: str = "", **kwargs):
    """Browse and manage issues in configured projects.

    Supports:
    1. "issues list" - Lists all issues and allows selection
    2. "issues <project-prefix>-<issue number>" - Directly loads a specific issue
    """
    # First check if issues are configured
    config = read_config()
    if not config.get("projects"):
        print_message(
            "Issue tracking is not configured yet.\n\n"
            "To configure issue tracking, run: /config issues\n\n"
            "This will help you set up workspaces and projects for issue tracking."
        )
        return

    project_config = get_project_from_config()

    # Check if we have any parameters
    parts = user_input.strip().split()

    if len(parts) < 1:
        # No arguments provided, default to list
        return list_issues(user_input, **kwargs)

    subcommand = parts[0]

    # Check if the argument matches the <project-prefix>-<issue number> pattern
    if "-" in subcommand and len(subcommand.split("-")) == 2:
        # This looks like a direct issue reference
        project_prefix, issue_number = subcommand.split("-")
        if issue_number.isdigit():
            issue = _load_issue(subcommand, **kwargs)
            comments = get_issue_comments(
                workspace_slug=project_config["workspace"],
                project_id=issue["project"],
                issue_id=issue["id"],
            )
            return format_issue_details(subcommand, issue, comments, [])

    # If not a direct issue reference, handle standard subcommands
    if subcommand == "list":
        return list_issues(user_input, **kwargs)
    else:
        print_message(
            f"Unknown subcommand: {subcommand}\n\n"
            "Available commands:\n"
            "- issues list - List and browse issues\n"
            "- issues <project-prefix>-<issue number> - Directly load a specific issue"
        )
        return


def _load_issue(sequence_id: str, **_):
    """Load a specific issue by its project prefix and issue number.

    Args:
        sequence_id: An issue identifier that maps to <project-identifier>-<issue number>

    This function directly loads a specific issue based on the project prefix and issue number.
    It bypasses the project and issue selection process.
    """
    config = read_config()

    # Check if issues are configured
    if not config.get("projects"):
        print_message(
            "Issue tracking is not configured yet. Please run '/config issues' first."
        )
        return

    project = get_project_from_config()
    endpoint = f"/api/v1/workspaces/{project['workspace']}/issues/{sequence_id}"
    return _make_plane_request("GET", endpoint)


def list_issues(user_input: str = "", **kwargs) -> str:
    """Browse issues in configured projects.

    This function lists issues from the configured project. When an issue is selected,
    it shows the full details including title, description, linked issues, comments,
    and their authors.

    Users can also add the issue details to the conversation.
    """
    config = read_config()

    # Extract project name from command if specified, otherwise try to match with git repo or current directory
    parts = user_input.strip().split()
    specified_project = None
    if len(parts) > 2:
        specified_project = parts[2]

    # Check if we need to select a project from available ones
    project_config = get_project_from_config(repo_name=specified_project)

    if not project_config:
        if not config.get("projects"):
            print_message("No projects configured. Please run '/config issues' first.")
            return

        # Let user select a project from the available ones
        project_choices = [
            (name, details) for name, details in config["projects"].items()
        ]
        if not project_choices:
            print_message("No projects configured. Please run '/config issues' first.")
            return

        _, project_config = interactive_select(
            project_choices, title="[bold blue]Select a project[/bold blue]"
        )

    workspace_slug = project_config["workspace"]
    project_id = project_config["_id"]
    project_name = project_config["name"]

    # Make sure we have an API key for the workspace
    if workspace_slug not in config["workspaces"]:
        print_message(
            f"No API key found for workspace '{workspace_slug}'. Please run '/config issues' first."
        )
        return

    api_key = config["workspaces"][workspace_slug]

    # Display the current project
    console.print(
        Panel(
            f"Working with project: [bold]{project_name}[/bold]", border_style="green"
        )
    )

    # Get issues for this project
    try:
        issues = get_project_issues(workspace_slug, project_id, api_key)

        if not issues:
            print_message(f"No issues found in project '{project_name}'.")
            return ""

        # Create a list of issues for selection, sorted by sequence_id
        issues.sort(key=lambda x: x.get("sequence_id", 0))

        # Build a rich table for display
        table = Table(box=box.ROUNDED, title=f"Issues in {project_name}")
        table.add_column("ID", style="cyan")
        table.add_column("Title", style="green", no_wrap=False)
        table.add_column("Status", style="yellow")
        table.add_column("Priority", style="magenta")
        table.add_column("Assignee", style="blue")

        issue_choices = []

        # Populate the table with issues
        for issue in issues:
            issue_name = issue.get("name", "Untitled")
            sequence_id = issue.get("sequence_id", "?")
            state = issue.get("state_detail", {}).get("name", "Unknown")
            priority = issue.get("priority", "None")
            assignee = issue.get("assignee_detail", {}).get(
                "display_name", "Unassigned"
            )

            # Add to table
            table.add_row(
                f"{project_config['identifier']}-{sequence_id}",
                issue_name[:50] + ("..." if len(issue_name) > 50 else ""),
                state,
                priority,
                assignee,
            )

            # Format: #ID | Title | Status | Assignee
            choice_text = f"{project_config['identifier']}-{sequence_id} | {issue_name} | {state} | {assignee}"
            issue_choices.append((choice_text, issue))

        # Let user select an issue
        selected_issue_text, selected_issue = interactive_select(
            issue_choices, title="[bold blue]Select an issue for details[/bold blue]"
        )

        # Get issue details including comments
        issue_details = get_issue_details(
            workspace_slug, project_id, selected_issue["id"], api_key
        )
        issue_comments = get_issue_comments(
            workspace_slug, project_id, selected_issue["id"]
        )

        # Get linked issues if any
        linked_issues = []
        if issue_details.get("link_count", 0) > 0:
            try:
                link_endpoint = f"/api/v1/workspaces/{workspace_slug}/projects/{project_id}/issues/{selected_issue['id']}/links"
                linked_issues = _make_plane_request(
                    "GET",
                    link_endpoint,
                )
            except Exception:
                pass

        # Format issue details
        issue_formatted = format_issue_details(
            f"{project_config['identifier']}-{issue_details['sequence_id']}",
            issue_details,
            issue_comments,
            linked_issues,
        )

        # Display issue details in a panel
        console.print(
            Panel(
                issue_formatted,
                title=f"Issue #{issue_details.get('sequence_id')}: {issue_details.get('name')}",
                border_style="green",
                expand=True,
            )
        )

    except Exception as e:
        print_message(f"Error browsing issues: {str(e)}")


def get_workspace_projects(workspace_slug: str, api_key: str) -> List[Dict[str, Any]]:
    """Get projects for a workspace."""

    endpoint = f"/api/v1/workspaces/{workspace_slug}/projects"
    return _make_plane_request("GET", endpoint)["results"]


def get_project_issues(
    workspace_slug: str, project_id: str, api_key: str
) -> List[Dict[str, Any]]:
    """Get issues for a project."""

    endpoint = f"/api/v1/workspaces/{workspace_slug}/projects/{project_id}/issues"
    return _make_plane_request("GET", endpoint)["results"]


def get_issue_details(
    workspace_slug: str, project_id: str, issue_id: str, api_key: str
) -> Dict[str, Any]:
    """Get details for an issue."""

    endpoint = (
        f"/api/v1/workspaces/{workspace_slug}/projects/{project_id}/issues/{issue_id}"
    )
    return _make_plane_request("GET", endpoint)


def get_issue_project_by_id(
    workspace_slug: str, project_id: str, api_key: str
) -> Dict[str, Any]:
    """Get details for a project by its ID."""

    endpoint = f"/api/v1/workspaces/{workspace_slug}/projects/{project_id}"
    return _make_plane_request("GET", endpoint)


def get_issue_comments(
    workspace_slug: str, project_id: str, issue_id: str
) -> List[Dict[str, Any]]:
    """Get comments for an issue."""

    endpoint = f"/api/v1/workspaces/{workspace_slug}/projects/{project_id}/issues/{issue_id}/comments"
    return _make_plane_request("GET", endpoint)["results"]


def create_new_project(
    workspace_slug: str, api_key: str, project_name: str
) -> Optional[str]:
    """Create a new project in Plane.so."""

    # Generate a project identifier (usually capital letters from the name)
    identifier = (
        "".join([c for c in project_name if c.isupper()]) or project_name[:3].upper()
    )

    data = {
        "name": project_name,
        "identifier": identifier,
    }

    endpoint = f"/api/v1/workspaces/{workspace_slug}/projects"
    try:
        response = _make_plane_request(
            "POST", endpoint, data=data, headers={"x-api-key": api_key}
        )
        return response.get("id")
    except Exception:
        return None


def format_issue_details(
    sequence_id: str,
    issue: Dict[str, Any],
    comments: List[Dict[str, Any]],
    linked_issues: List[Dict[str, Any]] = None,
) -> str:
    """Format issue details for display.

    Formats the issue with title, description, metadata, linked issues, and comments
    for display to the user.

    Args:
        issue: The issue details dictionary
        comments: List of comment dictionaries
        linked_issues: List of linked issue dictionaries

    Returns:
        Formatted string with issue details
    """
    result = f"[bold]{sequence_id.upper()}: {issue.get('name')}[/bold]\n"
    result += (
        f"[bold]Status:[/bold] {issue.get('state_detail', {}).get('name', 'Unknown')}\n"
    )
    result += f"[bold]Priority:[/bold] {issue.get('priority', 'None')}\n"
    result += f"[bold]Assignee:[/bold] {issue.get('assignee_detail', {}).get('display_name', 'Unassigned')}\n"
    result += f"[bold]Created by:[/bold] {issue.get('created_by_detail', {}).get('display_name', 'Unknown')}\n"
    result += f"[bold]Created:[/bold] {issue.get('created_at')}\n"
    result += f"[bold]Updated:[/bold] {issue.get('updated_at')}\n\n"

    result += "[bold underline]Description:[/bold underline]\n"
    description = issue.get("description", "No description")
    # Convert markdown to rich format if description is present
    if description and description.strip():
        result += f"{description}\n\n"
    else:
        result += "No description provided.\n\n"

    # Add linked issues if any
    if linked_issues:
        result += "[bold underline]Linked Issues:[/bold underline]\n"
        for link in linked_issues:
            relation = link.get("relation", "relates_to")
            related_issue = link.get("related_issue", {})
            title = related_issue.get("name", "Unknown")
            seq_id = related_issue.get("sequence_id", "?")
            result += f"• {title} (#{seq_id}, Relation: {relation})\n"
        result += "\n"
    elif issue.get("linked_issues"):
        result += "[bold underline]Linked Issues:[/bold underline]\n"
        for link in issue.get("linked_issues", []):
            result += f"• {link.get('title', 'Unknown')} (#{link.get('sequence_id', '?')}, Relation: {link.get('relation', 'relates_to')})\n"
        result += "\n"

    # Add comments if any
    if comments:
        result += "[bold underline]Comments:[/bold underline]\n"
        for i, comment in enumerate(comments, 1):
            author = comment.get("actor_detail", {}).get("display_name", "Unknown")
            text = comment.get("comment_text", "").strip()
            created_at = comment.get("created_at", "")

            result += f"[{i}] [bold cyan]{author}[/bold cyan] ([italic]{created_at}[/italic]):\n"
            result += f"{text}\n\n"

    return result


# CLI Tools to be registered
ISSUE_CLI_TOOLS = {
    "config": {
        "func": config_issues,
        "docstring": "Configure settings (use: /config issues)",
        "aliases": [],
    },
    "issues": {
        "func": issues,
        "docstring": "Browse and manage issues in configured projects",
        "aliases": ["i", "issue"],
    },
}
