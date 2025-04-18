import json
from unittest.mock import MagicMock, patch

import pytest

from heare.developer.context import AgentContext
from heare.developer.tools.memory import (
    search_memory,
    read_memory_entry,
    write_memory_entry,
)
from heare.developer.memory import MemoryManager


@pytest.fixture
def test_memory_manager(tmp_path):
    """Create a memory manager with a temporary memory directory for testing."""
    # Create a memory manager
    memory_manager = MemoryManager(base_dir=tmp_path / "memory")

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

    return memory_manager


@pytest.fixture
def mock_context(test_memory_manager):
    """Create a mock AgentContext for testing."""
    context = MagicMock(spec=AgentContext)
    context.report_usage = MagicMock()
    context.memory_manager = test_memory_manager
    context.user_interface = MagicMock()
    return context


def test_get_memory_tree(mock_context):
    """Test getting the memory tree with only node names."""

    tree = mock_context.memory_manager.get_tree()

    # Check that the root contains expected entries
    assert "global" in tree
    assert "projects" in tree

    # Verify no content is included, just structure
    assert isinstance(tree["global"], dict)
    assert len(tree["global"]) == 0  # Should be empty as we no longer include content

    # Test with a prefix
    tree = mock_context.memory_manager.get_tree("projects")
    assert "project1" in tree
    assert "frontend" in tree

    # Verify the JSON node has empty content
    assert isinstance(tree["project1"], dict)
    assert len(tree["project1"]) == 0


def test_write_and_read_memory_entry(mock_context):
    """Test writing and reading memory entries."""
    # Test writing a new entry
    result = write_memory_entry(
        mock_context, "notes/important.json", "This is an important note"
    )
    assert "successfully" in result

    # Verify the file was created
    assert (mock_context.memory_manager.base_dir / "notes" / "important.json").exists()

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


@patch("heare.developer.tools.subagent.agent")
def test_search_memory(mock_agent, mock_context):
    """Test searching memory."""
    # Configure the mock to return a mocked response
    mock_agent.return_value = "Mocked search response"

    # Test searching
    result = search_memory(mock_context, "project")
    assert result == "Mocked search response"

    # Verify the subagent was called
    mock_agent.assert_called_once()

    # Verify that the model argument was passed correctly
    assert mock_agent.call_args[1]["model"] == "smart"

    # Test searching with prefix
    mock_agent.reset_mock()
    result = search_memory(mock_context, "react", prefix="projects")
    assert result == "Mocked search response"


@patch("heare.developer.tools.memory.agent")
def test_critique_memory(mock_agent, mock_context):
    """Test critiquing memory organization."""
    # Configure the mock to return a mocked response
    mock_agent.return_value = "Mocked critique response"

    # Import the function to test
    from heare.developer.tools.memory import critique_memory

    # Test critiquing
    result = critique_memory(mock_context)
    assert result == "Mocked critique response"

    # Verify the agent was called
    mock_agent.assert_called_once()

    # Verify that the model argument was passed correctly
    assert mock_agent.call_args[1]["model"] == "haiku"

    # Check that the prompt contains the expected structural information
    prompt = mock_agent.call_args[1]["prompt"]
    assert "memory organization tree" in prompt
    assert "memory entry paths" in prompt
