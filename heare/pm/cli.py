#!/usr/bin/env python3
import argparse


def create_project(args):
    """Create a new project."""
    # TODO: Implement project creation


def list_projects(args):
    """List all projects."""
    # TODO: Implement project listing


def main():
    parser = argparse.ArgumentParser(description="Project Management CLI")
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Create project command
    create_parser = subparsers.add_parser("create", help="Create a new project")
    create_parser.add_argument("name", help="Name of the project")
    create_parser.add_argument("--description", help="Project description")
    create_parser.set_defaults(func=create_project)

    # List projects command
    list_parser = subparsers.add_parser("list", help="List all projects")
    list_parser.set_defaults(func=list_projects)

    args = parser.parse_args()

    if hasattr(args, "func"):
        args.func(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
