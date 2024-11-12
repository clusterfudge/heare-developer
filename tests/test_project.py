import pytest
from pathlib import Path
import json
import shutil
from heare.pm.project import Project, TaskType


@pytest.fixture
def temp_project_dir(tmp_path):
    """Create a temporary directory for project files"""
    project_dir = tmp_path / "test-project"
    project_dir.mkdir()
    yield project_dir
    # Cleanup
    if project_dir.exists():
        shutil.rmtree(project_dir)


@pytest.fixture
def sample_project(temp_project_dir):
    """Create a sample project for testing"""
    return Project("Test Project Alpha", temp_project_dir)


def test_project_initialization(temp_project_dir):
    """Test basic project creation and file structure"""
    project = Project("Test Project", temp_project_dir)

    # Test slug generation
    assert project.slug == "TESPR"

    # Test directory structure
    assert (temp_project_dir / "OVERVIEW.md").exists()
    assert (temp_project_dir / "TASKS.md").exists()
    assert (temp_project_dir / "MILESTONES.md").exists()
    assert (temp_project_dir / "DEPENDENCIES.json").exists()
    assert (temp_project_dir / "tasks").is_dir()


def test_slug_generation():
    """Test different cases of slug generation"""
    test_cases = [
        ("Simple Project", "SIMPR"),
        ("OneWord", "ONEWP"),
        ("Project Management", "PROMA"),
        ("Test Project", "TESPR"),
        ("My-Special.Project!", "MY-SP"),
    ]

    for name, expected_slug in test_cases:
        project = Project(name, Path("/tmp"))  # Path doesn't matter for this test
        assert project.slug == expected_slug, f"Failed for project name: {name}"


def test_task_creation(sample_project):
    """Test creating tasks and subtasks"""
    # Create main task
    task1 = sample_project.create_task(
        title="Main Task",
        description="This is a main task",
        task_type=TaskType.FEATURE,
        milestone="backlog",
    )

    assert task1.id == f"{sample_project.slug}-1"
    assert task1.title == "Main Task"
    assert task1.parent_task is None

    # Create subtask
    subtask = sample_project.create_task(
        title="Subtask",
        description="This is a subtask",
        task_type=TaskType.FEATURE,
        milestone="backlog",
        parent_task=task1.id,
    )

    assert subtask.id == f"{task1.id}.1"
    assert subtask.parent_task == task1.id

    # Verify task files were created
    task_dir = sample_project.path / "tasks"
    assert (task_dir / f"{task1.id}.md").exists()
    assert (task_dir / f"{subtask.id}.md").exists()


def test_milestone_management(sample_project):
    """Test milestone creation and task assignment"""
    # Add milestone
    sample_project.add_milestone("v1.0", "First Release")
    assert "v1.0" in sample_project.milestones

    # Create task in milestone
    task = sample_project.create_task(
        title="Milestone Task",
        description="Task in milestone",
        task_type=TaskType.FEATURE,
        milestone="v1.0",
    )

    assert task.milestone == "v1.0"
    assert task.id in sample_project.milestones["v1.0"].tasks


def test_dependency_management(sample_project):
    """Test adding and removing task dependencies"""
    # Create two tasks
    task1 = sample_project.create_task(
        title="Task 1", description="First task", task_type=TaskType.FEATURE
    )

    task2 = sample_project.create_task(
        title="Task 2", description="Second task", task_type=TaskType.FEATURE
    )

    # Add dependency
    sample_project.add_dependency(task2.id, task1.id)

    # Verify dependency
    deps = sample_project.get_task_dependencies(task2.id)
    assert task1.id in deps

    # Check dependencies file
    with open(sample_project.path / "DEPENDENCIES.json") as f:
        deps_data = json.load(f)
        assert task2.id in deps_data
        assert task1.id in deps_data[task2.id]

    # Remove dependency
    sample_project.remove_dependency(task2.id, task1.id)
    deps = sample_project.get_task_dependencies(task2.id)
    assert not deps


def test_task_completion(sample_project):
    """Test marking tasks as complete"""
    task = sample_project.create_task(
        title="Test Task", description="Task to complete", task_type=TaskType.FEATURE
    )

    # Mark as complete
    sample_project.mark_task_complete(task.id)
    assert sample_project.tasks[task.id].completed

    # Check TASKS.md for completion status
    with open(sample_project.path / "TASKS.md") as f:
        content = f.read()
        assert f"- [x] {task.id}: {task.title}" in content

    # Mark as incomplete
    sample_project.mark_task_complete(task.id, False)
    assert not sample_project.tasks[task.id].completed


def test_invalid_dependency(sample_project):
    """Test adding invalid dependencies"""
    task = sample_project.create_task(
        title="Task", description="Task", task_type=TaskType.FEATURE
    )

    with pytest.raises(ValueError):
        sample_project.add_dependency(task.id, "INVALID-1")

    with pytest.raises(ValueError):
        sample_project.add_dependency("INVALID-1", task.id)


def test_file_content_format(sample_project):
    """Test the format of generated files"""
    # Create a task with various attributes
    task = sample_project.create_task(
        title="Test Task",
        description="Test Description",
        task_type=TaskType.FEATURE,
        milestone="backlog",
    )

    # Check TASKS.md format
    with open(sample_project.path / "TASKS.md") as f:
        tasks_content = f.read()
        assert "# Tasks for Test Project Alpha" in tasks_content
        assert f"- [ ] {task.id}: {task.title}" in tasks_content

    # Check individual task file format
    with open(sample_project.path / "tasks" / f"{task.id}.md") as f:
        task_content = f.read()
        assert "# Test Task" in task_content
        assert "**Type:** feature" in task_content
        assert "**Milestone:** backlog" in task_content
        assert "Test Description" in task_content
