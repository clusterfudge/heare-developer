#!/usr/bin/env python3
import argparse
from pathlib import Path
from typing import Optional
from heare.pm.project import Project, TaskType

# Global config
PROJECTS_DIR = Path.home() / ".heare" / "projects"


def create_project(args):
    """Create a new project."""
    project_path = PROJECTS_DIR / args.name
    Project(args.name, project_path)
    print(f"Created project '{args.name}' at {project_path}")


def list_projects(args):
    """List all projects."""
    PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
    projects = [d for d in PROJECTS_DIR.iterdir() if d.is_dir()]

    if not projects:
        print("No projects found.")
        return

    print("Projects:")
    for project_dir in projects:
        print(f"- {project_dir.name}")


def get_project(project_name: str) -> Optional[Project]:
    """Helper function to load a project."""
    project_path = PROJECTS_DIR / project_name
    if not project_path.exists():
        print(f"Project '{project_name}' not found.")
        return None
    return Project(project_name, project_path)


def create_task(args):
    """Create a new task in a project."""
    project = get_project(args.project)
    if not project:
        return

    task_type = TaskType.FEATURE if args.type == "feature" else TaskType.BUG_FIX
    task = project.create_task(
        title=args.title,
        description=args.description,
        task_type=task_type,
        milestone=args.milestone,
        parent_task=args.parent,
    )
    print(f"Created task {task.id}: {task.title}")


def list_tasks(args):
    """List tasks in a project."""
    project = get_project(args.project)
    if not project:
        return

    print(f"\nTasks for project '{args.project}':")
    for task in sorted(project.tasks.values(), key=lambda t: t.id):
        status = "✓" if task.completed else " "
        print(f"[{status}] {task.id}: {task.title} ({task.milestone})")


def create_milestone(args):
    """Create a new milestone in a project."""
    project = get_project(args.project)
    if not project:
        return

    milestone = project.add_milestone(args.name, args.description)
    print(f"Created milestone '{milestone.name}'")


def list_milestones(args):
    """List milestones in a project."""
    project = get_project(args.project)
    if not project:
        return

    print(f"\nMilestones for project '{args.project}':")
    for milestone in project.milestones.values():
        print(f"\n## {milestone.name}")
        print(f"{milestone.description}")
        if milestone.tasks:
            print("Tasks:")
            for task_id in milestone.tasks:
                if task_id in project.tasks:
                    task = project.tasks[task_id]
                    status = "✓" if task.completed else " "
                    print(f"[{status}] {task.id}: {task.title}")


def complete_task(args):
    """Mark a task as complete."""
    project = get_project(args.project)
    if not project:
        return

    if args.task_id not in project.tasks:
        print(f"Task {args.task_id} not found in project.")
        return

    project.mark_task_complete(args.task_id, not args.uncomplete)
    status = "incomplete" if args.uncomplete else "complete"
    print(f"Marked task {args.task_id} as {status}")


def add_dependency(args):
    """Add a dependency between tasks."""
    project = get_project(args.project)
    if not project:
        return

    try:
        project.add_dependency(args.task_id, args.depends_on)
        print(f"Added dependency: {args.task_id} depends on {args.depends_on}")
    except ValueError as e:
        print(f"Error: {e}")


def main():
    parser = argparse.ArgumentParser(description="Project Management CLI")
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Create project command
    create_parser = subparsers.add_parser("create", help="Create a new project")
    create_parser.add_argument("name", help="Name of the project")
    create_parser.set_defaults(func=create_project)

    # List projects command
    list_parser = subparsers.add_parser("list", help="List all projects")
    list_parser.set_defaults(func=list_projects)

    # Create task command
    task_parser = subparsers.add_parser("task", help="Create a new task")
    task_parser.add_argument("project", help="Project name")
    task_parser.add_argument("title", help="Task title")
    task_parser.add_argument("--description", default="", help="Task description")
    task_parser.add_argument(
        "--type", choices=["feature", "bug"], default="feature", help="Task type"
    )
    task_parser.add_argument("--milestone", default="backlog", help="Milestone name")
    task_parser.add_argument("--parent", help="Parent task ID")
    task_parser.set_defaults(func=create_task)

    # List tasks command
    list_tasks_parser = subparsers.add_parser("tasks", help="List project tasks")
    list_tasks_parser.add_argument("project", help="Project name")
    list_tasks_parser.set_defaults(func=list_tasks)

    # Create milestone command
    milestone_parser = subparsers.add_parser("milestone", help="Create a new milestone")
    milestone_parser.add_argument("project", help="Project name")
    milestone_parser.add_argument("name", help="Milestone name")
    milestone_parser.add_argument("description", help="Milestone description")
    milestone_parser.set_defaults(func=create_milestone)

    # List milestones command
    list_milestones_parser = subparsers.add_parser(
        "milestones", help="List project milestones"
    )
    list_milestones_parser.add_argument("project", help="Project name")
    list_milestones_parser.set_defaults(func=list_milestones)

    # Complete task command
    complete_parser = subparsers.add_parser("complete", help="Mark a task as complete")
    complete_parser.add_argument("project", help="Project name")
    complete_parser.add_argument("task_id", help="Task ID")
    complete_parser.add_argument(
        "--uncomplete", action="store_true", help="Mark as incomplete instead"
    )
    complete_parser.set_defaults(func=complete_task)

    # Add dependency command
    dependency_parser = subparsers.add_parser("depend", help="Add a task dependency")
    dependency_parser.add_argument("project", help="Project name")
    dependency_parser.add_argument(
        "task_id", help="Task ID that depends on another task"
    )
    dependency_parser.add_argument(
        "depends_on", help="Task ID that must be completed first"
    )
    dependency_parser.set_defaults(func=add_dependency)

    args = parser.parse_args()

    if hasattr(args, "func"):
        args.func(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
