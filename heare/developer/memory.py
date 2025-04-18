import json
from pathlib import Path
from typing import Optional, Dict, Any


class MemoryManager:
    """Memory manager for persistent memory storage.

    Organizes memories into modular files where keys are memory file paths and values contain the file
    contents. Supports hierarchical organization through a tree-like structure.

    The memory is stored in two files per entry:
    1. A markdown file (.md) containing the content
    2. A JSON file (.metadata.json) containing the metadata
    """

    def __init__(self, base_dir: Path | None = None):
        """Initialize the memory manager."""
        self.base_dir = base_dir or Path.home() / ".hdev" / "memory"
        self.base_dir.mkdir(parents=True, exist_ok=True)

        # Default memory settings
        self.MAX_MEMORY_TOKENS = 100000
        self.CRITIQUE_THRESHOLD = 0.75
        self.CRITIQUE_INTERVAL = 10
        self.CRITIQUE_IN_SUMMARY = True

        # Ensure global memory exists
        self._ensure_global_memory()

    def _ensure_global_memory(self):
        """Ensure that the global memory file exists."""
        global_md_path = self.base_dir / "global.md"
        global_metadata_path = self.base_dir / "global.metadata.json"

        if not global_md_path.exists() or not global_metadata_path.exists():
            # Create the content file
            with open(global_md_path, "w") as f:
                f.write("Global memory storage for critical information")

            # Create the metadata file
            current_time = str(Path.home().stat().st_ctime)
            with open(global_metadata_path, "w") as f:
                json.dump(
                    {
                        "created": current_time,
                        "updated": current_time,
                        "version": 1,
                    },
                    f,
                    indent=2,
                )

    def get_tree(
        self, prefix: Optional[Path] = None, depth: int = -1
    ) -> Dict[str, Any]:
        """Get the memory tree structure starting from the given prefix.

        Args:
            prefix: The prefix path to start from (None for root)
            depth: How deep to traverse (-1 for unlimited)

        Returns:
            A dictionary representing the memory tree
        """
        if prefix is None:
            start_path = self.base_dir
            base_path = self.base_dir
        else:
            start_path = self.base_dir / prefix
            # For prefix queries, we want the base_path to be the parent of the start_path
            # This ensures the prefix is included as a top-level key
            base_path = start_path.parent

        if not start_path.exists():
            return {"error": f"Path {prefix} does not exist"}

        # Special handling for depth=0 at root level
        if depth == 0 and prefix is None:
            return {}

        result = self._build_tree(
            start_path, base_path, current_depth=0, max_depth=depth
        )
        return result

    def _build_tree(
        self, path: Path, base_path: Path, current_depth: int, max_depth: int
    ) -> Dict[str, Any]:
        """Iteratively build a tree of memory entries.

        Args:
            path: Current path to process
            base_path: Base path for creating relative paths
            current_depth: Current recursion depth
            max_depth: Maximum recursion depth (-1 for unlimited)

        Returns:
            A dictionary representing the memory tree
        """
        result = {}
        if not path.is_dir():
            return result

        # Initialize stack with the starting path and its depth
        stack = [(path, current_depth)]
        # Dictionary to store the results at each path
        path_to_items = {path: {}}

        while stack:
            current_path, depth = stack.pop()

            # Get or create items dictionary for current path
            items = path_to_items.get(current_path, {})

            # Apply depth limit at this level
            if max_depth != -1 and depth > max_depth:
                items = {"...": "depth limit reached"}
                path_to_items[current_path] = items
                continue

            # Process children
            for item in current_path.iterdir():
                str(
                    item.relative_to(base_path)
                )  # This line doesn't seem to do anything but maintain original behavior

                if item.is_dir():
                    # Add directory to stack to process later
                    stack.append((item, depth + 1))
                    # Create entry for this directory in the results dictionary
                    path_to_items[item] = {}
                    # Link this directory to its parent
                    items[item.name] = path_to_items[item]
                elif item.suffix == ".md" and not item.name.endswith(".metadata.json"):
                    # Only include the memory entries (markdown files) without content
                    # Skip metadata files, as they're associated with markdown files
                    items[item.stem] = {}

            # Store items in result dictionary
            path_to_items[current_path] = items

        # Extract the final result
        return path_to_items[path]

    def read_entry(self, path: str) -> str:
        """Read a memory entry.

        Args:
            path: Path to the memory entry

        Returns:
            The memory entry content or a list of contained memory paths if it's a directory
        """
        try:
            full_path = self.base_dir / path

            # Handle directory case
            if full_path.is_dir():
                result = f"Directory: {path}\n\nContained paths:\n"
                paths = []

                for item in full_path.iterdir():
                    item_path = str(item.relative_to(self.base_dir))
                    if item.is_dir():
                        paths.append(f"- [NODE] {item_path}")
                    elif item.suffix == ".md" and not item.name.endswith(
                        ".metadata.json"
                    ):
                        paths.append(f"- [LEAF] {item_path.replace('.md', '')}")

                if not paths:
                    result += "  (empty directory)"
                else:
                    result += "\n".join(sorted(paths))

                return result

            # Construct paths for content and metadata files
            content_path = full_path.with_suffix(".md")
            metadata_path = full_path.parent / f"{full_path.name}.metadata.json"

            # Check if files exist
            if not content_path.exists():
                return f"Error: Memory entry content at {path}.md does not exist"

            if not metadata_path.exists():
                return f"Error: Memory entry metadata at {path}.metadata.json does not exist"

            # Read content and metadata
            with open(content_path, "r") as f:
                content = f.read()

            with open(metadata_path, "r") as f:
                metadata = json.load(f)

            # Format the output
            result = f"Memory entry: {path}\n\n"
            result += f"Content:\n{content}\n\n"
            result += "Metadata:\n"
            for key, value in metadata.items():
                result += f"- {key}: {value}\n"

            return result
        except Exception as e:
            return f"Error reading memory entry: {str(e)}"

    def write_entry(
        self, path: str, content: str, metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Write a memory entry.

        Args:
            path: Path to the memory entry
            content: Content to write
            metadata: Optional metadata

        Returns:
            Status message
        """
        try:
            full_path = self.base_dir / path

            # Construct paths for content and metadata files
            content_path = full_path.with_suffix(".md")
            metadata_path = full_path.parent / f"{full_path.name}.metadata.json"

            # Create parent directories if they don't exist
            content_path.parent.mkdir(parents=True, exist_ok=True)

            # Check if the metadata file exists to preserve existing metadata
            existing_metadata = {}
            if metadata_path.exists():
                try:
                    with open(metadata_path, "r") as f:
                        existing_metadata = json.load(f)
                except Exception:
                    pass

            # Update metadata
            if metadata is None:
                metadata = {}

            current_time = str(Path.home().stat().st_ctime)
            new_metadata = {
                "updated": current_time,
                "version": existing_metadata.get("version", 0) + 1,
            }

            if not content_path.exists():
                new_metadata["created"] = current_time

            # Combine existing metadata with updates
            updated_metadata = {**existing_metadata, **new_metadata, **metadata}

            # Write the content file
            with open(content_path, "w") as f:
                f.write(content)

            # Write the metadata file
            with open(metadata_path, "w") as f:
                json.dump(updated_metadata, f, indent=2)

            return f"Memory entry written successfully to {path}"
        except Exception as e:
            return f"Error writing memory entry: {str(e)}"

    def delete_entry(self, path: str) -> str:
        """Delete a memory entry.

        Args:
            path: Path to the memory entry or directory to delete

        Returns:
            Status message
        """
        try:
            import shutil

            full_path = self.base_dir / path

            # Handle directory case
            if full_path.is_dir():
                if not full_path.exists():
                    return f"Error: Directory {path} does not exist"

                # Delete the directory and all its contents
                shutil.rmtree(full_path)
                return f"Successfully deleted directory {path} and all its contents"

            # Handle file case - check for both content and metadata files
            content_path = full_path.with_suffix(".md")
            metadata_path = full_path.parent / f"{full_path.name}.metadata.json"

            if not content_path.exists() and not metadata_path.exists():
                return f"Error: Memory entry at {path} does not exist"

            # Delete the files if they exist
            if content_path.exists():
                content_path.unlink()

            if metadata_path.exists():
                metadata_path.unlink()

            return f"Successfully deleted memory entry {path}"

        except Exception as e:
            return f"Error deleting memory entry: {str(e)}"
