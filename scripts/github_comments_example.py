#!/usr/bin/env python3
"""
Example script demonstrating the use of GitHub comment tools.

This script shows how to use the GitHub comment tools to interact with
pull request comments without webhooks.
"""

import argparse
import sys
from pathlib import Path

# Add the parent directory to the path so we can import heare
sys.path.append(str(Path(__file__).resolve().parent.parent))

from heare.developer.context import AgentContext
from heare.developer.tools.github_comments import (
    github_list_pr_comments,
    github_get_comment,
    github_add_pr_comment,
    github_list_new_comments,
)


class SimpleContext(AgentContext):
    """A simple Context implementation for demonstration purposes."""

    def __init__(self):
        self.history = []

    def emit(self, message):
        """Print messages to stdout."""
        print(message)
        self.history.append(message)

    def report_usage(self, usage, model_info=None):
        """No-op implementation."""


def main():
    """Execute the script with command-line arguments."""
    parser = argparse.ArgumentParser(description="GitHub comment tools example")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # List PR comments
    list_parser = subparsers.add_parser("list", help="List PR comments")
    list_parser.add_argument("pr_number", help="PR number")
    list_parser.add_argument(
        "--type",
        choices=["all", "inline", "conversation", "review"],
        default="all",
        help="Type of comments to list",
    )
    list_parser.add_argument("--repo", help="Repository in format OWNER/REPO")

    # Get specific comment
    get_parser = subparsers.add_parser("get", help="Get a specific comment")
    get_parser.add_argument("comment_id", help="Comment ID")
    get_parser.add_argument(
        "--type",
        dest="comment_type",
        choices=["pr", "issue", "review"],
        default="pr",
        help="Type of comment",
    )
    get_parser.add_argument("--repo", help="Repository in format OWNER/REPO")

    # Add PR comment
    add_parser = subparsers.add_parser("add", help="Add a PR comment")
    add_parser.add_argument("pr_number", help="PR number")
    add_parser.add_argument("--body", required=True, help="Comment text")
    add_parser.add_argument("--commit-id", help="Commit SHA (for inline comments)")
    add_parser.add_argument("--path", help="File path (for inline comments)")
    add_parser.add_argument(
        "--line", type=int, help="Line number (for inline comments)"
    )
    add_parser.add_argument("--reply-to", help="Comment ID to reply to")
    add_parser.add_argument("--repo", help="Repository in format OWNER/REPO")

    # List new comments
    new_parser = subparsers.add_parser("new", help="List new PR comments")
    new_parser.add_argument("pr_number", help="PR number")
    new_parser.add_argument(
        "--since", help="ISO 8601 date (e.g., 2023-04-01T00:00:00Z)"
    )
    new_parser.add_argument("--repo", help="Repository in format OWNER/REPO")

    args = parser.parse_args()
    context = SimpleContext()

    if args.command == "list":
        result = github_list_pr_comments(
            context, args.pr_number, type=args.type, repo=args.repo
        )
        print(result)
    elif args.command == "get":
        result = github_get_comment(
            context, args.comment_id, comment_type=args.comment_type, repo=args.repo
        )
        print(result)
    elif args.command == "add":
        result = github_add_pr_comment(
            context,
            args.pr_number,
            body=args.body,
            commit_id=args.commit_id,
            path=args.path,
            line=args.line,
            reply_to=args.reply_to,
            repo=args.repo,
        )
        print(result)
    elif args.command == "new":
        result = github_list_new_comments(
            context, args.pr_number, since=args.since, repo=args.repo
        )
        print(result)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
