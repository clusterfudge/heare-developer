"""
CLI tools for issue tracking with Plane.so
Provides CLI tools to initialize and work with issue tracking.
"""

import os
import yaml
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Any
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm

from heare.developer.sandbox import Sandbox
from heare.developer.user_interface import UserInterface
from heare.developer.tools.issues import _make_plane_request

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

    # Print the configuration (helps with debugging)
    print(yaml.dump(config, default_flow_style=False))

    # Create the directory for the file if it doesn't exist
    os.makedirs(os.path.dirname(str(CONFIG_FILE)), exist_ok=True)

    # Write the config to the file
    with open(str(CONFIG_FILE), "w") as f:
        yaml.dump(config, f, default_flow_style=False)


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
    if "projects" not in config:
        return None
    elif repo_name in config["projects"]:
        return config["projects"][repo_name]
    elif cwd in config["projects"]:
        return config["projects"][cwd]
    else:
        return None


def config_issues(
    user_interface: UserInterface, sandbox: Sandbox, user_input: str = "", **kwargs
):
    """Configure issue tracking for a project.

    This can be invoked either via the slash command /config issues or
    via the command line as heare-developer config issues.

    It initializes or updates the configuration for issue tracking by writing
    to ~/.config/hdev/issues.yml.
    """
    # Display help if just "config" is used
    if user_input.strip() == "config":
        user_interface.handle_system_message(
            "Usage: /config [type]\n\n"
            "Examples:\n"
            "  /config issues - Configure issue tracking\n"
        )
        return

    # Check if we're handling a specific subcommand of config
    config = read_config()

    # If no workspaces configured, prompt to add one
    if not config.get("workspaces"):
        config["workspaces"] = {}

    if not config.get("projects"):
        config["projects"] = {}

    # Check if we need to add a workspace
    if not config["workspaces"]:
        user_interface.handle_system_message(
            "No workspaces configured. Let's add one first."
        )

        workspace_name = user_interface.get_user_input("Enter workspace slug: ")
        api_key = user_interface.get_user_input(
            "Enter Plane.so API key for this workspace: "
        )

        config["workspaces"][workspace_name] = api_key
        write_config(config)
        user_interface.handle_system_message(
            f"Added workspace '{workspace_name}' to configuration."
        )
    else:
        # Ask if user wants to add a new workspace
        add_workspace = Confirm.ask("Add a new workspace?")
        if add_workspace:
            workspace_name = Prompt.ask("Enter workspace slug")
            api_key = Prompt.ask(
                "Enter Plane.so API key for this workspace", password=True
            )

            config["workspaces"][workspace_name] = api_key
            write_config(config)
            user_interface.handle_system_message(
                f"Added workspace '{workspace_name}' to configuration."
            )

    # Let user select a workspace
    workspace_choices = list(config["workspaces"].keys())

    console.print(Panel("[bold blue]Select a workspace[/bold blue]"))
    for i, workspace in enumerate(workspace_choices, 1):
        console.print(f"{i}. {workspace}")

    choice = Prompt.ask(
        "Enter the number of your choice",
        choices=[str(i) for i in range(1, len(workspace_choices) + 1)],
        show_choices=False,
    )

    if not choice:
        user_interface.handle_system_message("Operation canceled.")
        return

    selected_workspace = workspace_choices[int(choice) - 1]

    # Get workspace projects from Plane API
    try:
        api_key = config["workspaces"][selected_workspace]
        workspace_projects = get_workspace_projects(selected_workspace, api_key)

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
                choice_name = f"{project_name} ({project_id}) -- suggested"
                # Move to the top of the list
                project_choices.insert(0, (choice_name, project))
            else:
                project_choices.append((choice_name, project))

        # Add option to create a new project
        project_choices.append(("Create a new project", "new"))

        # Prompt user to select a project
        console.print(Panel("[bold blue]Select a project[/bold blue]"))
        for i, (name, _) in enumerate(project_choices, 1):
            console.print(f"{i}. {name}")

        choice = Prompt.ask(
            "Enter the number of your choice",
            choices=[str(i) for i in range(1, len(project_choices) + 1)],
            show_choices=False,
        )

        if not choice:
            user_interface.handle_system_message("Operation canceled.")
            return

        selected_project_name = project_choices[int(choice) - 1][0]

        # Find the selected project in our choices
        selected_project = None
        for name, project in project_choices:
            if name == selected_project_name:
                selected_project = project
                break

        if selected_project == "new":
            # Create a new project
            new_project_name = (
                user_interface.get_user_input(
                    f"Enter project name (default: {default_name}): "
                )
                or default_name
            )
            display_name = (
                user_interface.get_user_input(
                    f"Enter display name (optional, default: {new_project_name}): "
                )
                or new_project_name
            )
            new_project_id = create_new_project(
                selected_workspace, api_key, new_project_name
            )

            if new_project_id:
                user_interface.handle_system_message(
                    f"Created new project '{new_project_name}' with ID: {new_project_id}"
                )

                # Add to config
                config["projects"][new_project_name] = {
                    "_id": new_project_id,
                    "name": display_name,
                    "workspace": selected_workspace,
                }
                write_config(config)
                user_interface.handle_system_message(
                    f"Added project '{new_project_name}' to configuration."
                )
            else:
                user_interface.handle_system_message("Failed to create new project.")
                return
        else:
            # Use existing project
            project_name = selected_project.get("name")
            project_id = selected_project.get("id")

            # Ask for a display name (optional)
            display_name = (
                user_interface.get_user_input(
                    f"Enter display name (optional, default: {project_name}): "
                )
                or project_name
            )

            # Add to config
            config["projects"][project_name] = {
                "_id": project_id,
                "name": display_name,
                "workspace": selected_workspace,
            }
            write_config(config)
            user_interface.handle_system_message(
                f"Added project '{project_name}' to configuration."
            )

        user_interface.handle_system_message("Issue tracking initialized successfully!")

        # Pretty print the config
        user_interface.handle_system_message(
            f"\nCurrent configuration (~/.config/hdev/issues.yml):\n{yaml.dump(config, default_flow_style=False)}"
        )

    except Exception as e:
        user_interface.handle_system_message(
            f"Error initializing issue tracking: {str(e)}"
        )


def issues(
    user_interface: UserInterface, sandbox: Sandbox, user_input: str = "", **kwargs
):
    """Browse and manage issues in configured projects."""
    # First check if issues are configured
    config = read_config()
    if not config["projects"]:
        user_interface.handle_system_message(
            "Issue tracking is not configured yet.\n\n"
            "To configure issue tracking, run: /config issues\n\n"
            "This will help you set up workspaces and projects for issue tracking."
        )
        return

    # Check if we have any parameters
    parts = user_input.strip().split()
    subcommand = parts[1] if len(parts) > 1 else "list"

    if subcommand == "list":
        return list_issues(user_interface, sandbox, user_input, **kwargs)
    else:
        user_interface.handle_system_message(
            f"Unknown subcommand: {subcommand}\n\nAvailable subcommands:\n- list: List and browse issues"
        )
        return


def list_issues(
    user_interface: UserInterface, sandbox: Sandbox, user_input: str = "", **kwargs
):
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

    # Use specified project if explicitly provided
    project_config = get_project_from_config(repo_name=specified_project)
    workspace_slug = project_config["workspace"]
    project_id = project_config["_id"]
    api_key = config["workspaces"][workspace_slug]

    # Get issues for this project
    try:
        issues = get_project_issues(workspace_slug, project_id, api_key)

        if not issues:
            user_interface.handle_system_message(
                f"No issues found in project '{project_config['name']}'."
            )
            return

        # Create a list of issues for selection, sorted by sequence_id
        issues.sort(key=lambda x: x.get("sequence_id", 0))
        issue_choices = []

        for issue in issues:
            issue_name = issue.get("name", "Untitled")
            sequence_id = issue.get("sequence_id", "?")
            state = issue.get("state_detail", {}).get("name", "Unknown")
            assignee = issue.get("assignee_detail", {}).get(
                "display_name", "Unassigned"
            )

            # Format: #ID | Title | Status | Assignee
            choice_text = f"#{sequence_id} | {issue_name} | {state} | {assignee}"
            issue_choices.append((choice_text, issue))

        console.print(Panel("[bold blue]Select an issue[/bold blue]"))
        for i, (name, _) in enumerate(issue_choices, 1):
            console.print(f"{i}. {name}")

        choice = Prompt.ask(
            "Enter the number of your choice",
            choices=[str(i) for i in range(1, len(issue_choices) + 1)],
            show_choices=False,
        )

        if not choice:
            user_interface.handle_system_message("Operation canceled.")
            return

        selected_issue_name = issue_choices[int(choice) - 1][0]

        # Find the selected issue in our choices
        selected_issue = None
        for name, issue in issue_choices:
            if name == selected_issue_name:
                selected_issue = issue
                break

        if not selected_issue:
            user_interface.handle_system_message("Issue selection failed.")
            return

        # Get issue details including comments
        issue_details = get_issue_details(
            workspace_slug, project_id, selected_issue["id"], api_key
        )
        issue_comments = get_issue_comments(
            workspace_slug, project_id, selected_issue["id"], api_key
        )

        # Get linked issues if any
        linked_issues = []
        if issue_details.get("link_count", 0) > 0:
            try:
                link_endpoint = f"/api/v1/workspaces/{workspace_slug}/projects/{project_id}/issues/{selected_issue['id']}/links/"
                headers = {
                    "x-api-key": api_key,
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                }
                linked_issues = _make_plane_request(
                    "GET", link_endpoint, headers=headers
                )
            except Exception:
                pass

        # Display issue details
        issue_formatted = format_issue_details(
            issue_details, issue_comments, linked_issues
        )
        user_interface.handle_system_message(issue_formatted)

        # Ask if the user wants to add this to the conversation
        add_to_conversation = Confirm.ask("Add this issue to the conversation?")
        if add_to_conversation:
            # Add to tool result buffer
            tool_result_buffer = kwargs.get("tool_result_buffer", [])

            # Format a message that includes attribution for the issue and comments
            message = f"Issue #{issue_details.get('sequence_id')}: {issue_details.get('name')}\n\n"
            message += f"Created by: {issue_details.get('created_by_detail', {}).get('display_name', 'Unknown')}\n\n"
            message += issue_formatted

            tool_result_buffer.append({"role": "user", "content": message})
            user_interface.handle_system_message("Issue added to the conversation.")

    except Exception as e:
        user_interface.handle_system_message(f"Error browsing issues: {str(e)}")


def get_workspace_projects(workspace_slug: str, api_key: str) -> List[Dict[str, Any]]:
    """Get projects for a workspace."""
    headers = {
        "x-api-key": api_key,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    endpoint = f"/api/v1/workspaces/{workspace_slug}/projects"
    return _make_plane_request("GET", endpoint, headers=headers)["results"]


def get_project_issues(
    workspace_slug: str, project_id: str, api_key: str
) -> List[Dict[str, Any]]:
    """Get issues for a project."""
    headers = {
        "x-api-key": api_key,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    endpoint = f"/api/v1/workspaces/{workspace_slug}/projects/{project_id}/issues"
    return _make_plane_request("GET", endpoint, headers=headers)["results"]


def get_issue_details(
    workspace_slug: str, project_id: str, issue_id: str, api_key: str
) -> Dict[str, Any]:
    """Get details for an issue."""
    headers = {
        "x-api-key": api_key,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    endpoint = (
        f"/api/v1/workspaces/{workspace_slug}/projects/{project_id}/issues/{issue_id}"
    )
    return _make_plane_request("GET", endpoint, headers=headers)


def get_issue_comments(
    workspace_slug: str, project_id: str, issue_id: str, api_key: str
) -> List[Dict[str, Any]]:
    """Get comments for an issue."""
    headers = {
        "x-api-key": api_key,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    endpoint = f"/api/v1/workspaces/{workspace_slug}/projects/{project_id}/issues/{issue_id}/comments"
    return _make_plane_request("GET", endpoint, headers=headers)["results"]


def create_new_project(
    workspace_slug: str, api_key: str, project_name: str
) -> Optional[str]:
    """Create a new project in Plane.so."""
    headers = {
        "x-api-key": api_key,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

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
        response = _make_plane_request("POST", endpoint, data=data, headers=headers)
        return response.get("id")
    except Exception:
        return None


def format_issue_details(
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
    result = f"Issue #{issue.get('sequence_id')}: {issue.get('name')}\n"
    result += f"Status: {issue.get('state_detail', {}).get('name', 'Unknown')}\n"
    result += f"Priority: {issue.get('priority', 'None')}\n"
    result += f"Assignee: {issue.get('assignee_detail', {}).get('display_name', 'Unassigned')}\n"
    result += f"Created by: {issue.get('created_by_detail', {}).get('display_name', 'Unknown')}\n"
    result += f"Created: {issue.get('created_at')}\n"
    result += f"Updated: {issue.get('updated_at')}\n\n"

    result += "Description:\n"
    result += f"{issue.get('description', 'No description')}\n\n"

    # Add linked issues if any
    if linked_issues:
        result += "Linked Issues:\n"
        for link in linked_issues:
            relation = link.get("relation", "relates_to")
            related_issue = link.get("related_issue", {})
            title = related_issue.get("name", "Unknown")
            seq_id = related_issue.get("sequence_id", "?")
            result += f"- {title} (#{seq_id}, Relation: {relation})\n"
        result += "\n"
    elif issue.get("linked_issues"):
        result += "Linked Issues:\n"
        for link in issue.get("linked_issues", []):
            result += f"- {link.get('title', 'Unknown')} (#{link.get('sequence_id', '?')}, Relation: {link.get('relation', 'relates_to')})\n"
        result += "\n"

    # Add comments if any
    if comments:
        result += "Comments:\n"
        for i, comment in enumerate(comments, 1):
            author = comment.get("actor_detail", {}).get("display_name", "Unknown")
            text = comment.get("comment_text", "").strip()
            created_at = comment.get("created_at", "")

            result += f"[{i}] {author} ({created_at}):\n"
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
