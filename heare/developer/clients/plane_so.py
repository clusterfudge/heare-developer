import json
import os
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional, List

import requests
import yaml

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
    if result:
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
    if not project_config:
        raise ValueError(
            "Plane API key not found. Please set PLANE_API_KEY environment variable or create ~/.plane-secret file."
        )

    api_key = project_config.get("api_key")

    # If still no API key, raise an error
    if not project_config:
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

    except Exception as e:
        error_msg = f"Error making request to Plane.so API: {str(e)}"
        if (
            isinstance(e, requests.exceptions.RequestException)
            and response
            and response.text
        ):
            try:
                error_details = response.json()
                error_msg = f"{error_msg}. Details: {json.dumps(error_details)}"
            except Exception:
                pass

        raise Exception(error_msg)


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
    return _make_plane_request("GET", endpoint, api_key=api_key)


def get_issue_project_by_id(
    workspace_slug: str, project_id: str, api_key: str
) -> Dict[str, Any]:
    """Get details for a project by its ID."""

    endpoint = f"/api/v1/workspaces/{workspace_slug}/projects/{project_id}"
    return _make_plane_request("GET", endpoint)


def get_issue_comments(
    workspace_slug: str, project_id: str, issue_id: str, api_key: str = None
) -> List[Dict[str, Any]]:
    """Get comments for an issue."""

    endpoint = f"/api/v1/workspaces/{workspace_slug}/projects/{project_id}/issues/{issue_id}/comments"
    return _make_plane_request("GET", endpoint, api_key=api_key)["results"]


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

    endpoint = f"/api/v1/workspaces/{workspace_slug}/projects/"
    try:
        response = _make_plane_request("POST", endpoint, data=data, api_key=api_key)
        return response.get("id")
    except Exception:
        return None


def load_issue(sequence_id: str, **_):
    """Load a specific issue by its project prefix and issue number.

    Args:
        sequence_id: An issue identifier that maps to <project-identifier>-<issue number>

    This function directly loads a specific issue based on the project prefix and issue number.
    It bypasses the project and issue selection process.
    """
    config = read_config()

    # Check if issues are configured
    if not config.get("projects"):
        raise ValueError(
            "Issue tracking is not configured yet. Please run '/config issues' first."
        )

    project = get_project_from_config()
    endpoint = f"/api/v1/workspaces/{project['workspace']}/issues/{sequence_id}"
    return _make_plane_request("GET", endpoint)
