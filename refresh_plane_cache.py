#!/usr/bin/env python

from heare.developer.clients.plane_so import get_project_from_config
from heare.developer.clients.plane_cache import refresh_all_caches


def main():
    """Refresh the Plane.so cache."""
    project_config = get_project_from_config()
    if not project_config:
        print(
            "Error: Issue tracking is not configured. Please run '/config issues' first."
        )
        return

    workspace_slug = project_config["workspace"]
    project_id = project_config["_id"]
    api_key = project_config.get("api_key")

    print(f"Refreshing cache for project {project_config.get('name', 'Unknown')}...")
    results = refresh_all_caches(workspace_slug, project_id, api_key)

    # Format results
    success_count = sum(1 for v in results.values() if isinstance(v, bool) and v)
    total_count = sum(1 for v in results.values() if isinstance(v, bool))

    print(f"Cache refresh: {success_count}/{total_count} successful")

    for entity_type, success in results.items():
        if isinstance(success, bool):
            status = "✅ Success" if success else "❌ Failed"
            print(f"- {entity_type}: {status}")
            if not success and f"{entity_type}_error" in results:
                print(f"  Error: {results[f'{entity_type}_error']}")


if __name__ == "__main__":
    main()
