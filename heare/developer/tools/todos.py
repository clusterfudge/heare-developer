"""
Tools for managing session-based todo lists.

This module provides tools to read and write todos for the current session.
Todos are stored in JSON files in the ~/.local/share/heare/todos directory,
with each session having its own todo file named by session ID.
"""

import json
from enum import Enum
from pathlib import Path
from typing import List, Dict, Any
from dataclasses import dataclass
from uuid import uuid4

from heare.developer.context import AgentContext
from heare.developer.tools.framework import tool
from heare.developer.utils import get_data_dir, ensure_dir_exists, CustomJSONEncoder


class TodoStatus(str, Enum):
    """Status of a todo item."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class TodoPriority(str, Enum):
    """Priority of a todo item."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class TodoItem:
    """A todo item."""

    id: str
    content: str
    status: TodoStatus
    priority: TodoPriority

    @classmethod
    def create(cls, content: str, priority: TodoPriority = TodoPriority.MEDIUM):
        """Create a new todo item with a unique ID."""
        return cls(
            id=str(uuid4()),
            content=content,
            status=TodoStatus.PENDING,
            priority=priority,
        )


def get_todos_dir() -> Path:
    """Get the directory for storing todos."""
    todos_dir = get_data_dir() / "todos"
    ensure_dir_exists(todos_dir)
    return todos_dir


def get_todo_file(session_id: str) -> Path:
    """Get the path to a todo file for a session."""
    return get_todos_dir() / f"{session_id}.json"


def load_todos(session_id: str) -> List[TodoItem]:
    """Load todos from a file."""
    todo_file = get_todo_file(session_id)
    if not todo_file.exists():
        return []

    try:
        with open(todo_file, "r") as f:
            todos_data = json.load(f)

        return [
            TodoItem(
                id=item["id"],
                content=item["content"],
                status=TodoStatus(item["status"]),
                priority=TodoPriority(item["priority"]),
            )
            for item in todos_data
        ]
    except (json.JSONDecodeError, KeyError, ValueError) as e:
        # Log the error but return an empty list to avoid disrupting the user
        print(f"Error loading todos: {e}")
        return []


def save_todos(session_id: str, todos: List[TodoItem]) -> None:
    """Save todos to a file."""
    todo_file = get_todo_file(session_id)

    todos_data = [
        {
            "id": todo.id,
            "content": todo.content,
            "status": todo.status,
            "priority": todo.priority,
        }
        for todo in todos
    ]

    with open(todo_file, "w") as f:
        json.dump(todos_data, f, cls=CustomJSONEncoder, indent=2)


def sort_todos(todos: List[TodoItem]) -> List[TodoItem]:
    """Sort todos by status (in_progress first) then priority."""
    # Define the order of statuses for sorting
    status_order = {
        TodoStatus.IN_PROGRESS: 0,
        TodoStatus.PENDING: 1,
        TodoStatus.COMPLETED: 2,
    }

    # Define the order of priorities for sorting
    priority_order = {TodoPriority.HIGH: 0, TodoPriority.MEDIUM: 1, TodoPriority.LOW: 2}

    return sorted(
        todos,
        key=lambda todo: (status_order[todo.status], priority_order[todo.priority]),
    )


def format_todo_list(todos: List[TodoItem]) -> str:
    """Format a list of todos for display."""
    if not todos:
        return "No todos in the current session."

    sorted_todos = sort_todos(todos)

    # Format with status indicators and priorities
    lines = ["# Todo List", ""]

    for todo in sorted_todos:
        status_indicator = {
            TodoStatus.PENDING: "[ ]",
            TodoStatus.IN_PROGRESS: "[→]",
            TodoStatus.COMPLETED: "[✓]",
        }[todo.status]

        priority_indicator = {
            TodoPriority.HIGH: "(high)",
            TodoPriority.MEDIUM: "(medium)",
            TodoPriority.LOW: "(low)",
        }[todo.priority]

        lines.append(f"{status_indicator} {todo.content} {priority_indicator}")

    return "\n".join(lines)


def format_todo_diff(old_todos: List[TodoItem], new_todos: List[TodoItem]) -> str:
    """Format the difference between two todo lists."""
    # Create dictionaries for easier comparison
    old_dict = {todo.id: todo for todo in old_todos}
    new_dict = {todo.id: todo for todo in new_todos}

    added = [todo for todo in new_todos if todo.id not in old_dict]
    removed = [todo for todo in old_todos if todo.id not in new_dict]
    changed = [
        (old_dict[todo_id], new_dict[todo_id])
        for todo_id in set(old_dict) & set(new_dict)
        if old_dict[todo_id].status != new_dict[todo_id].status
        or old_dict[todo_id].priority != new_dict[todo_id].priority
        or old_dict[todo_id].content != new_dict[todo_id].content
    ]

    if not (added or removed or changed):
        return "No changes to the todo list."

    lines = ["# Todo List Changes", ""]

    if added:
        lines.append("## Added")
        for todo in added:
            lines.append(f"+ {todo.content} ({todo.priority})")
        lines.append("")

    if removed:
        lines.append("## Removed")
        for todo in removed:
            lines.append(f"- {todo.content}")
        lines.append("")

    if changed:
        lines.append("## Changed")
        for old, new in changed:
            if old.content != new.content:
                lines.append(f"* Changed: '{old.content}' → '{new.content}'")
            if old.status != new.status:
                lines.append(
                    f"* Status: '{old.status}' → '{new.status}' for '{new.content}'"
                )
            if old.priority != new.priority:
                lines.append(
                    f"* Priority: '{old.priority}' → '{new.priority}' for '{new.content}'"
                )
        lines.append("")

    return "\n".join(lines)


def validate_todos(todos_data: List[Dict[str, Any]]) -> List[TodoItem]:
    """Validate and convert input data to TodoItem objects."""
    valid_todos = []

    for item in todos_data:
        try:
            # Ensure required fields exist
            if not all(key in item for key in ["content"]):
                raise ValueError(f"Missing required fields in todo item: {item}")

            # Use existing ID or create new one
            todo_id = item.get("id", str(uuid4()))

            # Parse status
            status_str = item.get("status", "pending").lower()
            if status_str not in [s.value for s in TodoStatus]:
                raise ValueError(f"Invalid status: {status_str}")
            status = TodoStatus(status_str)

            # Parse priority
            priority_str = item.get("priority", "medium").lower()
            if priority_str not in [p.value for p in TodoPriority]:
                raise ValueError(f"Invalid priority: {priority_str}")
            priority = TodoPriority(priority_str)

            # Create TodoItem
            valid_todos.append(
                TodoItem(
                    id=todo_id,
                    content=item["content"],
                    status=status,
                    priority=priority,
                )
            )
        except (ValueError, KeyError) as e:
            # Log the error but continue processing other items
            print(f"Error validating todo item: {e}")

    return valid_todos


@tool
def todo_read(context: AgentContext) -> str:
    """
    Read the current todo list for the session.

    Returns a formatted list of todos for the current session.
    """
    todos = load_todos(context.session_id)
    return format_todo_list(todos)


@tool
def todo_write(context: AgentContext, todos: List[Dict[str, Any]]) -> str:
    """
    Create or update todos in the current session.

    Args:
        todos: A list of todo items. Each item must have a "content" field and may also have
              "status" (pending, in_progress, completed), "priority" (high, medium, low),
              and "id" (to update an existing todo).

    Returns a summary of changes made to the todo list.
    """
    # Load existing todos
    old_todos = load_todos(context.session_id)

    # Validate and convert input
    new_todos = validate_todos(todos)

    # Preserve existing todos not in the update
    {todo.id for todo in old_todos}
    update_ids = {todo.id for todo in new_todos}

    # Add preserved todos (those not in the update)
    preserved_todos = [todo for todo in old_todos if todo.id not in update_ids]
    final_todos = preserved_todos + new_todos

    # Save the updated list
    save_todos(context.session_id, final_todos)

    # Return a diff showing what changed
    return format_todo_diff(old_todos, final_todos)
