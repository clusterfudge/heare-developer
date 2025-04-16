import json
from pathlib import Path
from typing import Optional, Dict, Any

from heare.developer.context import AgentContext
from heare.developer.tools.framework import tool, _call_anthropic_with_retry


class MemoryManager:
    """Memory manager for persistent memory storage.

    Organizes memories into modular files where keys are memory file paths and values contain the file
    contents. Supports hierarchical organization through a tree-like structure.
    """

    def __init__(self):
        """Initialize the memory manager."""
        self.base_dir = Path.home() / ".hdev" / "memory"
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
            return {"root": {"...": "depth limit reached"}}

        return self._build_tree(start_path, base_path, current_depth=0, max_depth=depth)

    def _build_tree(
        self, path: Path, base_path: Path, current_depth: int, max_depth: int
    ) -> Dict[str, Any]:
        """Recursively build a tree of memory entries.

        Args:
            path: Current path to process
            base_path: Base path for creating relative paths
            current_depth: Current recursion depth
            max_depth: Maximum recursion depth (-1 for unlimited)

        Returns:
            A dictionary representing the memory tree
        """
        result = {}

        # Process directory
        if path.is_dir():
            items = {}

            # Apply depth limit at this level
            if max_depth != -1 and current_depth > max_depth:
                items = {"...": "depth limit reached"}
            else:
                for item in path.iterdir():
                    str(item.relative_to(base_path))
                    if item.is_dir():
                        items[item.name] = self._build_tree(
                            item, base_path, current_depth + 1, max_depth
                        )
                    elif item.suffix == ".json":
                        try:
                            with open(item, "r") as f:
                                data = json.load(f)
                            # Just show a preview of content for tree view
                            content_preview = (
                                data.get("content", "")[:50] + "..."
                                if len(data.get("content", "")) > 50
                                else data.get("content", "")
                            )
                            items[item.stem] = content_preview
                        except Exception:
                            items[item.stem] = "Error: Could not read memory file"

            # Use "root" only if we're at the base directory
            if path == base_path:
                result["root"] = items
            else:
                # For prefixed paths, return the items directly with the prefix as the key
                result[path.name] = items

        return result

    def search_memory(
        self, context: AgentContext, prefix: Optional[Path] = None, query: str = ""
    ) -> str:
        """Search memory with the given query.

        Args:
            context: The agent context
            prefix: Optional path prefix to limit search scope
            query: Search query

        Returns:
            Search results
        """
        # Get all memory entries to search through
        if prefix:
            search_path = self.base_dir / prefix
            if not search_path.exists() or not search_path.is_dir():
                return f"Error: Path {prefix} does not exist or is not a directory"
            memory_files = list(search_path.glob("**/*.json"))
        else:
            memory_files = list(self.base_dir.glob("**/*.json"))

        if not memory_files:
            return "No memory entries found to search through."

        # Build search context
        memory_contents = []
        for file in memory_files:
            try:
                with open(file, "r") as f:
                    data = json.load(f)
                    relative_path = file.relative_to(self.base_dir)
                    memory_contents.append(
                        {
                            "path": str(relative_path),
                            "content": data.get("content", ""),
                            "metadata": data.get("metadata", {}),
                        }
                    )
            except Exception as e:
                print(f"Error reading memory file {file}: {e}")

        try:
            # Use the agent tool to kick off an agentic search with the light model
            from heare.developer.tools.subagent import agent

            prompt = f"""
            TASK: Search through memory entries to find information relevant to this query: "{query}"
            
            MEMORY ENTRIES:
            {json.dumps(memory_contents, indent=2)}
            
            Find all entries relevant to the query and format the results as follows:
            
            ## Search Results
            
            1. [Path to memory]: Brief explanation of why this matches
            2. [Path to memory]: Brief explanation of why this matches
            
            If no results match, say "No matching memory entries found."
            """

            # Use the subagent tool to perform the search
            result = agent(
                context=context,
                prompt=prompt,
                tool_names="",  # No additional tools needed
                model="claude-3-haiku-20240307",  # Use light model as specified
            )

            return result
        except Exception as e:
            return f"Error searching memory: {str(e)}"

    def read_entry(self, path: str) -> str:
        """Read a memory entry.

        Args:
            path: Path to the memory entry

        Returns:
            The memory entry content
        """
        try:
            full_path = self.base_dir / path

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

    def critique_knowledge_base(self, context: AgentContext) -> str:
        """Generate a critique of the current knowledge base organization.

        Args:
            context: The agent context

        Returns:
            Critique of knowledge base organization
        """
        # Get all memory entries
        memory_files = list(self.base_dir.glob("**/*.json"))
        if not memory_files:
            return "No memory entries found to critique."

        # Build memory contents list for critique
        memory_contents = []
        for file in memory_files:
            try:
                with open(file, "r") as f:
                    data = json.load(f)
                    relative_path = file.relative_to(self.base_dir)
                    memory_contents.append(
                        {
                            "path": str(relative_path),
                            "content": data.get("content", ""),
                            "metadata": data.get("metadata", {}),
                        }
                    )
            except Exception as e:
                print(f"Error reading memory file {file}: {e}")

        system_prompt = """You are a memory organization expert. Your task is to analyze 
        the current organization of memory entries and provide constructive feedback.
        
        Focus on:
        1. Identifying redundancies or duplications
        2. Suggesting better organization or hierarchies
        3. Pointing out inconsistencies in naming or categorization
        4. Recommending consolidation where appropriate
        5. Identifying gaps in knowledge or categories that should be created
        
        Be specific and actionable in your recommendations."""

        user_prompt = f"""
        Here is the current memory organization:
        
        {json.dumps(memory_contents, indent=2)}
        
        Please analyze this memory organization and provide:
        
        1. An overall assessment of the current organization
        2. Specific issues you've identified
        3. Concrete recommendations for improvement
        4. Suggestions for any new categories that should be created
        """

        try:
            message = _call_anthropic_with_retry(
                context=context,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                max_tokens=1500,
                model="claude-3-haiku-20240307",
            )
            return message.content[0].text
        except Exception as e:
            return f"Error generating critique: {str(e)}"


# Create a singleton instance
memory_manager = MemoryManager()


@tool
def get_memory_tree(
    context: "AgentContext", prefix: Optional[str] = None, depth: int = -1
) -> str:
    """Get the memory tree structure starting from the given prefix.

    Args:
        prefix: The prefix path to start from (None for root)
        depth: How deep to traverse (-1 for unlimited)
    """
    prefix_path = Path(prefix) if prefix else None
    tree = memory_manager.get_tree(prefix_path, depth)
    return json.dumps(tree, indent=2)


@tool
def search_memory(
    context: "AgentContext", query: str, prefix: Optional[str] = None
) -> str:
    """Search memory with the given query.

    Args:
        query: Search query
        prefix: Optional path prefix to limit search scope
    """
    prefix_path = Path(prefix) if prefix else None
    return memory_manager.search_memory(context, prefix_path, query)


@tool
def read_memory_entry(context: "AgentContext", path: str) -> str:
    """Read a memory entry.

    Args:
        path: Path to the memory entry
    """
    return memory_manager.read_entry(path)


@tool
def write_memory_entry(context: "AgentContext", path: str, content: str) -> str:
    """Write a memory entry.

    Args:
        path: Path to the memory entry
        content: Content to write
    """
    return memory_manager.write_entry(path, content)


@tool
def critique_memory(context: "AgentContext") -> str:
    """Generate a critique of the current memory organization.

    This tool analyzes the current memory entries and provides recommendations
    for improving organization, reducing redundancy, and identifying gaps.
    """
    return memory_manager.critique_knowledge_base(context)
