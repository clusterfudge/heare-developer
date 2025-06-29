import os
import tempfile
import pytest
from unittest import mock

from heare.developer.sandbox import Sandbox, SandboxMode
from heare.developer.context import AgentContext
from heare.developer.tools.files import (
    list_directory_with_details,
    is_symlink,
    get_symlink_target,
    resolve_symlink,
    create_symlink,
    list_directory,
    read_file,
    write_file,
)


@pytest.fixture
def temp_dir():
    with tempfile.TemporaryDirectory() as temp_dir:
        yield temp_dir


@pytest.fixture
def context_with_symlinks(temp_dir):
    """Create a context with a sandbox containing symlinks."""
    # Create files and symlinks
    with open(os.path.join(temp_dir, "target.txt"), "w") as f:
        f.write("target content")

    with open(os.path.join(temp_dir, "regular.txt"), "w") as f:
        f.write("regular content")

    # Create symlinks
    os.symlink("target.txt", os.path.join(temp_dir, "link_to_file.txt"))
    os.symlink("nonexistent.txt", os.path.join(temp_dir, "broken_link.txt"))

    # Create context with mock
    sandbox = Sandbox(temp_dir, SandboxMode.ALLOW_ALL)
    context = mock.MagicMock(spec=AgentContext)
    context.sandbox = sandbox
    return context


def test_list_directory_with_details(context_with_symlinks):
    """Test listing directory with symlink details."""
    result = list_directory_with_details(context_with_symlinks, "")

    assert "Detailed contents of" in result
    assert "link_to_file.txt -> target.txt [symlink]" in result
    assert "broken_link.txt -> nonexistent.txt (broken) [symlink]" in result

    # Check that regular files don't have [symlink] marker
    lines = result.split("\n")
    regular_line = [line for line in lines if line.strip() == "regular.txt"][0]
    target_line = [line for line in lines if line.strip() == "target.txt"][0]

    assert "[symlink]" not in regular_line
    assert "[symlink]" not in target_line


def test_list_directory_includes_symlinks(context_with_symlinks):
    """Test that regular list_directory includes symlinks."""
    result = list_directory(context_with_symlinks, "")

    assert "Contents of" in result
    assert "link_to_file.txt" in result  # Symlink should be listed
    assert "broken_link.txt" in result  # Even broken symlinks should be listed
    assert "regular.txt" in result  # Regular files should be listed
    assert "target.txt" in result  # Target files should be listed


async def test_read_file_through_symlink(context_with_symlinks):
    """Test that read_file works through symlinks using existing file tool."""
    # Read through symlink
    result = await read_file(context_with_symlinks, "link_to_file.txt")
    assert result == "target content"

    # Read original file
    result = await read_file(context_with_symlinks, "target.txt")
    assert result == "target content"


def test_write_file_through_symlink(context_with_symlinks):
    """Test that write_file works through symlinks using existing file tool."""
    # Write through symlink
    result = write_file(
        context_with_symlinks, "link_to_file.txt", "new content via symlink"
    )
    assert "File written successfully" in result

    # Verify content changed in both paths
    sandbox = context_with_symlinks.sandbox
    import asyncio

    content_via_symlink = asyncio.run(sandbox.read_file("link_to_file.txt"))
    content_via_target = asyncio.run(sandbox.read_file("target.txt"))

    assert content_via_symlink == "new content via symlink"
    assert content_via_target == "new content via symlink"


def test_is_symlink_tool(context_with_symlinks):
    """Test the is_symlink tool."""
    # Test regular file
    result = is_symlink(context_with_symlinks, "regular.txt")
    assert "is not a symbolic link" in result

    # Test symlink
    result = is_symlink(context_with_symlinks, "link_to_file.txt")
    assert "is a symbolic link" in result

    # Test broken symlink
    result = is_symlink(context_with_symlinks, "broken_link.txt")
    assert "is a symbolic link" in result

    # Test nonexistent file
    result = is_symlink(context_with_symlinks, "nonexistent.txt")
    assert "is not a symbolic link" in result


def test_get_symlink_target_tool(context_with_symlinks):
    """Test the get_symlink_target tool."""
    # Test regular symlink
    result = get_symlink_target(context_with_symlinks, "link_to_file.txt")
    assert "points to: target.txt" in result

    # Test broken symlink
    result = get_symlink_target(context_with_symlinks, "broken_link.txt")
    assert "points to: nonexistent.txt" in result

    # Test regular file (should error)
    result = get_symlink_target(context_with_symlinks, "regular.txt")
    assert "Error getting symlink target" in result


def test_resolve_symlink_tool(context_with_symlinks):
    """Test the resolve_symlink tool."""
    # Test resolving symlink
    result = resolve_symlink(context_with_symlinks, "link_to_file.txt")
    assert "resolves to:" in result
    assert "target.txt" in result

    # Test resolving regular file
    result = resolve_symlink(context_with_symlinks, "regular.txt")
    assert "resolves to:" in result
    assert "regular.txt" in result


def test_create_symlink_tool(context_with_symlinks):
    """Test the create_symlink tool."""
    # Create new symlink
    result = create_symlink(context_with_symlinks, "target.txt", "new_link.txt")
    assert "Created symlink 'new_link.txt' pointing to 'target.txt'" in result

    # Verify symlink was created
    sandbox = context_with_symlinks.sandbox
    assert sandbox.is_symlink("new_link.txt")
    assert sandbox.get_symlink_target("new_link.txt") == "target.txt"


def test_create_symlink_tool_permissions(temp_dir, monkeypatch):
    """Test that create_symlink tool respects permissions."""
    # Create target file
    with open(os.path.join(temp_dir, "target.txt"), "w") as f:
        f.write("target")

    sandbox = Sandbox(temp_dir, SandboxMode.REQUEST_EVERY_TIME)
    context = mock.MagicMock(spec=AgentContext)
    context.sandbox = sandbox

    # Test permission granted
    monkeypatch.setattr("builtins.input", lambda _: "y")
    result = create_symlink(context, "target.txt", "permitted_link.txt")
    assert "Created symlink" in result

    # Test permission denied
    monkeypatch.setattr("builtins.input", lambda _: "n")
    result = create_symlink(context, "target.txt", "denied_link.txt")
    assert "No permission" in result


def test_create_symlink_tool_security(context_with_symlinks):
    """Test that create_symlink tool prevents security issues."""
    # Try to create symlink outside sandbox
    result = create_symlink(context_with_symlinks, "/etc/passwd", "malicious_link")
    assert "Error creating symlink" in result
    assert "outside the sandbox" in result
