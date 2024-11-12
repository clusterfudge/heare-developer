from enum import Enum
from pathlib import Path
import re
from typing import List, Optional, Dict, Set
import json


class TaskType(Enum):
    BUG_FIX = "bug"
    FEATURE = "feature"


class Task:
    def __init__(
        self,
        id: str,
        title: str,
        description: str,
        task_type: TaskType,
        milestone: str = "backlog",
        parent_task: Optional[str] = None,
        completed: bool = False,
    ):
        self.id = id
        self.title = title
        self.description = description
        self.task_type = task_type
        self.milestone = milestone
        self.parent_task = parent_task
        self.completed = completed


class Milestone:
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
        self.tasks: List[str] = []  # List of task IDs

    def to_dict(self) -> dict:
        return {"name": self.name, "description": self.description, "tasks": self.tasks}

    @classmethod
    def from_dict(cls, data: dict) -> "Milestone":
        milestone = cls(data["name"], data["description"])
        milestone.tasks = data["tasks"]
        return milestone


class Project:
    def __init__(self, name: str, path: Path):
        self.name = name
        self.path = Path(path)
        self.slug = self._generate_slug(name)
        self.tasks: Dict[str, Task] = {}
        self.milestones: Dict[str, Milestone] = {
            "backlog": Milestone("backlog", "Default milestone for unassigned tasks")
        }
        self.dependencies: Dict[
            str, Set[str]
        ] = {}  # task_id -> set of dependency task_ids
        self.next_task_id = 1

        # Create project directory structure
        self._initialize_project_structure()

    def _generate_slug(self, name: str) -> str:
        # Remove special characters and convert spaces to dashes
        cleaned = re.sub(r"[^\w\s-]", "", name)
        cleaned = cleaned.upper()
        words = cleaned.split()

        if len(words) == 2:
            # Two words: first three letters of first word + first two of second word
            return f"{words[0][:3]}{words[1][:2]}"

        # Single word or 3+ words: take first 4 letters of first word + P
        first_word = words[0]
        return f"{first_word[:4]}P"

    def _initialize_project_structure(self):
        """Create the initial project directory structure and files"""
        # Create main project directory if it doesn't exist
        self.path.mkdir(parents=True, exist_ok=True)

        # Create required directories
        (self.path / "tasks").mkdir(exist_ok=True)

        # Create initial files
        self._create_or_update_overview()
        self._create_or_update_tasks_file()
        self._create_or_update_milestones_file()
        self._create_or_update_dependencies_file()

    def _create_or_update_overview(self):
        overview_path = self.path / "OVERVIEW.md"
        if not overview_path.exists():
            with open(overview_path, "w") as f:
                f.write(f"# {self.name}\n\n")
                f.write("## Project Overview\n\n")
                f.write("*Add project description here*\n")

    def _create_or_update_tasks_file(self):
        tasks_path = self.path / "TASKS.md"
        with open(tasks_path, "w") as f:
            f.write(f"# Tasks for {self.name}\n\n")
            for task in sorted(self.tasks.values(), key=lambda t: t.id):
                status = "x" if task.completed else " "
                f.write(f"- [{status}] {task.id}: {task.title} ({task.milestone})\n")

    def _create_or_update_milestones_file(self):
        milestones_path = self.path / "MILESTONES.md"
        with open(milestones_path, "w") as f:
            f.write(f"# Milestones for {self.name}\n\n")
            for milestone in self.milestones.values():
                f.write(f"## {milestone.name}\n")
                f.write(f"{milestone.description}\n\n")
                f.write("### Tasks:\n")
                for task_id in milestone.tasks:
                    if task_id in self.tasks:
                        task = self.tasks[task_id]
                        status = "x" if task.completed else " "
                        f.write(f"- [{status}] {task.id}: {task.title}\n")
                f.write("\n")

    def _create_or_update_dependencies_file(self):
        deps_path = self.path / "DEPENDENCIES.json"
        with open(deps_path, "w") as f:
            json.dump(
                {task_id: list(deps) for task_id, deps in self.dependencies.items()},
                f,
                indent=2,
            )

    def create_task(
        self,
        title: str,
        description: str,
        task_type: TaskType,
        milestone: str = "backlog",
        parent_task: Optional[str] = None,
    ) -> Task:
        # Generate task ID
        if parent_task and parent_task in self.tasks:
            # Subtask: use parent's ID with additional number
            parent_subtasks = [
                t for t in self.tasks.values() if t.parent_task == parent_task
            ]
            subtask_num = len(parent_subtasks) + 1
            task_id = f"{parent_task}.{subtask_num}"
        else:
            # Main task
            task_id = f"{self.slug}-{self.next_task_id}"
            self.next_task_id += 1

        task = Task(
            id=task_id,
            title=title,
            description=description,
            task_type=task_type,
            milestone=milestone,
            parent_task=parent_task,
        )

        # Create task file
        task_path = self.path / "tasks" / f"{task_id}.md"
        with open(task_path, "w") as f:
            f.write(f"# {task.title}\n\n")
            f.write(f"**ID:** {task.id}\n")
            f.write(f"**Type:** {task.task_type.value}\n")
            f.write(f"**Milestone:** {task.milestone}\n")
            if task.parent_task:
                f.write(f"**Parent Task:** {task.parent_task}\n")
            f.write("\n## Description\n\n")
            f.write(f"{task.description}\n")
            f.write("\n## Exit Criteria\n\n")
            f.write("*Add exit criteria here*\n")

        self.tasks[task_id] = task
        self.milestones[milestone].tasks.append(task_id)

        # Update project files
        self._create_or_update_tasks_file()
        self._create_or_update_milestones_file()
        return task

    def add_milestone(self, name: str, description: str) -> Milestone:
        milestone = Milestone(name, description)
        self.milestones[name] = milestone
        self._create_or_update_milestones_file()
        return milestone

    def add_dependency(self, task_id: str, depends_on: str):
        """Add a dependency relationship between tasks"""
        if task_id not in self.tasks or depends_on not in self.tasks:
            raise ValueError("Both tasks must exist")

        if task_id not in self.dependencies:
            self.dependencies[task_id] = set()

        self.dependencies[task_id].add(depends_on)
        self._create_or_update_dependencies_file()

    def remove_dependency(self, task_id: str, depends_on: str):
        """Remove a dependency relationship between tasks"""
        if task_id in self.dependencies and depends_on in self.dependencies[task_id]:
            self.dependencies[task_id].remove(depends_on)
            if not self.dependencies[task_id]:
                del self.dependencies[task_id]
            self._create_or_update_dependencies_file()

    def get_task_dependencies(self, task_id: str) -> Set[str]:
        """Get all dependencies for a task"""
        return self.dependencies.get(task_id, set())

    def mark_task_complete(self, task_id: str, completed: bool = True):
        """Mark a task as complete or incomplete"""
        if task_id in self.tasks:
            self.tasks[task_id].completed = completed
            self._create_or_update_tasks_file()
            self._create_or_update_milestones_file()
