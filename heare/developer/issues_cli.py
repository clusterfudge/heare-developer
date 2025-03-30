"""
CLI tools for issue tracking with Plane.so
Provides CLI tools to initialize and work with issue tracking.
"""

import yaml
from typing import Dict, List, Any, Tuple
import sys
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table
from rich import box

from heare.developer.clients.plane_so import (
    read_config,
    write_config,
    get_git_repo_name,
    get_current_dir_name,
    get_project_from_config,
    _make_plane_request,
    get_project_issues,
    get_issue_details,
    get_issue_comments,
    create_new_project,
    load_issue,
)
from heare.developer.clients.plane_cache import (
    fetch_and_cache_states,
    fetch_and_cache_priorities,
    fetch_and_cache_members,
    get_state_name_by_id,
    get_member_by_id,
    refresh_all_caches,
)

console = Console()


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
        raise


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
        foo = interactive_select(
            workspace_choices,
            title="[bold blue]Select a workspace or create a new one[/bold blue]",
        )
        selected_workspace_text, selected_workspace = foo

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
            "identifier": selected_project.get("identifier"),
        }
        write_config(config)
        print_message(f"Added project '{project_name}' to configuration.")
        return project_name


def issues(user_input: str = "", **kwargs):
    """Browse and manage issues in configured projects.

    Supports:
    1. "issues list" - Lists all issues and allows selection
    2. "issues <project-prefix>-<issue number>" - Directly loads a specific issue
    3. "issues refresh" - Refreshes the local cache of issue data
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

    # Check if the command is to refresh cache
    if subcommand == "refresh":
        if not project_config:
            print_message(
                "No project configuration found. Please run '/config issues' first."
            )
            return

        api_key = config["workspaces"][project_config["workspace"]]
        results = refresh_all_caches(
            project_config["workspace"], project_config["_id"], api_key
        )

        print_message("Cache refresh complete:")
        for entity, success in results.items():
            if "error" not in entity:
                print_message(f"- {entity}: {'Success' if success else 'Failed'}")
        return

    # Check if the argument matches the <project-prefix>-<issue number> pattern
    if "-" in subcommand and len(subcommand.split("-")) == 2:
        # This looks like a direct issue reference
        project_prefix, issue_number = subcommand.split("-")
        if issue_number.isdigit():
            issue = load_issue(subcommand, **kwargs)
            api_key = config["workspaces"][project_config["workspace"]]
            comments = get_issue_comments(
                workspace_slug=project_config["workspace"],
                project_id=issue["project"],
                issue_id=issue["id"],
                api_key=api_key,
            )

            # Ensure we have cached states, priorities, and members
            fetch_and_cache_states(
                project_config["workspace"],
                issue["project"],
                api_key,
                force_refresh=False,
            )
            fetch_and_cache_priorities(
                project_config["workspace"],
                issue["project"],
                api_key,
                force_refresh=False,
            )

            # Try to pre-load member cache, but continue if it fails
            try:
                fetch_and_cache_members(
                    project_config["workspace"],
                    issue["project"],
                    api_key,
                    force_refresh=False,
                )
            except Exception:
                # Continue even if member cache fails
                pass

            return format_issue_details(subcommand, issue, comments, [])

    # If not a direct issue reference, handle standard subcommands
    if subcommand == "list":
        return list_issues(user_input, **kwargs)
    elif subcommand == "refresh":
        # Already handled above
        pass
    else:
        print_message(
            f"Unknown subcommand: {subcommand}\n\n"
            "## Available commands:\n"
            "- **issues list** - List and browse issues\n"
            "- **issues <project-prefix>-<issue number>** - Directly load a specific issue\n"
            "- **issues refresh** - Refresh the local cache of issue data"
        )
        return


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
        # Ensure we have cached states, priorities, and members
        fetch_and_cache_states(workspace_slug, project_id, api_key, force_refresh=False)
        fetch_and_cache_priorities(
            workspace_slug, project_id, api_key, force_refresh=False
        )

        # Try to pre-load member cache, but continue if it fails
        try:
            fetch_and_cache_members(
                workspace_slug, project_id, api_key, force_refresh=False
            )
        except Exception:
            # Continue even if member cache fails
            pass

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

            # Get the state name from cache if possible
            state = "Unknown"
            if issue.get("state"):
                state = get_state_name_by_id(
                    workspace_slug, project_id, issue.get("state"), api_key
                ) or issue.get("state_detail", {}).get("name", "Unknown")
            else:
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
            workspace_slug, project_id, selected_issue["id"], api_key
        )

        # Get linked issues if any
        linked_issues = []
        if issue_details.get("link_count", 0) > 0:
            try:
                link_endpoint = f"/api/v1/workspaces/{workspace_slug}/projects/{project_id}/issues/{selected_issue['id']}/links"
                linked_issues = _make_plane_request(
                    "GET", link_endpoint, api_key=api_key
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
    return _make_plane_request("GET", endpoint, api_key=api_key)["results"]


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
        sequence_id: the user-facing identifier of the issue
        issue: The issue details dictionary
        comments: List of comment dictionaries
        linked_issues: List of linked issue dictionaries

    Returns:
        Formatted string with issue details
    """
    result = f"[bold]{sequence_id.upper()}: {issue.get('name')}[/bold]\n"

    # Get state name from cache if possible, otherwise fallback to details in the issue
    state_name = "Unknown"
    if issue.get("state"):
        project_config = get_project_from_config()
        if project_config:
            api_key = read_config()["workspaces"][project_config["workspace"]]
            state_name = get_state_name_by_id(
                project_config["workspace"],
                issue.get("project"),
                issue.get("state"),
                api_key,
            ) or issue.get("state_detail", {}).get("name", "Unknown")
        else:
            state_name = issue.get("state_detail", {}).get("name", "Unknown")
    else:
        state_name = issue.get("state_detail", {}).get("name", "Unknown")

    result += f"[bold]Status:[/bold] {state_name}\n"
    result += f"[bold]Priority:[/bold] {issue.get('priority', 'None')}\n"

    # Get assignee information from cache if possible
    assignees = []
    for assignee_id in issue.get("assignees", []):
        assignee_name = "Unassigned"
        if assignee_id:
            project_config = get_project_from_config()
            if project_config:
                api_key = read_config()["workspaces"][project_config["workspace"]]
                workspace_slug = project_config["workspace"]

                member_details = get_member_by_id(
                    workspace_slug, issue.get("project"), assignee_id, api_key
                )
                if member_details and member_details.get("name"):
                    assignee_name = member_details.get("name")
                else:
                    # Fall back to the details in the issue if cache lookup fails
                    assignee_name = issue.get("assignee_detail", {}).get(
                        "display_name", "Unassigned"
                    )
            else:
                assignee_name = issue.get("assignee_detail", {}).get(
                    "display_name", "Unassigned"
                )
        assignees.append(assignee_name)

    if not assignees:
        assignees.append("Unassigned")

    # Get creator information from cache if possible
    created_by_id = issue.get("created_by")
    created_by_name = "Unknown"
    if created_by_id:
        project_config = get_project_from_config()
        if project_config:
            api_key = read_config()["workspaces"][project_config["workspace"]]
            workspace_slug = project_config["workspace"]

            member_details = get_member_by_id(
                workspace_slug, issue.get("project"), created_by_id, api_key
            )
            if member_details and member_details.get("name"):
                created_by_name = member_details.get("name")
            else:
                # Fall back to the details in the issue if cache lookup fails
                created_by_name = issue.get("created_by_detail", {}).get(
                    "display_name", "Unknown"
                )
        else:
            created_by_name = issue.get("created_by_detail", {}).get(
                "display_name", "Unknown"
            )

    result += f"[bold]Assignee:[/bold] {','.join(assignees)}\n"
    result += f"[bold]Created by:[/bold] {created_by_name}\n"
    result += f"[bold]Created:[/bold] {issue.get('created_at')}\n"
    result += f"[bold]Updated:[/bold] {issue.get('updated_at')}\n\n"

    result += "[bold underline]Description:[/bold underline]\n"
    description = issue.get("description_stripped", "No description")
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
            # Get author information from cache if possible
            actor_id = comment.get("actor")
            author = "Unknown"
            if actor_id:
                project_config = get_project_from_config()
                if project_config:
                    api_key = read_config()["workspaces"][project_config["workspace"]]
                    workspace_slug = project_config["workspace"]

                    member_details = get_member_by_id(
                        workspace_slug, issue.get("project"), actor_id, api_key
                    )
                    if member_details and member_details.get("name"):
                        author = member_details.get("name")
                    else:
                        # Fall back to the details in the comment if cache lookup fails
                        author = comment.get("actor_detail", {}).get(
                            "display_name", "Unknown"
                        )
                else:
                    author = comment.get("actor_detail", {}).get(
                        "display_name", "Unknown"
                    )
            else:
                author = comment.get("actor_detail", {}).get("display_name", "Unknown")

            text = comment.get("comment_stripped", "").strip()
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
