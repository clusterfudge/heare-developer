#!/usr/bin/env python
"""
Google Token Manager for Heare

This script helps manage Google API tokens for remote/headless environments.
It provides functionality to:
1. Generate tokens using device flow authentication
2. Export tokens to a portable format or to stdout
3. Import tokens from a portable format or from stdin

Usage:
  python google_token_manager.py generate gmail
  python google_token_manager.py generate calendar

  # Export options
  python google_token_manager.py export gmail --output ~/gmail_token.txt  # to file
  python google_token_manager.py export gmail                            # to stdout

  # Import options
  python google_token_manager.py import gmail --input ~/gmail_token.txt  # from file
  python google_token_manager.py import gmail                            # from stdin

  # Pipeline example (one-line transfer from local to remote):
  python google_token_manager.py export gmail | ssh user@remote-host "python scripts/google_token_manager.py import gmail"
"""

import argparse
import sys
from pathlib import Path

# Add the parent directory to the sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from heare.developer.tools.gcal import CALENDAR_SCOPES
from heare.developer.tools.gmail import GMAIL_SCOPES
from heare.developer.tools.google_shared import (
    get_credentials_using_device_flow,
    export_token,
    import_token,
    get_auth_info,
    ensure_dirs,
)


def parse_args():
    parser = argparse.ArgumentParser(description="Google Token Manager for Heare")
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # Generate token parser
    generate_parser = subparsers.add_parser(
        "generate", help="Generate a new token using device flow"
    )
    generate_parser.add_argument(
        "service",
        choices=["gmail", "calendar"],
        help="Which Google service to generate a token for",
    )

    # Export token parser
    export_parser = subparsers.add_parser(
        "export", help="Export a token to a portable format"
    )
    export_parser.add_argument(
        "service",
        choices=["gmail", "calendar"],
        help="Which Google service token to export",
    )
    export_parser.add_argument(
        "--output",
        "-o",
        help="Output file path for the exported token (omit to output to stdout)",
    )

    # Import token parser
    import_parser = subparsers.add_parser(
        "import", help="Import a token from a portable format"
    )
    import_parser.add_argument(
        "service",
        choices=["gmail", "calendar"],
        help="Which Google service token to import",
    )
    import_parser.add_argument(
        "--input",
        "-i",
        help="Input file path containing the exported token (omit to read from stdin)",
    )

    return parser.parse_args()


def main():
    args = parse_args()
    auth_info = get_auth_info()

    if not args.command:
        print("No command specified. Use --help for usage information.")
        return

    # Determine which token file to use based on service
    if args.service == "gmail":
        scopes = GMAIL_SCOPES
        token_file = auth_info["gmail_token_file"]
    else:  # calendar
        scopes = CALENDAR_SCOPES
        token_file = auth_info["calendar_token_file"]

    # Execute the appropriate command
    if args.command == "generate":
        print(f"Generating {args.service} token using device flow...")
        get_credentials_using_device_flow(
            scopes, auth_info["client_secrets_file"], token_file
        )
        print("\nToken generated and saved successfully!")

    elif args.command == "export":
        if args.output:
            print(
                f"Exporting {args.service} token to {args.output}...", file=sys.stderr
            )
            export_token(token_file, args.output)
        else:
            # Export to stdout
            encoded_token = export_token(token_file)
            print(encoded_token)

    elif args.command == "import":
        if args.input:
            print(
                f"Importing {args.service} token from {args.input}...", file=sys.stderr
            )
            import_token(token_file, input_file=args.input)
        else:
            # Import from stdin
            print(f"Reading {args.service} token from stdin...", file=sys.stderr)
            encoded_token = sys.stdin.read().strip()
            import_token(token_file, encoded_token=encoded_token)

    else:
        print(f"Unknown command: {args.command}")


if __name__ == "__main__":
    # Ensure directories exist
    ensure_dirs()
    main()
