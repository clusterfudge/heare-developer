#!/usr/bin/env python3

import argparse
from pathlib import Path


class Project:
    def __init__(self, name=None):
        self.name = name if name else Path.cwd().name
        # If name was explicitly provided, use name.project, otherwise use .project
        self.project_dir = Path(f"{self.name}.project") if name else Path(".project")

    def create(self):
        """Create a new project directory structure"""
        if self.project_dir.exists():
            print(f"Project directory '{self.project_dir}' already exists")
            return False

        self.project_dir.mkdir(parents=True)
        return True

    def load(self):
        """Load an existing project"""
        if not self.project_dir.exists():
            print(f"Project directory '{self.project_dir}' does not exist")
            return False
        return True


def main():
    parser = argparse.ArgumentParser(description="Heare Project Management Tool")
    parser.add_argument("--name", help="Project name")
    parser.add_argument("--create", action="store_true", help="Create a new project")

    args = parser.parse_args()

    project = Project(args.name)

    if args.create:
        if project.create():
            print(f"Created new project: {project.name}")
    else:
        if project.load():
            print(f"Loaded project: {project.name}")


if __name__ == "__main__":
    main()
