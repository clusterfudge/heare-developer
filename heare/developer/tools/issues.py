import json
from heare.developer.tools.framework import tool
from heare.developer.context import AgentContext
from heare.developer.clients.plane_so import (
    get_project_from_config,
    get_project_issues,
    _make_plane_request,
    load_issue,
    get_issue_comments,
)
from heare.developer.clients.plane_cache import (
    get_state_id_by_name,
    get_state_name_by_id,
    refresh_all_caches,
    fetch_and_cache_members,
    get_member_by_id,
)
from typing import Optional


@tool
def get_issue(context: "AgentContext", issue_id: str) -> str:
    """Fetch details of a specific issue by its ID.

    This retrieves comprehensive information about an issue including its description,
    status, assigned users, and comments.

    Args:
        issue_id: The issue identifier in the format <project-identifier>-<issue-number> (e.g., PROJ-123)
    """
    # Check if project is configured
    project_config = get_project_from_config()
    if not project_config:
        return "Error: Issue tracking is not configured. Please run '/config issues' first."

    try:
        # Load the issue
        issue = load_issue(issue_id)

        workspace_slug = project_config["workspace"]
        project_id = issue["project"]
        api_key = project_config.get("api_key")

        # Get comments for the issue
        comments = get_issue_comments(
            workspace_slug=workspace_slug,
            project_id=project_id,
            issue_id=issue["id"],
            api_key=api_key,
        )

        # Get state information using the cache
        state_id = issue.get("state")
        state_name = "Unknown"

        if state_id:
            # Try to get the state name from the cache
            cached_state_name = get_state_name_by_id(
                workspace_slug, project_id, state_id, api_key
            )
            if cached_state_name:
                state_name = cached_state_name

        # Ensure member cache is populated
        try:
            fetch_and_cache_members(workspace_slug, project_id, api_key)
        except Exception:
            # Continue even if member cache fails, we'll fall back to the details in the issue
            pass

        # Handle assignee information (with caching)
        assignee_id = issue.get("assignee")
        assignee_name = "Unassigned"
        if assignee_id:
            member_details = get_member_by_id(
                workspace_slug, project_id, assignee_id, api_key
            )
            if member_details and member_details.get("name"):
                assignee_name = member_details.get("name")
            else:
                # Fall back to the details in the issue if cache lookup fails
                assignee_name = issue.get("assignee_detail", {}).get(
                    "display_name", f"User {assignee_id}"
                )

        # Handle creator information (with caching)
        created_by_id = issue.get("created_by")
        created_by_name = "Unknown"
        if created_by_id:
            member_details = get_member_by_id(
                workspace_slug, project_id, created_by_id, api_key
            )
            if member_details and member_details.get("name"):
                created_by_name = member_details.get("name")
            else:
                # Fall back to the details in the issue if cache lookup fails
                created_by_name = issue.get("created_by_detail", {}).get(
                    "display_name", f"User {created_by_id}"
                )

        # Format issue information as a string
        result = f"# {issue_id}: {issue.get('name')}\n"
        result += f"Status: {state_name}\n"
        result += f"Priority: {issue.get('priority', 'None')}\n"
        result += f"Assignee: {assignee_name}\n"
        result += f"Created by: {created_by_name}\n"
        result += f"Created: {issue.get('created_at')}\n"
        result += f"Updated: {issue.get('updated_at')}\n\n"

        result += "## Description\n"
        description = issue.get("description_stripped", "No description")
        if description and description.strip():
            result += f"{description}\n\n"
        else:
            result += "No description\n\n"

        # Add comments if any
        if comments:
            result += "## Comments\n"
            for i, comment in enumerate(comments, 1):
                # Handle commenter information (with caching)
                actor_id = comment.get("actor")
                author = "Unknown"
                if actor_id:
                    member_details = get_member_by_id(
                        workspace_slug, project_id, actor_id, api_key
                    )
                    if member_details and member_details.get("name"):
                        author = member_details.get("name")
                    else:
                        # Fall back to the details in the comment if cache lookup fails
                        author = comment.get("actor_detail", {}).get(
                            "display_name", f"User {actor_id}"
                        )

                text = comment.get("comment_stripped", "").strip()
                created_at = comment.get("created_at", "")
                result += f"**{author}** ({created_at}):\n{text}\n\n"

        return result

    except Exception as e:
        return f"Error retrieving issue: {str(e)}"


@tool
def list_issues(context: "AgentContext", group: str = None) -> str:
    """List all issues in a project.

    Lists all issues from a project, showing their ID, title, status, priority and assignee.

    Args:
        group: Optional group name to specify to filter issues. Leave empty to list all.
                Valid groups are: backlog, unstarted, started, completed, cancelled
    """
    # Check if project is configured
    project_config = get_project_from_config()
    if not project_config:
        return "Error: Issue tracking is not configured. Please run '/config issues' first."

    try:
        workspace_slug = project_config["workspace"]
        project_id = project_config["_id"]
        api_key = project_config.get("api_key")

        # Get issues for this project
        issues = get_project_issues(workspace_slug, project_id, api_key)

        if not issues:
            return (
                f"No issues found in project '{project_config.get('name', 'Unknown')}'."
            )

        # Ensure caches are available
        from heare.developer.clients.plane_cache import (
            fetch_and_cache_states,
            get_state_name_by_id,
        )

        # Pre-load caches for better performance
        fetch_and_cache_states(workspace_slug, project_id, api_key)

        # Try to pre-load member cache, but continue if it fails
        try:
            fetch_and_cache_members(workspace_slug, project_id, api_key)
        except Exception:
            # Continue even if member cache fails
            pass

        # Sort issues by sequence_id
        issues.sort(key=lambda x: x.get("sequence_id", 0))

        if group.strip():
            group = group.strip().lower()

        # Format the issues as a table
        result = f"# Issues in {project_config.get('name', 'Unknown')}\n\n"
        result += "| ID | Title | Status | Priority | Assignee |\n"
        result += "|----|-------|--------|----------|----------|\n"

        for issue in issues:
            issue_name = issue.get("name", "Untitled")
            sequence_id = issue.get("sequence_id", "?")

            # Get state from cache
            state_id = issue.get("state")
            state_name = "Unknown"
            if state_id:
                state_name = (
                    get_state_name_by_id(workspace_slug, project_id, state_id, api_key)
                    or "Unknown"
                )
            if group and not state_name == group:
                continue

            priority = issue.get("priority", "None")

            # Handle assignee information (with caching)
            assignee_id = issue.get("assignee")
            assignee_name = "Unassigned"
            if assignee_id:
                member_details = get_member_by_id(
                    workspace_slug, project_id, assignee_id, api_key
                )
                if member_details and member_details.get("name"):
                    assignee_name = member_details.get("name")
                else:
                    # Fall back to the details in the issue if cache lookup fails
                    assignee_name = issue.get("assignee_detail", {}).get(
                        "display_name", f"User {assignee_id}"
                    )

            result += f"| {project_config.get('identifier', '')}-{sequence_id} | {issue_name} | {state_name} | {priority} | {assignee_name} |\n"

        return result

    except Exception as e:
        return f"Error listing issues: {str(e)}"


@tool
def create_issue(
    context: "AgentContext",
    title: str,
    description: str,
    priority: Optional[str] = "none",
    project_name: Optional[str] = None,
) -> str:
    """Create a new issue in a project.

    Creates a new issue with the specified title, description, and optional priority.

    Args:
        title: The title of the issue
        description: The description of the issue
        priority: The priority of the issue (urgent, high, medium, low, or none)
        project_name: Optional project name to specify which project to create the issue in.
                     If not provided, will use the current git repository or directory.
    """
    # Check if project is configured
    project_config = get_project_from_config(repo_name=project_name)
    if not project_config:
        return "Error: Issue tracking is not configured. Please run '/config issues' first."

    # Validate priority
    valid_priorities = ["urgent", "high", "medium", "low", "none"]
    if priority.lower() not in valid_priorities:
        return f"Error: Invalid priority. Must be one of: {', '.join(valid_priorities)}"

    try:
        workspace_slug = project_config["workspace"]
        project_id = project_config["_id"]

        # Prepare issue data
        issue_data = {
            "name": title,
            "description_html": description,
            "priority": priority.lower(),
        }

        # Create the issue
        endpoint = f"/api/v1/workspaces/{workspace_slug}/projects/{project_id}/issues/"
        response = _make_plane_request("POST", endpoint, data=issue_data)

        if "id" in response:
            sequence_id = response.get("sequence_id")
            identifier = project_config.get("identifier", "")
            return f"Issue created successfully: {identifier}-{sequence_id}: {title}"
        else:
            return "Error creating issue: Unexpected response format"

    except Exception as e:
        return f"Error creating issue: {str(e)}"


@tool
def update_issue(
    context: "AgentContext",
    issue_id: str,
    title: Optional[str] = None,
    description: Optional[str] = None,
    priority: Optional[str] = None,
    state: Optional[str] = None,
) -> str:
    """Update an existing issue.

    Updates an issue with the specified fields. Only fields that are provided will be updated.

    Args:
        issue_id: The issue identifier in the format <project-identifier>-<issue-number> (e.g., PROJ-123)
        title: Optional new title for the issue
        description: Optional new description for the issue
        priority: Optional new priority (urgent, high, medium, low, or none)
        state: Optional new state (case-insensitive name like "done", "in progress", etc.)
    """
    # Check if project is configured
    project_config = get_project_from_config()
    if not project_config:
        return "Error: Issue tracking is not configured. Please run '/config issues' first."

    # Validate priority if provided
    if priority:
        valid_priorities = ["urgent", "high", "medium", "low", "none"]
        if priority.lower() not in valid_priorities:
            return f"Error: Invalid priority. Must be one of: {', '.join(valid_priorities)}"

    try:
        # Load the issue to get its id
        issue = load_issue(issue_id)
        issue_id_uuid = issue["id"]

        workspace_slug = project_config["workspace"]
        project_id = project_config["_id"]
        api_key = project_config.get("api_key")

        # Prepare update data with only the fields that are provided
        update_data = {}
        if title:
            update_data["name"] = title
        if description:
            update_data["description_html"] = description
        if priority:
            update_data["priority"] = priority.lower()
        if state:
            # Convert state name to state ID using the cache
            state_id = get_state_id_by_name(workspace_slug, project_id, state, api_key)
            if not state_id:
                return f"Error: Could not find state with name '{state}'. Please use a valid state name."
            update_data["state"] = state_id

        if not update_data:
            return "Error: No fields provided to update"

        # Update the issue
        endpoint = f"/api/v1/workspaces/{workspace_slug}/projects/{project_id}/issues/{issue_id_uuid}/"
        response = _make_plane_request("PATCH", endpoint, data=update_data)

        if "id" in response:
            return f"Issue {issue_id} updated successfully"
        else:
            return "Error updating issue: Unexpected response format"

    except Exception as e:
        return f"Error updating issue: {str(e)}"


@tool
def comment_on_issue(context: "AgentContext", issue_id: str, comment: str) -> str:
    """Add a comment to an issue.

    Adds a new comment to the specified issue.

    Args:
        issue_id: The issue identifier in the format <project-identifier>-<issue-number> (e.g., PROJ-123)
        comment: The comment text to add
    """
    # Check if project is configured
    project_config = get_project_from_config()
    if not project_config:
        return "Error: Issue tracking is not configured. Please run '/config issues' first."

    try:
        # Load the issue to get its id
        issue = load_issue(issue_id)
        issue_id_uuid = issue["id"]

        workspace_slug = project_config["workspace"]
        project_id = project_config["_id"]

        # Prepare comment data according to the API documentation
        comment_data = {
            "comment_html": comment,  # Required field per documentation
        }

        # Add the comment
        endpoint = f"/api/v1/workspaces/{workspace_slug}/projects/{project_id}/issues/{issue_id_uuid}/comments/"
        response = _make_plane_request("POST", endpoint, data=comment_data)
        # Check for different possible success responses
        if "id" in response:
            return f"Comment added successfully to issue {issue_id}"
        elif "results" in response and len(response["results"]) > 0:
            return f"Comment added successfully to issue {issue_id}"
        else:
            error_details = (
                json.dumps(response)
                if isinstance(response, dict)
                else "Unexpected response format"
            )
            return f"Error adding comment: {error_details}"

    except Exception as e:
        return f"Error adding comment: {str(e)}"


@tool
def refresh_plane_cache(
    context: "AgentContext", project_name: Optional[str] = None
) -> str:
    """Refresh the Plane.so cache.

    Refreshes the local cache of Plane.so entities like states and priorities.
    This is useful if changes have been made in Plane.so that aren't reflected in the CLI.

    Args:
        project_name: Optional project name to specify which project's cache to refresh.
                     If not provided, will use the current git repository or directory.
    """
    # Check if project is configured
    project_config = get_project_from_config(repo_name=project_name)
    if not project_config:
        return "Error: Issue tracking is not configured. Please run '/config issues' first."

    try:
        workspace_slug = project_config["workspace"]
        project_id = project_config["_id"]
        api_key = project_config.get("api_key")

        # Refresh all caches
        results = refresh_all_caches(workspace_slug, project_id, api_key)

        # Format results
        success_count = sum(1 for v in results.values() if isinstance(v, bool) and v)
        total_count = sum(1 for v in results.values() if isinstance(v, bool))

        result_str = f"Cache refresh: {success_count}/{total_count} successful\n\n"

        for entity_type, success in results.items():
            if isinstance(success, bool):
                status = "✅ Success" if success else "❌ Failed"
                result_str += f"- {entity_type}: {status}\n"
                if not success and f"{entity_type}_error" in results:
                    result_str += f"  Error: {results[f'{entity_type}_error']}\n"

        return result_str

    except Exception as e:
        return f"Error refreshing cache: {str(e)}"


# List of all tools for export
PLANE_TOOLS = [
    get_issue,
    list_issues,
    create_issue,
    update_issue,
    comment_on_issue,
    refresh_plane_cache,
]
