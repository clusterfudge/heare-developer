"""
Plane.so API integration tools for task management.
Provides tools to interact with Plane.so project management platform.
"""

import os
import json
from typing import Optional, Dict, Any
import requests

from heare.developer.context import AgentContext
# We'll define our own tool decorator to avoid circular imports

from .framework import tool


def _get_plane_api_key() -> str:
    """
    Get the Plane.so API key from environment variables or from the ~/.plane-secret file.

    Returns:
        str: The API key for Plane.so

    Raises:
        ValueError: If API key is not found
    """
    # Check environment variable first
    api_key = os.environ.get("PLANE_API_KEY")

    # If not in environment variable, check the file
    if not api_key:
        try:
            api_key_path = os.path.expanduser("~/.plane-secret")
            if os.path.exists(api_key_path):
                with open(api_key_path, "r") as f:
                    api_key = f.read().strip()
        except Exception as e:
            raise ValueError(f"Error reading Plane API key from file: {str(e)}")

    # If still no API key, raise an error
    if not api_key:
        raise ValueError(
            "Plane API key not found. Please set PLANE_API_KEY environment variable or create ~/.plane-secret file."
        )

    return api_key


def _get_plane_headers() -> Dict[str, str]:
    """
    Get headers for Plane.so API requests including the API key.

    Returns:
        Dict[str, str]: Headers dictionary with API key
    """
    api_key = _get_plane_api_key()
    return {
        "x-api-key": {api_key},
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def _make_plane_request(
    method: str,
    endpoint: str,
    data: Optional[Dict[str, Any]] = None,
    params: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None,
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

    if headers is None:
        headers = _get_plane_headers()

    try:
        response = requests.request(
            method=method,
            url=url,
            headers=headers,
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
            if response.text:
                error_details = response.json()
                error_msg = f"{error_msg}. Details: {json.dumps(error_details)}"
        except Exception:
            raise

        raise Exception(error_msg)


@tool
def list_plane_workspaces(context: "AgentContext") -> str:
    """List all workspaces accessible to the authenticated user in Plane.so.

    Returns a list of workspaces with their details.

    Args:
        context: The agent's context
    """
    try:
        response = _make_plane_request("GET", "/api/v1/workspaces/")

        if not response:
            return "No workspaces found."

        result = "Available workspaces:\n"
        for workspace in response:
            result += f"- Name: {workspace.get('name')}\n"
            result += f"  Slug: {workspace.get('slug')}\n"
            result += f"  ID: {workspace.get('id')}\n"
            result += f"  Created: {workspace.get('created_at')}\n"
            result += "\n"

        return result
    except Exception as e:
        return f"Error listing workspaces: {str(e)}"


@tool
def list_plane_projects(context: "AgentContext", workspace_slug: str) -> str:
    """List all projects in a specific workspace in Plane.so.

    Args:
        context: The agent's context
        workspace_slug: The slug identifier of the workspace
    """
    try:
        endpoint = f"/api/v1/workspaces/{workspace_slug}/projects/"
        response = _make_plane_request("GET", endpoint)

        if not response:
            return f"No projects found in workspace '{workspace_slug}'."

        result = f"Projects in workspace '{workspace_slug}':\n"
        for project in response:
            result += f"- Name: {project.get('name')}\n"
            result += f"  ID: {project.get('id')}\n"
            result += f"  Identifier: {project.get('identifier')}\n"
            result += f"  Description: {project.get('description', 'N/A')}\n"
            result += "\n"

        return result
    except Exception as e:
        return f"Error listing projects: {str(e)}"


@tool
def get_plane_project_details(
    context: "AgentContext", workspace_slug: str, project_id: str
) -> str:
    """Get details of a specific project in Plane.so.

    Args:
        context: The agent's context
        workspace_slug: The slug identifier of the workspace
        project_id: The ID of the project
    """
    try:
        endpoint = f"/api/v1/workspaces/{workspace_slug}/projects/{project_id}/"
        response = _make_plane_request("GET", endpoint)

        if not response:
            return f"No project found with ID '{project_id}'."

        result = "Project Details:\n"
        result += f"- Name: {response.get('name')}\n"
        result += f"- ID: {response.get('id')}\n"
        result += f"- Identifier: {response.get('identifier')}\n"
        result += f"- Description: {response.get('description', 'N/A')}\n"
        result += f"- Network: {response.get('network', 'N/A')}\n"
        result += f"- Created: {response.get('created_at')}\n"
        result += f"- Updated: {response.get('updated_at')}\n"

        return result
    except Exception as e:
        return f"Error getting project details: {str(e)}"


@tool
def create_plane_project(
    context: "AgentContext",
    workspace_slug: str,
    name: str,
    identifier: str,
    description: Optional[str] = None,
) -> str:
    """Create a new project in Plane.so.

    Args:
        context: The agent's context
        workspace_slug: The slug identifier of the workspace
        name: The name of the project
        identifier: The unique identifier for the project (usually a short code)
        description: Optional description for the project
    """
    try:
        endpoint = f"/api/v1/workspaces/{workspace_slug}/projects/"

        data = {
            "name": name,
            "identifier": identifier,
        }

        if description:
            data["description"] = description

        response = _make_plane_request("POST", endpoint, data=data)

        return f"Project created successfully!\nName: {response.get('name')}\nID: {response.get('id')}\nIdentifier: {response.get('identifier')}"
    except Exception as e:
        return f"Error creating project: {str(e)}"


@tool
def list_plane_issues(
    context: "AgentContext",
    workspace_slug: str,
    project_id: str,
    state_id: Optional[str] = None,
) -> str:
    """List all issues in a specific project in Plane.so.

    Args:
        context: The agent's context
        workspace_slug: The slug identifier of the workspace
        project_id: The ID of the project
        state_id: Optional filter for issues by state ID
    """
    try:
        endpoint = f"/api/v1/workspaces/{workspace_slug}/projects/{project_id}/issues/"

        params = {}
        if state_id:
            params["state_id"] = state_id

        response = _make_plane_request("GET", endpoint, params=params)

        if not response:
            return f"No issues found in project '{project_id}'."

        result = f"Issues in project '{project_id}':\n"
        for issue in response:
            result += f"- ID: {issue.get('id')}\n"
            result += f"  Title: {issue.get('name')}\n"
            result += (
                f"  State: {issue.get('state_detail', {}).get('name', 'Unknown')}\n"
            )
            result += f"  Priority: {issue.get('priority', 'None')}\n"
            result += f"  Assignee: {issue.get('assignee_detail', {}).get('display_name', 'Unassigned')}\n"
            result += f"  Created: {issue.get('created_at')}\n"
            result += "\n"

        return result
    except Exception as e:
        return f"Error listing issues: {str(e)}"


@tool
def get_plane_issue_details(
    context: "AgentContext", workspace_slug: str, project_id: str, issue_id: str
) -> str:
    """Get detailed information about a specific issue in Plane.so.

    Args:
        context: The agent's context
        workspace_slug: The slug identifier of the workspace
        project_id: The ID of the project
        issue_id: The ID of the issue
    """
    try:
        endpoint = f"/api/v1/workspaces/{workspace_slug}/projects/{project_id}/issues/{issue_id}/"
        response = _make_plane_request("GET", endpoint)

        if not response:
            return f"No issue found with ID '{issue_id}'."

        result = "Issue Details:\n"
        result += f"- Title: {response.get('name')}\n"
        result += f"- ID: {response.get('id')}\n"
        result += f"- Description: {response.get('description', 'N/A')}\n"
        result += (
            f"- State: {response.get('state_detail', {}).get('name', 'Unknown')}\n"
        )
        result += f"- Priority: {response.get('priority', 'None')}\n"
        result += f"- Assignee: {response.get('assignee_detail', {}).get('display_name', 'Unassigned')}\n"
        result += f"- Created: {response.get('created_at')}\n"
        result += f"- Updated: {response.get('updated_at')}\n"

        # Get linked issues if any
        if response.get("link_count", 0) > 0:
            try:
                link_endpoint = f"/api/v1/workspaces/{workspace_slug}/projects/{project_id}/issues/{issue_id}/links/"
                links_response = _make_plane_request("GET", link_endpoint)
                if links_response:
                    result += "\nLinked Issues:\n"
                    for link in links_response:
                        result += f"- {link.get('title')} (ID: {link.get('id')}, Relation: {link.get('relation')})\n"
            except Exception as link_error:
                result += f"\nError fetching linked issues: {str(link_error)}\n"

        # Get subtasks if any
        if response.get("sub_issues_count", 0) > 0:
            try:
                subtask_endpoint = f"/api/v1/workspaces/{workspace_slug}/projects/{project_id}/issues/{issue_id}/sub-issues/"
                subtasks_response = _make_plane_request("GET", subtask_endpoint)
                if subtasks_response:
                    result += "\nSubtasks:\n"
                    for subtask in subtasks_response:
                        result += f"- {subtask.get('name')} (ID: {subtask.get('id')})\n"
            except Exception as subtask_error:
                result += f"\nError fetching subtasks: {str(subtask_error)}\n"

        return result
    except Exception as e:
        return f"Error getting issue details: {str(e)}"


@tool
def create_plane_issue(
    context: "AgentContext",
    workspace_slug: str,
    project_id: str,
    name: str,
    description: Optional[str] = None,
    state_id: Optional[str] = None,
    priority: Optional[str] = None,
    assignee_id: Optional[str] = None,
) -> str:
    """Create a new issue in a Plane.so project.

    Args:
        context: The agent's context
        workspace_slug: The slug identifier of the workspace
        project_id: The ID of the project
        name: The title/name of the issue
        description: Optional description of the issue
        state_id: Optional state ID for the issue
        priority: Optional priority (urgent, high, medium, low, none)
        assignee_id: Optional user ID to assign the issue to
    """
    try:
        endpoint = f"/api/v1/workspaces/{workspace_slug}/projects/{project_id}/issues/"

        data = {
            "name": name,
        }

        if description:
            data["description"] = description
        if state_id:
            data["state_id"] = state_id
        if priority:
            if priority.lower() in ["urgent", "high", "medium", "low", "none"]:
                data["priority"] = priority.lower()
            else:
                return f"Invalid priority '{priority}'. Must be one of: urgent, high, medium, low, none"
        if assignee_id:
            data["assignee_id"] = assignee_id

        response = _make_plane_request("POST", endpoint, data=data)

        return f"Issue created successfully!\nTitle: {response.get('name')}\nID: {response.get('id')}"
    except Exception as e:
        return f"Error creating issue: {str(e)}"


@tool
def update_plane_issue(
    context: "AgentContext",
    workspace_slug: str,
    project_id: str,
    issue_id: str,
    name: Optional[str] = None,
    description: Optional[str] = None,
    state_id: Optional[str] = None,
    priority: Optional[str] = None,
    assignee_id: Optional[str] = None,
) -> str:
    """Update an existing issue in a Plane.so project.

    Args:
        context: The agent's context
        workspace_slug: The slug identifier of the workspace
        project_id: The ID of the project
        issue_id: The ID of the issue to update
        name: Optional new title/name of the issue
        description: Optional new description of the issue
        state_id: Optional new state ID for the issue
        priority: Optional new priority (urgent, high, medium, low, none)
        assignee_id: Optional new user ID to assign the issue to
    """
    try:
        endpoint = f"/api/v1/workspaces/{workspace_slug}/projects/{project_id}/issues/{issue_id}/"

        data = {}

        if name:
            data["name"] = name
        if description:
            data["description"] = description
        if state_id:
            data["state_id"] = state_id
        if priority:
            if priority.lower() in ["urgent", "high", "medium", "low", "none"]:
                data["priority"] = priority.lower()
            else:
                return f"Invalid priority '{priority}'. Must be one of: urgent, high, medium, low, none"
        if assignee_id:
            data["assignee_id"] = assignee_id

        # If no fields to update were provided
        if not data:
            return "No fields provided for update."

        response = _make_plane_request("PATCH", endpoint, data=data)

        return f"Issue updated successfully!\nTitle: {response.get('name')}\nID: {response.get('id')}"
    except Exception as e:
        return f"Error updating issue: {str(e)}"


@tool
def add_plane_issue_comment(
    context: "AgentContext",
    workspace_slug: str,
    project_id: str,
    issue_id: str,
    comment_text: str,
) -> str:
    """Add a comment to an issue in Plane.so.

    Args:
        context: The agent's context
        workspace_slug: The slug identifier of the workspace
        project_id: The ID of the project
        issue_id: The ID of the issue
        comment_text: The text content of the comment
    """
    try:
        endpoint = f"/api/v1/workspaces/{workspace_slug}/projects/{project_id}/issues/{issue_id}/comments/"

        data = {
            "comment_html": comment_text,
            "comment": comment_text,  # Provide both formats
        }

        response = _make_plane_request("POST", endpoint, data=data)

        return f"Comment added successfully!\nComment ID: {response.get('id')}"
    except Exception as e:
        return f"Error adding comment: {str(e)}"


@tool
def create_plane_issue_link(
    context: "AgentContext",
    workspace_slug: str,
    project_id: str,
    issue_id: str,
    linked_issue_id: str,
    relation: str,
) -> str:
    """Create a link between two issues in Plane.so.

    Args:
        context: The agent's context
        workspace_slug: The slug identifier of the workspace
        project_id: The ID of the project
        issue_id: The ID of the issue
        linked_issue_id: The ID of the issue to link to
        relation: The relation type (e.g., "blocks", "is_blocked_by", "relates_to")
    """
    try:
        endpoint = f"/api/v1/workspaces/{workspace_slug}/projects/{project_id}/issues/{issue_id}/links/"

        # Valid relation types
        valid_relations = [
            "blocks",
            "is_blocked_by",
            "relates_to",
            "duplicates",
            "is_duplicated_by",
        ]

        if relation not in valid_relations:
            return f"Invalid relation type '{relation}'. Must be one of: {', '.join(valid_relations)}"

        data = {
            "issue": issue_id,
            "related_issue": linked_issue_id,
            "relation": relation,
        }

        response = _make_plane_request("POST", endpoint, data=data)

        return f"Issues linked successfully!\nLink ID: {response.get('id')}"
    except Exception as e:
        return f"Error linking issues: {str(e)}"


@tool
def create_plane_subtask(
    context: "AgentContext",
    workspace_slug: str,
    project_id: str,
    parent_issue_id: str,
    name: str,
    description: Optional[str] = None,
    state_id: Optional[str] = None,
    priority: Optional[str] = None,
    assignee_id: Optional[str] = None,
) -> str:
    """Create a subtask for an issue in Plane.so.

    Args:
        context: The agent's context
        workspace_slug: The slug identifier of the workspace
        project_id: The ID of the project
        parent_issue_id: The ID of the parent issue
        name: The title/name of the subtask
        description: Optional description of the subtask
        state_id: Optional state ID for the subtask
        priority: Optional priority (urgent, high, medium, low, none)
        assignee_id: Optional user ID to assign the subtask to
    """
    try:
        endpoint = f"/api/v1/workspaces/{workspace_slug}/projects/{project_id}/issues/{parent_issue_id}/sub-issues/"

        data = {"name": name, "parent": parent_issue_id, "project_id": project_id}

        if description:
            data["description"] = description
        if state_id:
            data["state_id"] = state_id
        if priority:
            if priority.lower() in ["urgent", "high", "medium", "low", "none"]:
                data["priority"] = priority.lower()
            else:
                return f"Invalid priority '{priority}'. Must be one of: urgent, high, medium, low, none"
        if assignee_id:
            data["assignee_id"] = assignee_id

        response = _make_plane_request("POST", endpoint, data=data)

        return f"Subtask created successfully!\nTitle: {response.get('name')}\nID: {response.get('id')}"
    except Exception as e:
        return f"Error creating subtask: {str(e)}"


@tool
def list_plane_states(
    context: "AgentContext", workspace_slug: str, project_id: str
) -> str:
    """List all states/statuses available in a project.

    Args:
        context: The agent's context
        workspace_slug: The slug identifier of the workspace
        project_id: The ID of the project
    """
    try:
        endpoint = f"/api/v1/workspaces/{workspace_slug}/projects/{project_id}/states/"
        response = _make_plane_request("GET", endpoint)

        if not response:
            return f"No states found in project '{project_id}'."

        result = f"States in project '{project_id}':\n"
        for state in response:
            result += f"- Name: {state.get('name')}\n"
            result += f"  ID: {state.get('id')}\n"
            result += f"  Group: {state.get('group')}\n"
            result += f"  Color: {state.get('color')}\n"
            result += "\n"

        return result
    except Exception as e:
        return f"Error listing states: {str(e)}"


@tool
def list_plane_members(context: "AgentContext", workspace_slug: str) -> str:
    """List all members in a workspace.

    Args:
        context: The agent's context
        workspace_slug: The slug identifier of the workspace
    """
    try:
        endpoint = f"/api/v1/workspaces/{workspace_slug}/members/"
        response = _make_plane_request("GET", endpoint)

        if not response:
            return f"No members found in workspace '{workspace_slug}'."

        result = f"Members in workspace '{workspace_slug}':\n"
        for member in response:
            user = member.get("member", {})
            result += f"- Name: {user.get('display_name')}\n"
            result += f"  ID: {user.get('id')}\n"
            result += f"  Email: {user.get('email')}\n"
            result += f"  Role: {member.get('role')}\n"
            result += "\n"

        return result
    except Exception as e:
        return f"Error listing members: {str(e)}"


# List of all Plane.so tools
PLANE_TOOLS = [
    list_plane_workspaces,
    list_plane_projects,
    get_plane_project_details,
    create_plane_project,
    list_plane_issues,
    get_plane_issue_details,
    create_plane_issue,
    update_plane_issue,
    add_plane_issue_comment,
    create_plane_issue_link,
    create_plane_subtask,
    list_plane_states,
    list_plane_members,
]
