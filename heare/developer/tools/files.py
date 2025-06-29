from typing import Optional

from heare.developer.context import AgentContext
from heare.developer.sandbox import DoSomethingElseError
from .framework import tool


@tool
async def read_file(context: "AgentContext", path: str):
    """Read and return the contents of a file from the sandbox.

    Args:
        path: Path to the file to read
    """
    try:
        return await context.sandbox.read_file(path)
    except PermissionError:
        return f"Error: No read permission for {path}"
    except DoSomethingElseError:
        raise  # Re-raise to be handled by higher-level components
    except Exception as e:
        return f"Error reading file: {str(e)}"


@tool(max_concurrency=1)
def write_file(context: "AgentContext", path: str, content: str):
    """Write content to a file in the sandbox.

    Args:
        path: Path where the file should be written
        content: Content to write to the file
    """
    try:
        context.sandbox.write_file(path, content)
        return "File written successfully"
    except PermissionError:
        return f"Error: No write permission for {path}"
    except DoSomethingElseError:
        raise  # Re-raise to be handled by higher-level components
    except Exception as e:
        return f"Error writing file: {str(e)}"


@tool
def list_directory(
    context: "AgentContext", path: str, recursive: Optional[bool] = None
):
    """List contents of a directory in the sandbox.

    Args:
        path: Path to the directory to list
        recursive: If True, list contents recursively (optional)
    """
    try:
        contents = context.sandbox.get_directory_listing(
            path, recursive=bool(recursive) if recursive is not None else False
        )

        result = f"Contents of {path}:\n"
        for item in contents:
            result += f"{item}\n"
        return result
    except Exception as e:
        return f"Error listing directory: {str(e)}"


@tool
def list_directory_with_details(
    context: "AgentContext", path: str, recursive: Optional[bool] = None
):
    """List contents of a directory with detailed metadata including symlink information.

    Args:
        path: Path to the directory to list
        recursive: If True, list contents recursively (optional)
    """
    try:
        contents = context.sandbox.get_directory_listing_with_metadata(
            path, recursive=bool(recursive) if recursive is not None else False
        )

        if not contents:
            return f"Directory {path} is empty or does not exist"

        result = f"Detailed contents of {path}:\n"
        for item in contents:
            name = item["name"]
            if item["is_symlink"]:
                target = item.get("symlink_target", "unknown")
                exists = " (broken)" if not item.get("symlink_exists", False) else ""
                result += f"{name} -> {target}{exists} [symlink]\n"
            else:
                result += f"{name}\n"
        return result
    except Exception as e:
        return f"Error listing directory: {str(e)}"


@tool
def is_symlink(context: "AgentContext", path: str):
    """Check if a path is a symbolic link.

    Args:
        path: Path to check
    """
    try:
        is_link = context.sandbox.is_symlink(path)
        return f"Path '{path}' is {'a symbolic link' if is_link else 'not a symbolic link'}"
    except Exception as e:
        return f"Error checking symlink status: {str(e)}"


@tool
def get_symlink_target(context: "AgentContext", path: str):
    """Get the target of a symbolic link.

    Args:
        path: Path to the symbolic link
    """
    try:
        target = context.sandbox.get_symlink_target(path)
        return f"Symlink '{path}' points to: {target}"
    except Exception as e:
        return f"Error getting symlink target: {str(e)}"


@tool
def resolve_symlink(context: "AgentContext", path: str):
    """Resolve a symbolic link to its final target path.

    Args:
        path: Path to resolve (can be a symlink or regular path)
    """
    try:
        resolved = context.sandbox.resolve_symlink_path(path)
        return f"Path '{path}' resolves to: {resolved}"
    except Exception as e:
        return f"Error resolving path: {str(e)}"


@tool(max_concurrency=1)
def create_symlink(context: "AgentContext", target_path: str, link_path: str):
    """Create a symbolic link.

    Args:
        target_path: Path that the symlink will point to
        link_path: Path where the symlink will be created
    """
    try:
        context.sandbox.create_symlink(target_path, link_path)
        return f"Created symlink '{link_path}' pointing to '{target_path}'"
    except PermissionError:
        return f"Error: No permission to create symlink '{link_path}'"
    except DoSomethingElseError:
        raise  # Re-raise to be handled by higher-level components
    except Exception as e:
        return f"Error creating symlink: {str(e)}"


@tool(max_concurrency=1)
async def edit_file(
    context: "AgentContext", path: str, match_text: str, replace_text: str
):
    """Make a targeted edit to a file in the sandbox by replacing specific text.

    Args:
        path: Path to the file to edit
        match_text: Text to find in the file
        replace_text: Text to replace the matched text with
    """
    try:
        content = await context.sandbox.read_file(path)

        # Check if the match_text is unique
        if content.count(match_text) > 1:
            return "Error: The text to match is not unique in the file."
        elif content.count(match_text) == 0:
            # If match_text is not found, append replace_text to the end of the file
            new_content = content + "\n" + replace_text
            context.sandbox.write_file(path, new_content)
            return "Text not found. Content added to the end of the file."
        else:
            # Replace the matched text
            new_content = content.replace(match_text, replace_text, 1)
            context.sandbox.write_file(path, new_content)
            return "File edited successfully"
    except PermissionError:
        return f"Error: No read or write permission for {path}"
    except DoSomethingElseError:
        raise  # Re-raise to be handled by higher-level components
    except Exception as e:
        return f"Error editing file: {str(e)}"
