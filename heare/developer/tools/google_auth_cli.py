"""
Google authentication CLI tools for Heare

This module provides CLI tools to manage Google API tokens for remote/headless environments.
It offers functionality to:
1. Generate tokens using device flow authentication
2. Export tokens to a portable format or to stdout
3. Import tokens from a portable format or from stdin

These tools are designed to be used as subcommands on the hdev entry point:
  hdev gauth generate gmail
  hdev gauth generate calendar

  # Export options
  hdev gauth export gmail --output ~/gmail_token.txt  # to file
  hdev gauth export gmail                            # to stdout

  # Import options
  hdev gauth import gmail --input ~/gmail_token.txt  # from file
  hdev gauth import gmail                            # from stdin
"""

import argparse
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional
from rich.console import Console
from rich.panel import Panel

from heare.developer.tools.gcal import CALENDAR_SCOPES
from heare.developer.tools.gmail import GMAIL_SCOPES
from heare.developer.tools.google_shared import (
    get_credentials_using_device_flow,
    export_token,
    import_token,
    get_auth_info,
    ensure_dirs,
)

console = Console()


def print_message(message: str):
    """Print a message to the console."""
    console.print(message)


def google_auth(user_input: str = "", tool_result_buffer: List[dict] = None, **kwargs):
    """Manage Google authentication tokens.

    This command allows you to generate, export, and import Google API tokens.
    
    Examples:
      gauth generate gmail - Generate a token for Gmail API
      gauth export gmail --output ~/gmail_token.txt - Export Gmail token to file
      gauth import gmail --input ~/gmail_token.txt - Import Gmail token from file
    """
    tool_result_buffer = tool_result_buffer or []
    
    # Parse arguments
    parts = user_input.strip().split()
    
    if len(parts) < 1:
        print_message(
            "## Google Authentication Tools\n\n"
            "Usage: gauth <command> [options]\n\n"
            "Available commands:\n"
            "- **generate** - Generate a new token using device flow\n"
            "- **export** - Export a token to a portable format\n"
            "- **import** - Import a token from a portable format\n\n"
            "For more information, use: gauth <command> --help"
        )
        return
    
    # Handle subcommands
    subcommand = parts[0]
    args = parts[1:]
    
    if subcommand == "generate":
        handle_generate(args, tool_result_buffer)
    elif subcommand == "export":
        handle_export(args, tool_result_buffer)
    elif subcommand == "import":
        handle_import(args, tool_result_buffer)
    else:
        print_message(f"Unknown subcommand: {subcommand}\n\n"
                     "Available commands: generate, export, import")


def handle_generate(args: List[str], tool_result_buffer: List[dict]):
    """Handle the generate subcommand."""
    if not args or args[0] not in ["gmail", "calendar"]:
        print_message("Usage: gauth generate <service>\n\n"
                     "Where <service> is one of: gmail, calendar")
        return
    
    service = args[0]
    auth_info = get_auth_info()
    ensure_dirs()
    
    # Determine which token file and scopes to use
    if service == "gmail":
        scopes = GMAIL_SCOPES
        token_file = auth_info["gmail_token_file"]
    else:  # calendar
        scopes = CALENDAR_SCOPES
        token_file = auth_info["calendar_token_file"]
    
    print_message(f"Generating {service} token using device flow...")
    
    try:
        get_credentials_using_device_flow(
            scopes, auth_info["client_secrets_file"], token_file
        )
        print_message("\nToken generated and saved successfully!")
        tool_result_buffer.append({
            "role": "user", 
            "content": f"Successfully generated and saved {service} token."
        })
    except Exception as e:
        print_message(f"Error generating token: {str(e)}")
        tool_result_buffer.append({
            "role": "user", 
            "content": f"Error generating {service} token: {str(e)}"
        })


def handle_export(args: List[str], tool_result_buffer: List[dict]):
    """Handle the export subcommand."""
    if not args or args[0] not in ["gmail", "calendar"]:
        print_message("Usage: gauth export <service> [--output PATH]\n\n"
                     "Where <service> is one of: gmail, calendar")
        return
    
    service = args[0]
    auth_info = get_auth_info()
    ensure_dirs()
    
    # Determine which token file to use
    if service == "gmail":
        token_file = auth_info["gmail_token_file"]
    else:  # calendar
        token_file = auth_info["calendar_token_file"]
    
    # Check for output file parameter
    output_file = None
    if len(args) > 1 and (args[1] == "--output" or args[1] == "-o") and len(args) > 2:
        output_file = args[2]
    
    try:
        if output_file:
            print_message(f"Exporting {service} token to {output_file}...")
            export_token(token_file, output_file)
            print_message(f"Token exported to {output_file}")
            tool_result_buffer.append({
                "role": "user", 
                "content": f"Successfully exported {service} token to {output_file}."
            })
        else:
            # Export to stdout
            encoded_token = export_token(token_file)
            console.print(
                Panel(
                    encoded_token,
                    title=f"{service.capitalize()} Token",
                    border_style="green",
                )
            )
            # Don't add the actual token to the tool buffer for security reasons
            tool_result_buffer.append({
                "role": "user", 
                "content": f"Successfully exported {service} token to stdout."
            })
    except Exception as e:
        print_message(f"Error exporting token: {str(e)}")
        tool_result_buffer.append({
            "role": "user", 
            "content": f"Error exporting {service} token: {str(e)}"
        })


def handle_import(args: List[str], tool_result_buffer: List[dict]):
    """Handle the import subcommand."""
    if not args or args[0] not in ["gmail", "calendar"]:
        print_message("Usage: gauth import <service> [--input PATH]\n\n"
                     "Where <service> is one of: gmail, calendar")
        return
    
    service = args[0]
    auth_info = get_auth_info()
    ensure_dirs()
    
    # Determine which token file to use
    if service == "gmail":
        token_file = auth_info["gmail_token_file"]
    else:  # calendar
        token_file = auth_info["calendar_token_file"]
    
    # Check for input file parameter
    input_file = None
    if len(args) > 1 and (args[1] == "--input" or args[1] == "-i") and len(args) > 2:
        input_file = args[2]
    
    try:
        if input_file:
            print_message(f"Importing {service} token from {input_file}...")
            import_token(token_file, input_file=input_file)
            print_message(f"Token imported from {input_file} and saved successfully")
            tool_result_buffer.append({
                "role": "user", 
                "content": f"Successfully imported {service} token from {input_file}."
            })
        else:
            # Import from stdin
            print_message(f"Reading {service} token from stdin...")
            print_message("Paste your token and press Ctrl+D when finished:")
            encoded_token = sys.stdin.read().strip()
            import_token(token_file, encoded_token=encoded_token)
            print_message(f"Token imported from stdin and saved successfully")
            tool_result_buffer.append({
                "role": "user", 
                "content": f"Successfully imported {service} token from stdin."
            })
    except Exception as e:
        print_message(f"Error importing token: {str(e)}")
        tool_result_buffer.append({
            "role": "user", 
            "content": f"Error importing {service} token: {str(e)}"
        })


# CLI Tools to be registered
GOOGLE_AUTH_CLI_TOOLS = {
    "gauth": {
        "func": google_auth,
        "docstring": "Manage Google authentication tokens",
        "aliases": ["google-auth", "google_auth"],
    },
}