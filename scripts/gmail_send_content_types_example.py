#!/usr/bin/env python3
"""
Example script demonstrating the gmail_send tool with content type support.

This script shows how to use the gmail_send tool to send emails with different
content types: plain text, HTML, and Markdown.
"""

from heare.developer.context import AgentContext


def main():
    """Demonstrate gmail_send content type functionality."""

    # Create a context (this would normally be provided by the agent)
    AgentContext()

    print("Gmail Send Content Types Examples")
    print("=" * 50)

    # Example 1: Plain text email (default)
    print("\n1. Plain text email (default behavior):")
    plain_text_example = """gmail_send(
    context,
    to='recipient@example.com',
    subject='Plain Text Email',
    body='This is a plain text email.\\n\\nIt preserves line breaks\\nbut has no formatting.',
    content_type='plain'  # optional, this is the default
)"""
    print(plain_text_example)

    # Example 2: HTML email
    print("\n2. HTML email:")
    html_example = """gmail_send(
    context,
    to='recipient@example.com',
    subject='HTML Email with Formatting',
    body='<h1>Important Update</h1><p>This email has <strong>bold</strong> and <em>italic</em> text.</p><ul><li>Feature 1</li><li>Feature 2</li></ul>',
    content_type='html'
)"""
    print(html_example)

    # Example 3: Markdown email (converted to HTML)
    print("\n3. Markdown email (automatically converted to HTML):")
    markdown_example = """gmail_send(
    context,
    to='recipient@example.com',
    subject='Markdown Email',
    body='''# Project Update

We've made great progress on the project:

## Completed Tasks
- [x] Feature development
- [x] Testing
- [x] Documentation

## Next Steps
- [ ] Code review
- [ ] Deployment

Please review the [project documentation](https://example.com/docs) for more details.

**Note**: This will be automatically converted to HTML for better email client compatibility.''',
    content_type='markdown'
)"""
    print(markdown_example)

    # Example 4: Combined with other features
    print("\n4. Markdown email with CC and BCC:")
    combined_example = """gmail_send(
    context,
    to='team@example.com',
    subject='Weekly Status Report',
    body='''# Weekly Status Report

## Achievements
- Completed user authentication module
- Fixed 3 critical bugs
- Improved performance by 15%

## Challenges
- Database migration took longer than expected
- Need additional resources for next sprint

## Action Items
1. Schedule code review session
2. Update project timeline
3. Prepare demo for stakeholders

---
*This report was generated automatically.*''',
    cc='manager@example.com',
    bcc='archive@example.com',
    content_type='markdown'
)"""
    print(combined_example)

    print("\nSupported content types:")
    print("- 'plain' (default): Send as plain text")
    print("- 'html': Send as HTML with formatting")
    print("- 'markdown': Convert Markdown to HTML and send as HTML")

    print("\nNote: To actually send emails, you need:")
    print("- Valid Gmail API credentials (gmail_token.pickle)")
    print("- Valid recipient email addresses")
    print("- Proper Gmail API permissions")

    print("\nMarkdown features supported include:")
    print("- Headers (# ## ###)")
    print("- Bold (**text**) and italic (*text*)")
    print("- Lists (- item or 1. item)")
    print("- Links ([text](url))")
    print("- Inline code (`code`)")
    print("- Code blocks (```)")
    print("- Horizontal rules (---)")
    print("- And more standard Markdown syntax")


if __name__ == "__main__":
    main()
