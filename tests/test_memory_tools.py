import json
from unittest.mock import MagicMock, patch

import pytest

from heare.developer.context import AgentContext
from heare.developer.tools.memory import (
    get_memory_tree,
    search_memory,
    read_memory_entry,
    write_memory_entry,
    critique_memory,
    memory_manager,
)


@pytest.fixture
def test_memory_dir(tmp_path):
    """Create a temporary memory directory for testing."""
    # Save the original base_dir
    original_base_dir = memory_manager.base_dir

    # Set the base_dir to a temporary directory
    memory_manager.base_dir = tmp_path / "memory"
    memory_manager.base_dir.mkdir(parents=True, exist_ok=True)

    # Create some test memory entries
    (memory_manager.base_dir / "global.json").write_text(
        json.dumps(
            {
                "content": "Global memory for testing",
                "metadata": {
                    "created": "123456789",
                    "updated": "123456789",
                    "version": 1,
                },
            }
        )
    )

    # Create a nested directory structure
    projects_dir = memory_manager.base_dir / "projects"
    projects_dir.mkdir(exist_ok=True)

    (projects_dir / "project1.json").write_text(
        json.dumps(
            {
                "content": "Information about project 1",
                "metadata": {
                    "created": "123456789",
                    "updated": "123456789",
                    "version": 1,
                },
            }
        )
    )

    # Create a subdirectory
    frontend_dir = projects_dir / "frontend"
    frontend_dir.mkdir(exist_ok=True)

    (frontend_dir / "react.json").write_text(
        json.dumps(
            {
                "content": "React components and patterns",
                "metadata": {
                    "created": "123456789",
                    "updated": "123456789",
                    "version": 1,
                },
            }
        )
    )

    yield tmp_path

    # Restore the original base_dir
    memory_manager.base_dir = original_base_dir


@pytest.fixture
def mock_context():
    """Create a mock AgentContext for testing."""
    context = MagicMock(spec=AgentContext)
    context.report_usage = MagicMock()
    return context


@patch("heare.developer.tools.memory._call_anthropic_with_retry")
def test_get_memory_tree(_, test_memory_dir, mock_context):
    """Test getting the memory tree."""
    result = get_memory_tree(mock_context)
    tree = json.loads(result)

    # Check that the root contains expected entries
    assert "root" in tree
    assert "global" in tree["root"]
    assert "projects" in tree["root"]

    # Test with a prefix
    result = get_memory_tree(mock_context, prefix="projects")
    tree = json.loads(result)
    assert "projects" in tree
    assert "project1" in tree["projects"]
    assert "frontend" in tree["projects"]

    # Test with depth limit
    result = get_memory_tree(mock_context, depth=0)
    tree = json.loads(result)
    assert "..." in tree["root"]


@patch("heare.developer.tools.memory._call_anthropic_with_retry")
def test_write_and_read_memory_entry(mock_call, test_memory_dir, mock_context):
    """Test writing and reading memory entries."""
    # Configure the mock to return a response object with content attribute
    mock_message = MagicMock()
    mock_message.content = [MagicMock()]
    mock_message.content[0].text = "Mocked search response"
    mock_call.return_value = mock_message

    # Test writing a new entry
    result = write_memory_entry(
        mock_context, "notes/important.json", "This is an important note"
    )
    assert "successfully" in result

    # Verify the file was created
    assert (memory_manager.base_dir / "notes" / "important.json").exists()

    # Test reading the entry
    result = read_memory_entry(mock_context, "notes/important.json")
    assert "This is an important note" in result

    # Test overwriting an existing entry
    result = write_memory_entry(
        mock_context, "notes/important.json", "Updated note content"
    )
    assert "successfully" in result

    # Verify content was updated
    result = read_memory_entry(mock_context, "notes/important.json")
    assert "Updated note content" in result

    # Test reading non-existent entry
    result = read_memory_entry(mock_context, "nonexistent/entry.json")
    assert "Error" in result


@patch("heare.developer.tools.memory._call_anthropic_with_retry")
def test_search_memory(mock_call, test_memory_dir, mock_context):
    """Test searching memory."""
    # Configure the mock to return a response object with content attribute
    mock_message = MagicMock()
    mock_message.content = [MagicMock()]
    mock_message.content[0].text = "Mocked search response"
    mock_call.return_value = mock_message

    # Test searching
    result = search_memory(mock_context, "project")
    assert result == "Mocked search response"

    # Verify the API was called with expected parameters
    mock_call.assert_called_once()

    # Test searching with prefix
    mock_call.reset_mock()
    result = search_memory(mock_context, "react", prefix="projects")
    assert result == "Mocked search response"


@patch("heare.developer.tools.memory._call_anthropic_with_retry")
def test_critique_memory(mock_call, test_memory_dir, mock_context):
    """Test memory critique."""
    # Configure the mock to return a response object with content attribute
    mock_message = MagicMock()
    mock_message.content = [MagicMock()]
    mock_message.content[0].text = "Mocked critique response"
    mock_call.return_value = mock_message

    # Test critiquing
    result = critique_memory(mock_context)
    assert result == "Mocked critique response"

    # Verify the API was called with expected parameters
    mock_call.assert_called_once()
