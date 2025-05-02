#!/usr/bin/env python3
"""
Demo script for the session management features.
Shows how to list and resume sessions programmatically.
"""

import argparse
import os
import sys

# Add the parent directory to the path so we can import heare modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from heare.developer.tools.sessions import (
    list_sessions,
    print_session_list,
    resume_session,
)


def main():
    """Main entry point for the session manager demo."""
    parser = argparse.ArgumentParser(description="Heare Developer Session Manager Demo")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # List command
    list_parser = subparsers.add_parser("list", help="List available sessions")
    list_parser.add_argument(
        "--workdir",
        "-w",
        help="Filter sessions by working directory (default: current directory)",
        default=os.getcwd(),
    )

    # Resume command
    resume_parser = subparsers.add_parser("resume", help="Resume a previous session")
    resume_parser.add_argument(
        "session_id", help="ID or prefix of the session to resume"
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    if args.command == "list":
        sessions = list_sessions(workdir=args.workdir)
        print_session_list(sessions)
    elif args.command == "resume":
        resume_session(args.session_id)


if __name__ == "__main__":
    main()
