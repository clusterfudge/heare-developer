# Google Integration Tools Documentation

This document provides examples and usage information for the Google API integration tools available in the heare framework, specifically for Gmail and Google Calendar.

## Prerequisites

Before using these tools, you must set up authentication with Google:

1. Go to the [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (or select an existing one)
3. Enable the Gmail API and Google Calendar API for your project
4. Create OAuth 2.0 credentials:
   - Navigate to "APIs & Services" > "Credentials"
   - Click "Create Credentials" > "OAuth client ID"
   - Select "Desktop app" as the application type
   - Name your credential and click "Create"
5. Download the credentials JSON file
6. Save the downloaded file as `~/.hdev/credentials/google_clientid.json`

### Remote/Headless Authentication

If you're running the application on a remote server or in a headless environment where browser-based authentication isn't suitable, you can use the device flow authentication method instead:

```bash
# Set authentication method to device flow
export HEARE_GOOGLE_AUTH_METHOD="device"
```

For detailed instructions on remote authentication, see the [Remote Google Authentication](google_remote_auth.md) documentation.

## Gmail Tools

### 1. Gmail Search

Search for emails in Gmail using Google's search syntax.

```python
gmail_search(query="from:example@gmail.com subject:meeting", max_results=5)
```

**Parameters:**
- `query`: Gmail search query (follows Gmail search syntax)
- `max_results`: Maximum number of results to return (default: 10)

**Common search operators:**
- `from:` - Search for messages from a specific sender
- `to:` - Search for messages to a specific recipient
- `subject:` - Search for messages with specific text in the subject
- `is:unread` - Search for unread messages
- `is:starred` - Search for starred messages
- `after:YYYY/MM/DD` - Search for messages after a specific date
- `before:YYYY/MM/DD` - Search for messages before a specific date
- `has:attachment` - Search for messages with attachments

### 2. Gmail Read

Read the content of a specific email by its ID.

```python
gmail_read(email_id="1234abcd")
```

**Parameters:**
- `email_id`: The ID of the email to read (obtained from gmail_search)

### 3. Gmail Send

Send an email via Gmail.

```python
gmail_send(
    to="recipient@example.com",
    subject="Meeting Reminder",
    body="Don't forget our meeting tomorrow at 2pm.",
    cc="colleague@example.com",
    bcc="manager@example.com"
)
```

**Parameters:**
- `to`: Email address(es) of the recipient(s), comma-separated for multiple
- `subject`: Subject line of the email
- `body`: Body text of the email
- `cc`: Email address(es) to CC, comma-separated for multiple (optional)
- `bcc`: Email address(es) to BCC, comma-separated for multiple (optional)

## Google Calendar Tools

### Calendar Configuration

Before using the calendar tools, you should set up your calendar configuration to specify which calendars you want to use.

```python
calendar_setup()
```

This interactive tool will:
1. List all available calendars in your Google account
2. Let you select which ones should be enabled
3. Save the configuration to `~/.config/hdev/google-calendar.yml`

You can also view your current calendar configuration:

```python
calendar_list_calendars()
```

This will show all available calendars and indicate which ones are currently enabled in your configuration.

### 1. Calendar List Events

List upcoming events from Google Calendar.

```python
# List events from all configured calendars
calendar_list_events(days=7)

# List events from a specific calendar
calendar_list_events(days=7, calendar_id="primary")
```

**Parameters:**
- `days`: Number of days to look ahead (default: 7)
- `calendar_id`: ID of the calendar to query (default: None, which uses all enabled calendars)

### 2. Calendar Create Event

Create a new event in Google Calendar.

```python
# Create event in primary calendar
calendar_create_event(
    summary="Team Meeting",
    start_time="2023-10-15T14:00:00",
    end_time="2023-10-15T15:00:00",
    description="Weekly team sync",
    location="Conference Room A",
    attendees="colleague1@example.com,colleague2@example.com"
)

# Create event in a specific calendar
calendar_create_event(
    summary="Team Meeting",
    start_time="2023-10-15T14:00:00",
    end_time="2023-10-15T15:00:00",
    description="Weekly team sync",
    location="Conference Room A",
    attendees="colleague1@example.com,colleague2@example.com",
    calendar_id="calendar_id_here"
)
```

**Parameters:**
- `summary`: Title/summary of the event
- `start_time`: Start time in ISO format (YYYY-MM-DDTHH:MM:SS) or date (YYYY-MM-DD) for all-day events
- `end_time`: End time in ISO format (YYYY-MM-DDTHH:MM:SS) or date (YYYY-MM-DD) for all-day events
- `description`: Description of the event (optional)
- `location`: Location of the event (optional)
- `attendees`: Comma-separated list of email addresses to invite (optional)
- `calendar_id`: ID of the calendar to add the event to (default: None, which uses primary calendar from configuration)

### 3. Calendar Delete Event

Delete an event from Google Calendar.

```python
# Delete an event when you know the calendar ID
calendar_delete_event(event_id="event123abc", calendar_id="calendar_id_here")

# Delete an event without specifying calendar ID
# (will search all enabled calendars and prompt for confirmation)
calendar_delete_event(event_id="event123abc")
```

**Parameters:**
- `event_id`: ID of the event to delete
- `calendar_id`: ID of the calendar containing the event (default: None, which will search in all enabled calendars and prompt for confirmation)

## Calendar Configuration File

The calendar configuration is stored in YAML format at `~/.config/hdev/google-calendar.yml`. The file structure looks like:

```yaml
calendars:
- id: primary@example.com
  name: My Calendar
  enabled: true
  primary: true
- id: secondary@group.calendar.google.com
  name: Team Calendar
  enabled: true
  primary: false
- id: holidays@group.calendar.google.com
  name: Holidays
  enabled: false
  primary: false
```

You can manually edit this file if needed, or use the `calendar_setup()` and `calendar_list_calendars()` tools to manage your configuration.

## Authentication Notes

- The first time you use a Gmail or Calendar tool, you'll be prompted to authorize the application
- By default, a browser window will open where you'll need to sign in and grant permissions
- In remote/headless environments, a device flow option is available that provides a URL to visit on another device
- After authorization, token files will be saved in `~/.hdev/credentials/` for future use:
  - `gmail_token.pickle` for Gmail API access
  - `calendar_token.pickle` for Calendar API access
- Separate token files are used for Gmail and Calendar to minimize requested permissions
- You can use the Google Token Manager script to generate, export, or import tokens:
  ```bash
  # Generate tokens using device flow
  python scripts/google_token_manager.py generate gmail
  
  # Export tokens (to file or stdout)
  python scripts/google_token_manager.py export gmail --output ~/gmail_token.txt  # to file
  python scripts/google_token_manager.py export gmail                            # to stdout
  
  # Import tokens (from file or stdin)
  python scripts/google_token_manager.py import gmail --input ~/gmail_token.txt  # from file
  python scripts/google_token_manager.py import gmail                            # from stdin
  
  # Direct transfer over SSH (more secure)
  python scripts/google_token_manager.py export gmail | ssh user@remote-host "python scripts/google_token_manager.py import gmail"
  ```

## Error Handling

All tools include comprehensive error handling. If something goes wrong, the tool will return an error message describing the issue.

Common errors include:
- Authentication failures
- Network connectivity issues
- Invalid parameters
- Permission issues
- Rate limiting

## Security Considerations

- Authentication tokens are stored locally in your home directory
- The application only requests the minimum permissions needed for each API
- No data is transmitted to third parties
- All communication is directly between your local machine and Google's APIs