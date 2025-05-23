#!/usr/bin/env python3
"""
Example script demonstrating the gmail_forward tool.

This script shows how to use the gmail_forward tool to forward Gmail messages
and threads to specified recipients.
"""

from heare.developer.context import AgentContext


def main():
    """Demonstrate gmail_forward functionality."""

    # Create a context (this would normally be provided by the agent)
    AgentContext()

    print("Gmail Forward Tool Examples")
    print("=" * 40)

    # Example 1: Forward a single message
    print("\n1. Forward a single message:")
    print("   gmail_forward(context, 'msg_123', 'colleague@example.com')")
    print("   -> Forwards the message with ID 'msg_123' to 'colleague@example.com'")

    # Example 2: Forward with additional message
    print("\n2. Forward with additional message:")
    print("   gmail_forward(")
    print("       context,")
    print("       'msg_123',")
    print("       'team@example.com',")
    print("       additional_message='Please review this request.'")
    print("   )")
    print("   -> Adds your comment at the top of the forwarded content")

    # Example 3: Forward to multiple recipients
    print("\n3. Forward to multiple recipients:")
    print("   gmail_forward(")
    print("       context,")
    print("       'msg_123',")
    print("       'alice@example.com,bob@example.com',")
    print("       cc='manager@example.com'")
    print("   )")
    print("   -> Sends to multiple recipients with CC")

    # Example 4: Forward an entire thread
    print("\n4. Forward an entire thread:")
    print("   gmail_forward(")
    print("       context,")
    print("       'thread_456',")
    print("       'partner@external.com',")
    print("       additional_message='Full conversation history for context.'")
    print("   )")
    print("   -> Forwards all messages in the thread chronologically")

    print("\nNote: To actually forward emails, you need:")
    print("- Valid Gmail API credentials")
    print("- Existing message or thread IDs")
    print("- Valid recipient email addresses")

    print("\nTo test with real emails, replace the example IDs with actual")
    print("message or thread IDs from your Gmail account.")


if __name__ == "__main__":
    main()
