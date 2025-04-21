"""Memory web browser implementation.

Provides a web interface for browsing and viewing memory content.
"""

import webbrowser
from pathlib import Path
from typing import Optional

import markdown
from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    send_from_directory,
)

from heare.developer.memory import MemoryManager


class MemoryWebApp:
    """Web application for browsing memory content."""

    def __init__(self, memory_manager: MemoryManager):
        """Initialize the web application with a memory manager.

        Args:
            memory_manager: The memory manager to use for accessing memory content
        """
        self.memory_manager = memory_manager
        self.app = Flask(__name__)
        self.setup_routes()

        # Create a templates directory if needed
        self.templates_dir = Path(__file__).parent / "templates"
        self.templates_dir.mkdir(exist_ok=True)
        self.static_dir = Path(__file__).parent / "static"
        self.static_dir.mkdir(exist_ok=True)

    def setup_routes(self):
        """Set up the routes for the web application."""

        @self.app.route("/static/<path:filename>")
        def static_files(filename):
            return send_from_directory(self.static_dir, filename)

        @self.app.route("/")
        def index():
            """Root route that displays the memory tree."""
            return self.render_memory_tree()

        @self.app.route("/view/<path:memory_path>")
        def view_memory(memory_path):
            """View a specific memory entry."""
            return self.render_memory_entry(memory_path)

        @self.app.route("/browse/<path:directory_path>")
        def browse_directory(directory_path):
            """Browse a specific directory in the memory tree."""
            return self.render_memory_directory(directory_path)

        @self.app.route("/search")
        def search():
            """Search for memory entries."""
            query = request.args.get("query", "")
            if not query:
                return redirect(url_for("index"))
            return self.render_search_results(query)

    def render_memory_tree(self, prefix: Optional[str] = None):
        """Render the memory tree starting from the given prefix.

        Args:
            prefix: Optional prefix path to start from

        Returns:
            Rendered HTML template with the memory tree
        """
        # Clean up the prefix if it has any double slashes
        if prefix:
            clean_prefix = prefix.replace("//", "/")
        else:
            clean_prefix = prefix

        tree = self.memory_manager.get_tree(
            Path(clean_prefix) if clean_prefix else None
        )

        # Create breadcrumb navigation
        breadcrumbs = self._create_breadcrumbs(clean_prefix) if clean_prefix else []

        content_block = render_template(
            "tree.html", tree=tree, current_path=clean_prefix or ""
        )

        return render_template(
            "base.html",
            content_block=content_block,
            breadcrumbs=breadcrumbs,
            title="Memory Browser",
        )

    def render_memory_entry(self, memory_path: str):
        """Render a specific memory entry.

        Args:
            memory_path: Path to the memory entry to render

        Returns:
            Rendered HTML template with the memory entry content
        """
        full_path = self.memory_manager.base_dir / memory_path

        # Handle directory case
        if full_path.is_dir():
            return self.render_memory_directory(memory_path)

        # Get the memory entry content and parse it according to the new structure
        content = self.memory_manager.read_entry(memory_path, format="markdown")

        # Separate content and metadata
        metadata = {}
        content_text = ""

        # Create breadcrumb navigation
        breadcrumbs = self._create_breadcrumbs(memory_path)

        # Parse the structured response from read_entry
        # Format: "Memory entry: path\n\nContent:\ncontent\n\nMetadata:\n- key: value\n..."
        try:
            if (
                "Memory entry:" in content
                and "Content:" in content
                and "Metadata:" in content
            ):
                # Split the content into header, content, and metadata sections
                parts = content.split("\n\n", 1)

                # Skip the first part which is "Memory entry: path"
                if len(parts) >= 2:
                    # Extract content (removing "Content:" prefix)
                    for i, part in enumerate(parts):
                        if part.startswith("Content:"):
                            content_text = part[len("Content:") :].strip()
                            break

                # Extract metadata
                metadata_section = content.split("Metadata:", 1)
                if len(metadata_section) > 1:
                    metadata_text = metadata_section[1].strip()
                    for line in metadata_text.split("\n"):
                        if line.startswith("- ") and ":" in line:
                            key, value = line[2:].split(":", 1)
                            metadata[key.strip()] = value.strip()
        except Exception as e:
            content_text = (
                f"Error parsing memory entry: {str(e)}\n\nRaw content:\n{content}"
            )

        # Convert markdown to HTML
        content_html = markdown.markdown(content_text)

        content_block = render_template(
            "entry.html",
            content=content_html,
            metadata=metadata,
            memory_path=memory_path,
        )

        return render_template(
            "base.html",
            content_block=content_block,
            breadcrumbs=breadcrumbs,
            title=f"Memory: {memory_path}",
        )

    def render_memory_directory(self, directory_path: str):
        """Render the contents of a memory directory.

        Args:
            directory_path: Path to the directory to render

        Returns:
            Rendered HTML template with the directory contents
        """
        try:
            # Get directory content using the memory manager
            directory_content = self.memory_manager.read_entry(directory_path)

            # Parse the content to extract the list of contained paths
            items = []
            if "Contained paths:" in directory_content:
                # Split the content at "Contained paths:" to get the directory listing
                parts = directory_content.split("Contained paths:")
                if len(parts) > 1:
                    lines = parts[1].strip().split("\n")
                    for line in lines:
                        if line.startswith("- [NODE]") or line.startswith("- [LEAF]"):
                            is_directory = line.startswith("- [NODE]")
                            path = line.split("] ", 1)[1].strip()

                            # Make sure we have clean path with proper structure
                            # If the path does not start with the directory_path, prepend it
                            if directory_path and not path.startswith(directory_path):
                                if directory_path.endswith("/"):
                                    full_path = directory_path + path
                                else:
                                    full_path = f"{directory_path}/{path}"
                                # Clean up any double slashes
                                full_path = full_path.replace("//", "/")
                            else:
                                full_path = path

                            items.append(
                                {
                                    "name": Path(path).name,
                                    "path": full_path,
                                    "is_directory": is_directory,
                                }
                            )

            # Create breadcrumb navigation
            breadcrumbs = self._create_breadcrumbs(directory_path)

            content_block = render_template(
                "directory.html", items=items, directory_path=directory_path
            )

            return render_template(
                "base.html",
                content_block=content_block,
                breadcrumbs=breadcrumbs,
                title=f"Directory: {directory_path}",
            )
        except Exception as e:
            content_block = render_template("error.html", error=str(e))

            return render_template(
                "base.html", content_block=content_block, breadcrumbs=[], title="Error"
            )

    def render_search_results(self, query: str):
        """Render the results of a memory search.

        Args:
            query: Search query

        Returns:
            Rendered HTML template with the search results
        """
        # We need to implement a basic search functionality using Python
        # This is a simple implementation that searches through all .md files

        results = []
        try:
            # Look for files containing the query
            for md_file in self.memory_manager.base_dir.glob("**/*.md"):
                # Skip metadata files
                if md_file.name.endswith(".metadata.json"):
                    continue

                # Get the relative path for the memory entry
                rel_path = md_file.relative_to(self.memory_manager.base_dir)
                memory_path = str(rel_path.with_suffix(""))

                # Read file content
                with open(md_file, "r") as f:
                    content = f.read()

                # Check if query is in content (case-insensitive)
                if query.lower() in content.lower():
                    # Extract a snippet of context around the match
                    idx = content.lower().find(query.lower())
                    start = max(0, idx - 50)
                    end = min(len(content), idx + len(query) + 50)

                    # Create a snippet with ellipsis if needed
                    snippet = ""
                    if start > 0:
                        snippet += "..."
                    snippet += content[start:end]
                    if end < len(content):
                        snippet += "..."

                    # Highlight the query in the snippet (case-insensitive)
                    import re

                    pattern = re.compile(re.escape(query), re.IGNORECASE)
                    highlighted_snippet = pattern.sub(
                        lambda m: f"<mark>{m.group(0)}</mark>", snippet
                    )

                    # Add to results
                    results.append(
                        {"path": memory_path, "snippet": highlighted_snippet}
                    )
        except Exception as e:
            # If there's an error, we'll show it in the results
            results.append(
                {"path": "Error", "snippet": f"Error during search: {str(e)}"}
            )

        content_block = render_template("search.html", query=query, results=results)

        return render_template(
            "base.html",
            content_block=content_block,
            breadcrumbs=[],
            title=f"Search: {query}",
        )

    def _create_breadcrumbs(self, path: str):
        """Create breadcrumb navigation for a path.

        Args:
            path: Path to create breadcrumbs for

        Returns:
            List of breadcrumb items with name and path
        """
        if not path:
            return []

        parts = Path(path).parts
        breadcrumbs = [{"name": "Home", "path": "/"}]

        current_path = ""
        for i, part in enumerate(parts):
            # Properly join path parts using Path object
            if current_path:
                current_path = str(Path(current_path) / part)
            else:
                current_path = part

            # Determine if this is a directory or file
            is_last = i == len(parts) - 1
            full_path = self.memory_manager.base_dir / current_path

            # Check if it's a directory
            is_dir = full_path.is_dir()

            # If it's not a directory, it might be a memory entry (without extension)
            if not is_dir:
                # Check if the .md file exists
                md_path = full_path.with_suffix(".md")
                is_file = md_path.exists()
            else:
                is_file = False

            # Create clean URLs without duplicate slashes
            url = f"/browse/{current_path}" if is_dir else f"/view/{current_path}"
            if is_last and is_file:
                url = f"/view/{current_path}"

            # Replace any accidental double slashes
            url = url.replace("//", "/")

            breadcrumbs.append({"name": part, "path": url})

        return breadcrumbs

    def run(self, host: str = "127.0.0.1", port: int = 5000, open_browser: bool = True):
        """Run the web application.

        Args:
            host: Hostname to bind to
            port: Port to bind to
            open_browser: Whether to open a browser window automatically
        """
        if open_browser:
            webbrowser.open(f"http://{host}:{port}")
        self.app.run(host=host, port=port)


def run_memory_webapp(
    memory_dir: Optional[Path] = None, host: str = "127.0.0.1", port: int = 5500
):
    """Run the memory webapp.

    Args:
        memory_dir: Optional path to the memory directory to use
        host: Hostname to bind to
        port: Port to bind to
    """
    memory_manager = MemoryManager(memory_dir)
    app = MemoryWebApp(memory_manager)

    print(f"Starting memory browser at http://{host}:{port}")
    print("Press Ctrl+C to stop the server")

    app.run(host=host, port=port)
