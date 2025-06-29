import os
import tempfile
import pytest

from heare.developer.sandbox import Sandbox, SandboxMode


@pytest.fixture
def temp_dir():
    with tempfile.TemporaryDirectory() as temp_dir:
        yield temp_dir


@pytest.fixture
def symlink_test_dir(temp_dir):
    """Create a test directory with various symlink scenarios."""
    # Create regular files
    with open(os.path.join(temp_dir, "regular.txt"), "w") as f:
        f.write("regular file content")

    with open(os.path.join(temp_dir, "target.txt"), "w") as f:
        f.write("target file content")

    # Create subdirectory with content
    subdir = os.path.join(temp_dir, "subdir")
    os.makedirs(subdir)
    with open(os.path.join(subdir, "subfile.txt"), "w") as f:
        f.write("subdirectory file content")

    # Create symlinks
    # Relative symlink to file in same directory
    os.symlink("target.txt", os.path.join(temp_dir, "link_to_file.txt"))

    # Absolute symlink to file
    target_path = os.path.join(temp_dir, "target.txt")
    os.symlink(target_path, os.path.join(temp_dir, "abs_link_to_file.txt"))

    # Symlink to directory
    os.symlink("subdir", os.path.join(temp_dir, "link_to_dir"))

    # Broken symlink
    os.symlink("nonexistent.txt", os.path.join(temp_dir, "broken_link.txt"))

    # Nested symlink in subdirectory
    os.symlink("../target.txt", os.path.join(subdir, "link_to_parent.txt"))

    return temp_dir


def test_directory_listing_shows_symlinks(symlink_test_dir):
    """Test that directory listing includes symlink information."""
    sandbox = Sandbox(symlink_test_dir, SandboxMode.ALLOW_ALL)

    listing = sandbox.get_directory_listing()

    # Should include all files and symlinks
    # When following symlinks, files appear both under original and symlinked paths
    expected_items = {
        "regular.txt",
        "target.txt",
        "link_to_file.txt",
        "abs_link_to_file.txt",
        "link_to_dir",
        "broken_link.txt",
        "subdir/subfile.txt",
        "subdir/link_to_parent.txt",
        "link_to_dir/subfile.txt",  # File accessed via symlinked directory
        "link_to_dir/link_to_parent.txt",  # Symlink accessed via symlinked directory
    }

    assert set(listing) == expected_items


def test_directory_listing_with_symlink_info(symlink_test_dir):
    """Test that directory listing can provide symlink metadata."""
    sandbox = Sandbox(symlink_test_dir, SandboxMode.ALLOW_ALL)

    # Get detailed listing with symlink information
    detailed_listing = sandbox.get_directory_listing_with_metadata()

    # Find symlink entries
    link_to_file = next(
        item for item in detailed_listing if item["name"] == "link_to_file.txt"
    )
    regular_file = next(
        item for item in detailed_listing if item["name"] == "regular.txt"
    )
    broken_link = next(
        item for item in detailed_listing if item["name"] == "broken_link.txt"
    )

    # Check symlink metadata
    assert link_to_file["is_symlink"] is True
    assert link_to_file["symlink_target"] == "target.txt"
    assert link_to_file["symlink_resolved_path"].endswith("target.txt")
    assert link_to_file["symlink_exists"] is True

    # Check regular file metadata
    assert regular_file["is_symlink"] is False
    assert "symlink_target" not in regular_file

    # Check broken symlink metadata
    assert broken_link["is_symlink"] is True
    assert broken_link["symlink_target"] == "nonexistent.txt"
    assert broken_link["symlink_exists"] is False


async def test_read_file_through_symlink(symlink_test_dir):
    """Test reading files through symlinks."""
    sandbox = Sandbox(symlink_test_dir, SandboxMode.ALLOW_ALL)

    # Read through relative symlink
    content = await sandbox.read_file("link_to_file.txt")
    assert content == "target file content"

    # Read through absolute symlink
    content = await sandbox.read_file("abs_link_to_file.txt")
    assert content == "target file content"

    # Read through nested symlink
    content = await sandbox.read_file("subdir/link_to_parent.txt")
    assert content == "target file content"


async def test_read_broken_symlink_fails(symlink_test_dir):
    """Test that reading a broken symlink raises appropriate error."""
    sandbox = Sandbox(symlink_test_dir, SandboxMode.ALLOW_ALL)

    with pytest.raises(FileNotFoundError):
        await sandbox.read_file("broken_link.txt")


async def test_write_file_through_symlink(symlink_test_dir):
    """Test writing files through symlinks."""
    sandbox = Sandbox(symlink_test_dir, SandboxMode.ALLOW_ALL)

    # Write through symlink
    new_content = "modified through symlink"
    sandbox.write_file("link_to_file.txt", new_content)

    # Verify content changed in target file
    target_content = await sandbox.read_file("target.txt")
    assert target_content == new_content

    # Verify content accessible through other symlinks too
    abs_link_content = await sandbox.read_file("abs_link_to_file.txt")
    assert abs_link_content == new_content


async def test_create_symlink(symlink_test_dir):
    """Test creating new symlinks."""
    sandbox = Sandbox(symlink_test_dir, SandboxMode.ALLOW_ALL)

    # Create relative symlink
    sandbox.create_symlink("target.txt", "new_link.txt")

    # Verify symlink was created and works
    assert os.path.islink(os.path.join(symlink_test_dir, "new_link.txt"))
    content = await sandbox.read_file("new_link.txt")
    assert content == "target file content"

    # Create absolute symlink
    target_path = os.path.join(symlink_test_dir, "target.txt")
    sandbox.create_symlink(target_path, "new_abs_link.txt")

    # Verify absolute symlink works
    assert os.path.islink(os.path.join(symlink_test_dir, "new_abs_link.txt"))
    content = await sandbox.read_file("new_abs_link.txt")
    assert content == "target file content"


def test_is_symlink_method(symlink_test_dir):
    """Test method to check if a path is a symlink."""
    sandbox = Sandbox(symlink_test_dir, SandboxMode.ALLOW_ALL)

    assert sandbox.is_symlink("link_to_file.txt") is True
    assert sandbox.is_symlink("regular.txt") is False
    assert sandbox.is_symlink("broken_link.txt") is True
    assert sandbox.is_symlink("nonexistent.txt") is False


def test_get_symlink_target(symlink_test_dir):
    """Test getting symlink target path."""
    sandbox = Sandbox(symlink_test_dir, SandboxMode.ALLOW_ALL)

    # Test relative symlink
    target = sandbox.get_symlink_target("link_to_file.txt")
    assert target == "target.txt"

    # Test absolute symlink
    target = sandbox.get_symlink_target("abs_link_to_file.txt")
    assert target == os.path.join(symlink_test_dir, "target.txt")

    # Test broken symlink
    target = sandbox.get_symlink_target("broken_link.txt")
    assert target == "nonexistent.txt"

    # Test non-symlink raises error
    with pytest.raises(ValueError, match="not a symlink"):
        sandbox.get_symlink_target("regular.txt")


def test_resolve_symlink_path(symlink_test_dir):
    """Test resolving symlink to final target path."""
    sandbox = Sandbox(symlink_test_dir, SandboxMode.ALLOW_ALL)

    # Test resolving relative symlink
    resolved = sandbox.resolve_symlink_path("link_to_file.txt")
    assert resolved.endswith("target.txt")

    # Test resolving absolute symlink
    resolved = sandbox.resolve_symlink_path("abs_link_to_file.txt")
    assert resolved.endswith("target.txt")

    # Test resolving non-symlink returns original path
    resolved = sandbox.resolve_symlink_path("regular.txt")
    assert resolved.endswith("regular.txt")


def test_directory_traversal_follows_symlinks(symlink_test_dir):
    """Test that directory traversal follows symlinked directories."""
    sandbox = Sandbox(symlink_test_dir, SandboxMode.ALLOW_ALL)

    listing = sandbox.get_directory_listing()

    # Should include files from symlinked directory
    # Note: This tests current os.walk() behavior which follows symlinks
    symlinked_files = [item for item in listing if item.startswith("link_to_dir/")]
    assert len(symlinked_files) > 0
    assert "link_to_dir/subfile.txt" in listing


def test_symlink_outside_sandbox_prevented(symlink_test_dir):
    """Test that creating symlinks outside sandbox is prevented."""
    sandbox = Sandbox(symlink_test_dir, SandboxMode.ALLOW_ALL)

    # Try to create symlink pointing outside sandbox
    with pytest.raises(ValueError, match="outside the sandbox"):
        sandbox.create_symlink("/etc/passwd", "malicious_link")

    # Try to create symlink with target outside sandbox
    with pytest.raises(ValueError, match="outside the sandbox"):
        sandbox.create_symlink("../../../etc/passwd", "another_malicious_link")


def test_permissions_for_symlink_operations(temp_dir, monkeypatch):
    """Test that symlink operations respect sandbox permissions."""
    sandbox = Sandbox(temp_dir, SandboxMode.REQUEST_EVERY_TIME)

    # Create a target file
    with open(os.path.join(temp_dir, "target.txt"), "w") as f:
        f.write("target content")

    # Test permission check for creating symlink
    monkeypatch.setattr("builtins.input", lambda _: "y")
    sandbox.create_symlink("target.txt", "permitted_link.txt")
    assert os.path.islink(os.path.join(temp_dir, "permitted_link.txt"))

    # Test permission denial for creating symlink
    monkeypatch.setattr("builtins.input", lambda _: "n")
    with pytest.raises(PermissionError):
        sandbox.create_symlink("target.txt", "denied_link.txt")
