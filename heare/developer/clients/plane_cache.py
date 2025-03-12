"""
Cache module for Plane.so entities.

This module provides caching for Plane.so entities like states, priorities, users, and other reference data
to avoid repeated API calls and to provide a lookup mechanism for IDs and labels.

The Plane.so API typically returns UUIDs instead of full details for related resources. This cache
helps resolve those UUIDs to their full details without making additional API calls for each entity.
"""

import json
import os
import time
from typing import Dict, Any, Optional

from .plane_so import _make_plane_request

# Cache directory
CACHE_DIR = os.path.expanduser("~/.cache/hdev/plane.so")
CACHE_TTL = 86400  # 24 hours in seconds


def ensure_cache_dir():
    """Ensure the cache directory exists."""
    os.makedirs(CACHE_DIR, exist_ok=True)


def get_cache_path(workspace_slug: str, project_id: str, entity_type: str) -> str:
    """
    Get the path for a cached entity.

    Args:
        workspace_slug: The workspace slug
        project_id: The project ID
        entity_type: The entity type (e.g., 'states', 'priorities')

    Returns:
        The path to the cached file
    """
    ensure_cache_dir()
    return os.path.join(CACHE_DIR, f"{workspace_slug}_{project_id}_{entity_type}.json")


def cache_is_valid(cache_path: str) -> bool:
    """
    Check if a cache file is valid (exists and is not too old).

    Args:
        cache_path: Path to the cache file

    Returns:
        True if the cache is valid, False otherwise
    """
    if not os.path.exists(cache_path):
        return False

    # Check if cache is too old
    file_mtime = os.path.getmtime(cache_path)
    current_time = time.time()
    return (current_time - file_mtime) < CACHE_TTL


def read_cache(
    workspace_slug: str, project_id: str, entity_type: str
) -> Optional[Dict[str, Any]]:
    """
    Read data from cache.

    Args:
        workspace_slug: The workspace slug
        project_id: The project ID
        entity_type: The entity type (e.g., 'states', 'priorities')

    Returns:
        The cached data or None if cache doesn't exist or is invalid
    """
    cache_path = get_cache_path(workspace_slug, project_id, entity_type)

    if not cache_is_valid(cache_path):
        return None

    try:
        with open(cache_path, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return None


def write_cache(
    workspace_slug: str, project_id: str, entity_type: str, data: Dict[str, Any]
):
    """
    Write data to cache.

    Args:
        workspace_slug: The workspace slug
        project_id: The project ID
        entity_type: The entity type (e.g., 'states', 'priorities')
        data: The data to cache
    """
    cache_path = get_cache_path(workspace_slug, project_id, entity_type)

    with open(cache_path, "w") as f:
        json.dump(data, f, indent=2)


def fetch_and_cache_states(
    workspace_slug: str, project_id: str, api_key: str, force_refresh: bool = False
) -> Dict[str, Any]:
    """
    Fetch and cache states for a project.

    Args:
        workspace_slug: The workspace slug
        project_id: The project ID
        api_key: The API key for Plane.so
        force_refresh: Force refresh the cache even if it's valid

    Returns:
        The fetched states
    """
    entity_type = "states"
    cache_path = get_cache_path(workspace_slug, project_id, entity_type)

    # Check cache first if not forcing refresh
    if not force_refresh and cache_is_valid(cache_path):
        cached_data = read_cache(workspace_slug, project_id, entity_type)
        if cached_data:
            return cached_data

    # Fetch states from API
    endpoint = f"/api/v1/workspaces/{workspace_slug}/projects/{project_id}/states"
    response = _make_plane_request("GET", endpoint, api_key=api_key)

    # Create a lookup dict with both name->id and id->name mappings
    states = {}

    # First, add raw results for completeness
    states["raw_results"] = response.get("results", [])

    # Then add lookup maps
    name_to_id = {}
    id_to_details = {}

    for state in response.get("results", []):
        state_id = state.get("id")
        state_name = state.get("name")

        if state_id and state_name:
            name_to_id[state_name.lower()] = state_id
            name_to_id[state_name] = state_id  # Also store with original case
            id_to_details[state_id] = {
                "name": state_name,
                "group": state.get("group"),
                "color": state.get("color"),
                "slug": state.get("slug"),
            }

    states["name_to_id"] = name_to_id
    states["id_to_details"] = id_to_details

    # Cache the results
    write_cache(workspace_slug, project_id, entity_type, states)

    return states


def fetch_and_cache_priorities(
    workspace_slug: str, project_id: str, api_key: str, force_refresh: bool = False
) -> Dict[str, Any]:
    """
    Fetch and cache priorities.
    Note: Priorities might be project-specific or workspace-wide depending on Plane.so setup.

    Args:
        workspace_slug: The workspace slug
        project_id: The project ID
        api_key: The API key for Plane.so
        force_refresh: Force refresh the cache even if it's valid

    Returns:
        The fetched priorities
    """
    entity_type = "priorities"
    cache_path = get_cache_path(workspace_slug, project_id, entity_type)

    # Check cache first if not forcing refresh
    if not force_refresh and cache_is_valid(cache_path):
        cached_data = read_cache(workspace_slug, project_id, entity_type)
        if cached_data:
            return cached_data

    # Basic priorities that are commonly used
    # Plane.so might not have an API for priorities, so we'll hard-code common ones
    priorities = {
        "name_to_id": {
            "urgent": "urgent",
            "high": "high",
            "medium": "medium",
            "low": "low",
            "none": "none",
        },
        "id_to_details": {
            "urgent": {"name": "Urgent", "color": "#FF5630"},
            "high": {"name": "High", "color": "#FF9800"},
            "medium": {"name": "Medium", "color": "#0069FF"},
            "low": {"name": "Low", "color": "#8DA2C0"},
            "none": {"name": "None", "color": "#6B6F76"},
        },
    }

    # Cache the results
    write_cache(workspace_slug, project_id, entity_type, priorities)

    return priorities


def fetch_and_cache_members(
    workspace_slug: str, project_id: str, api_key: str, force_refresh: bool = False
) -> Dict[str, Any]:
    """
    Fetch and cache workspace members.

    Args:
        workspace_slug: The workspace slug
        project_id: The project ID
        api_key: The API key for Plane.so
        force_refresh: Force refresh the cache even if it's valid

    Returns:
        The fetched members
    """
    entity_type = "members"
    cache_path = get_cache_path(workspace_slug, project_id, entity_type)

    # Check cache first if not forcing refresh
    if not force_refresh and cache_is_valid(cache_path):
        cached_data = read_cache(workspace_slug, project_id, entity_type)
        if cached_data:
            return cached_data

    # Fetch members from API
    endpoint = f"/api/workspaces/{workspace_slug}/members"
    try:
        response = _make_plane_request("GET", endpoint, api_key=api_key)
    except Exception:
        # Try the alternative endpoint format
        endpoint = f"/api/v1/workspaces/{workspace_slug}/members"
        response = _make_plane_request("GET", endpoint, api_key=api_key)

    # Create a lookup dict with both name->id and id->name mappings
    members = {}

    # Handle response format - could be either a list or a dictionary with "results" key
    if isinstance(response, dict) and "results" in response:
        members_list = response.get("results", [])
    else:
        members_list = response if isinstance(response, list) else []

    # First, add raw results for completeness
    members["raw_results"] = members_list

    # Then add lookup maps
    id_to_details = {}
    email_to_id = {}
    name_to_id = {}

    for member in members_list:
        if not isinstance(member, dict):
            continue

        member_id = member.get("id")
        email = member.get("email")
        name = (
            member.get("display_name")
            or member.get("first_name", "")
            or member.get("username", "")
        )

        if member_id:
            id_to_details[member_id] = {
                "email": email,
                "name": name,
                "avatar": member.get("avatar"),
                "role": member.get("role"),
                "user_id": member.get("id"),
            }

            if email:
                email_to_id[email] = member_id

            if name:
                name_to_id[name] = member_id

    members["id_to_details"] = id_to_details
    members["email_to_id"] = email_to_id
    members["name_to_id"] = name_to_id

    # Cache the results
    write_cache(workspace_slug, project_id, entity_type, members)

    return members


def refresh_all_caches(
    workspace_slug: str, project_id: str, api_key: str
) -> Dict[str, bool]:
    """
    Refresh all caches for a project.

    Args:
        workspace_slug: The workspace slug
        project_id: The project ID
        api_key: The API key for Plane.so

    Returns:
        A dictionary indicating which caches were refreshed successfully
    """
    results = {}

    try:
        fetch_and_cache_states(workspace_slug, project_id, api_key, force_refresh=True)
        results["states"] = True
    except Exception as e:
        results["states"] = False
        results["states_error"] = str(e)

    try:
        fetch_and_cache_priorities(
            workspace_slug, project_id, api_key, force_refresh=True
        )
        results["priorities"] = True
    except Exception as e:
        results["priorities"] = False
        results["priorities_error"] = str(e)

    try:
        fetch_and_cache_members(workspace_slug, project_id, api_key, force_refresh=True)
        results["members"] = True
    except Exception as e:
        results["members"] = False
        results["members_error"] = str(e)

    return results


def get_state_id_by_name(
    workspace_slug: str, project_id: str, state_name: str, api_key: str
) -> Optional[str]:
    """
    Get a state ID by its name.

    Args:
        workspace_slug: The workspace slug
        project_id: The project ID
        state_name: The state name (case-insensitive)
        api_key: The API key for Plane.so

    Returns:
        The state ID or None if not found
    """
    states = fetch_and_cache_states(workspace_slug, project_id, api_key)

    # Try exact match first (case insensitive)
    name_to_id = states.get("name_to_id", {})
    state_id = name_to_id.get(state_name.lower())

    if state_id:
        return state_id

    # Try partial match
    for name, id in name_to_id.items():
        if state_name.lower() in name.lower():
            return id

    return None


def get_state_name_by_id(
    workspace_slug: str, project_id: str, state_id: str, api_key: str
) -> Optional[str]:
    """
    Get a state name by its ID.

    Args:
        workspace_slug: The workspace slug
        project_id: The project ID
        state_id: The state ID
        api_key: The API key for Plane.so

    Returns:
        The state name or None if not found
    """
    states = fetch_and_cache_states(workspace_slug, project_id, api_key)

    id_to_details = states.get("id_to_details", {})
    state_details = id_to_details.get(state_id)

    if state_details:
        return state_details.get("name")

    return None


def get_member_by_id(
    workspace_slug: str, project_id: str, member_id: str, api_key: str
) -> Optional[Dict[str, Any]]:
    """
    Get member details by their ID.

    Args:
        workspace_slug: The workspace slug
        project_id: The project ID
        member_id: The member ID
        api_key: The API key for Plane.so

    Returns:
        The member details or None if not found
    """
    members = fetch_and_cache_members(workspace_slug, project_id, api_key)

    id_to_details = members.get("id_to_details", {})
    return id_to_details.get(member_id)


def get_member_by_email(
    workspace_slug: str, project_id: str, email: str, api_key: str
) -> Optional[Dict[str, Any]]:
    """
    Get member details by their email.

    Args:
        workspace_slug: The workspace slug
        project_id: The project ID
        email: The member's email
        api_key: The API key for Plane.so

    Returns:
        The member details or None if not found
    """
    members = fetch_and_cache_members(workspace_slug, project_id, api_key)

    email_to_id = members.get("email_to_id", {})
    member_id = email_to_id.get(email)

    if member_id:
        return get_member_by_id(workspace_slug, project_id, member_id, api_key)

    return None


def get_member_by_name(
    workspace_slug: str, project_id: str, name: str, api_key: str
) -> Optional[Dict[str, Any]]:
    """
    Get member details by their name.

    Args:
        workspace_slug: The workspace slug
        project_id: The project ID
        name: The member's display name
        api_key: The API key for Plane.so

    Returns:
        The member details or None if not found
    """
    members = fetch_and_cache_members(workspace_slug, project_id, api_key)

    name_to_id = members.get("name_to_id", {})
    member_id = name_to_id.get(name)

    if member_id:
        return get_member_by_id(workspace_slug, project_id, member_id, api_key)

    return None


def clear_cache(
    workspace_slug: Optional[str] = None,
    project_id: Optional[str] = None,
    entity_type: Optional[str] = None,
):
    """
    Clear the cache.

    Args:
        workspace_slug: Optional workspace slug to filter by
        project_id: Optional project ID to filter by
        entity_type: Optional entity type to filter by
    """
    ensure_cache_dir()

    # Build a pattern based on the parameters
    pattern = ""
    if workspace_slug:
        pattern += f"{workspace_slug}_"
    if project_id:
        pattern += f"{project_id}_"
    if entity_type:
        pattern += f"{entity_type}"

    # If all parameters are provided, delete a specific file
    if workspace_slug and project_id and entity_type:
        cache_path = get_cache_path(workspace_slug, project_id, entity_type)
        if os.path.exists(cache_path):
            os.remove(cache_path)
        return

    # Otherwise, delete files matching the pattern
    for filename in os.listdir(CACHE_DIR):
        if pattern and not filename.startswith(pattern):
            continue

        file_path = os.path.join(CACHE_DIR, filename)
        if os.path.isfile(file_path):
            os.remove(file_path)
