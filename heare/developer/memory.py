import json
from pathlib import Path
from typing import Optional, Dict, Any


class MemoryManager:
    """Memory manager for persistent memory storage.

    Organizes memories into modular files where keys are memory file paths and values contain the file
    contents. Supports hierarchical organization through a tree-like structure.
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
        global_path = self.base_dir / "global.json"
        if not global_path.exists():
            with open(global_path, "w") as f:
                json.dump(
                    {
                        "content": "Global memory storage for critical information",
                        "metadata": {
                            "created": str(Path.home().stat().st_ctime),
                            "updated": str(Path.home().stat().st_ctime),
                            "version": 1,
                        },
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
                elif item.suffix == ".json":
                    # Only include the node name without any content
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
                    elif item.suffix == ".json":
                        paths.append(f"- [LEAF] {item_path.replace('.json', '')}")

                if not paths:
                    result += "  (empty directory)"
                else:
                    result += "\n".join(sorted(paths))

                return result

            # Add .json extension if not present
            if not full_path.suffix:
                full_path = full_path.with_suffix(".json")

            if not full_path.exists():
                return f"Error: Memory entry at {path} does not exist"

            with open(full_path, "r") as f:
                data = json.load(f)

            # Format the output
            content = data.get("content", "No content")
            metadata = data.get("metadata", {})

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

            # Add .json extension if not present
            if not full_path.suffix:
                full_path = full_path.with_suffix(".json")

            # Create parent directories if they don't exist
            full_path.parent.mkdir(parents=True, exist_ok=True)

            # Check if the file exists to preserve metadata
            existing_metadata = {}
            if full_path.exists():
                try:
                    with open(full_path, "r") as f:
                        data = json.load(f)
                        existing_metadata = data.get("metadata", {})
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

            if not full_path.exists():
                new_metadata["created"] = current_time

            # Combine existing metadata with updates
            updated_metadata = {**existing_metadata, **new_metadata, **metadata}

            # Write the file
            with open(full_path, "w") as f:
                json.dump(
                    {"content": content, "metadata": updated_metadata}, f, indent=2
                )

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

            # Handle file case - add .json extension if not present
            if not full_path.suffix:
                full_path = full_path.with_suffix(".json")

            if not full_path.exists():
                return f"Error: Memory entry at {path} does not exist"

            # Delete the file
            full_path.unlink()
            return f"Successfully deleted memory entry {path}"

        except Exception as e:
            return f"Error deleting memory entry: {str(e)}"
