import pickle
import yaml
import os
from pathlib import Path
from typing import List
from datetime import datetime, timedelta
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

from . import google_remote_auth

from heare.developer.context import AgentContext
from .framework import tool

# Define the scopes needed for each API
GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.modify",
]
CALENDAR_SCOPES = [
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/calendar.events",
]

# Configuration paths
CONFIG_DIR = Path.home() / ".config" / "hdev"
CALENDAR_CONFIG_PATH = CONFIG_DIR / "google-calendar.yml"
CREDENTIALS_DIR = Path.home() / ".hdev" / "credentials"


def ensure_config_dir():
    """Ensure the configuration directory exists."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def get_calendar_config():
    """Get the calendar configuration.

    Returns:
        Dictionary containing calendar configuration or None if not configured
    """
    if not CALENDAR_CONFIG_PATH.exists():
        return None

    with open(CALENDAR_CONFIG_PATH, "r") as f:
        return yaml.safe_load(f)


def save_calendar_config(config):
    """Save the calendar configuration.

    Args:
        config: Configuration dictionary to save
    """
    ensure_config_dir()
    with open(CALENDAR_CONFIG_PATH, "w") as f:
        yaml.dump(config, f, default_flow_style=False)


def get_credentials(scopes: List[str], token_file: str = "token.pickle"):
    """Get or refresh credentials for the Google API.

    Args:
        scopes: List of API scopes to request
        token_file: Path to the token pickle file (default: 'token.pickle')

    Returns:
        The credentials object
    """
    # Check if we should use remote/device auth
    auth_method = os.environ.get("HEARE_GOOGLE_AUTH_METHOD", "auto")

    if auth_method in ["device", "auto"]:
        # Use the automatic method which will choose the appropriate flow
        return google_remote_auth.get_credentials_auto(scopes, token_file)

    # Original browser-based flow
    creds = None
    # The file token.pickle stores the user's access and refresh tokens
    token_path = CREDENTIALS_DIR / token_file

    # Create directory if it doesn't exist
    CREDENTIALS_DIR.mkdir(parents=True, exist_ok=True)

    # Try to load existing credentials
    if token_path.exists():
        with open(token_path, "rb") as token:
            creds = pickle.load(token)

    # If no valid credentials, get new ones
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            # Look for credentials.json file
            credentials_path = CREDENTIALS_DIR / "google_clientid.json"
            client_secrets_file = os.environ.get(
                "HEARE_GOOGLE_CLIENT_SECRETS", str(credentials_path)
            )

            if not os.path.exists(client_secrets_file):
                raise FileNotFoundError(
                    f"Google credentials file not found. Please download your OAuth client ID credentials "
                    f"from Google Cloud Console and save them as {client_secrets_file} or "
                    f"set HEARE_GOOGLE_CLIENT_SECRETS environment variable."
                )

            flow = InstalledAppFlow.from_client_secrets_file(
                client_secrets_file, scopes
            )
            creds = flow.run_local_server(port=0)

        # Save the credentials for the next run
        with open(token_path, "wb") as token:
            pickle.dump(creds, token)

    return creds


def list_available_calendars():
    """List all available calendars for the user.

    Returns:
        List of dictionaries containing calendar information
    """
    # Get credentials for Calendar API
    creds = get_credentials(CALENDAR_SCOPES, token_file="calendar_token.pickle")
    service = build("calendar", "v3", credentials=creds)

    # Get the calendar list
    calendar_list = service.calendarList().list().execute()

    calendars = []
    for calendar_entry in calendar_list.get("items", []):
        calendars.append(
            {
                "id": calendar_entry["id"],
                "summary": calendar_entry.get("summary", "Unnamed Calendar"),
                "description": calendar_entry.get("description", ""),
                "primary": calendar_entry.get("primary", False),
                "access_role": calendar_entry.get("accessRole", ""),
            }
        )

    return calendars


@tool
def calendar_setup(context: "AgentContext") -> str:
    """Set up Google Calendar configuration by listing and selecting which calendars to enable.

    This tool guides the user through an interactive setup process to configure which
    Google Calendars should be visible and usable through the calendar tools.

    Args:
        (No additional arguments needed)
    """
    try:
        # Check if config already exists
        existing_config = get_calendar_config()
        if existing_config:
            calendars = existing_config.get("calendars", [])
            enabled_calendars = [cal for cal in calendars if cal.get("enabled", False)]

            # Ask if user wants to reconfigure
            print(
                f"Calendar configuration already exists with {len(enabled_calendars)} enabled calendars."
            )
            print("Do you want to reconfigure? (y/n)")
            response = input("> ").strip().lower()
            if response != "y":
                return "Keeping existing calendar configuration."

        # List all available calendars
        print("Fetching available calendars from Google...")
        calendars = list_available_calendars()

        if not calendars:
            return "No calendars found in your Google account."

        # Create a formatted list of calendars for display
        calendar_list = "Available calendars:\n\n"
        for i, cal in enumerate(calendars, 1):
            primary_indicator = " (primary)" if cal.get("primary", False) else ""
            calendar_list += f"{i}. {cal['summary']}{primary_indicator}\n"
            if cal.get("description"):
                calendar_list += f"   Description: {cal['description']}\n"
            calendar_list += f"   ID: {cal['id']}\n"
            calendar_list += f"   Access Role: {cal['access_role']}\n\n"

        # Print the calendar list
        print(calendar_list)

        # Get user selection
        print(
            "Enter the numbers of calendars you want to include (comma-separated), or 'all' for all calendars:"
        )
        selection = input("> ").strip()

        selected_calendars = []

        if selection.lower() == "all":
            selected_calendars = calendars
        else:
            try:
                indices = [int(idx.strip()) - 1 for idx in selection.split(",")]
                for idx in indices:
                    if 0 <= idx < len(calendars):
                        selected_calendars.append(calendars[idx])
                    else:
                        print(
                            f"Warning: Index {idx+1} is out of range and will be ignored."
                        )
            except ValueError:
                return "Invalid selection. Please run the setup again and enter valid numbers."

        if not selected_calendars:
            return "No calendars were selected. Configuration not saved."

        # Create the configuration
        config = {
            "calendars": [
                {
                    "id": cal["id"],
                    "name": cal["summary"],
                    "enabled": True,
                    "primary": cal.get("primary", False),
                }
                for cal in selected_calendars
            ]
        }

        # Find the primary calendar if not already included
        has_primary = any(cal.get("primary", False) for cal in selected_calendars)
        if not has_primary:
            for cal in calendars:
                if cal.get("primary", False):
                    config["calendars"].append(
                        {
                            "id": cal["id"],
                            "name": cal["summary"],
                            "enabled": True,
                            "primary": True,
                        }
                    )
                    break

        # Save the configuration
        save_calendar_config(config)

        return f"Calendar configuration saved. {len(config['calendars'])} calendars configured."

    except Exception as e:
        return f"Error setting up calendar configuration: {str(e)}"


def get_enabled_calendars():
    """Get a list of enabled calendars from the configuration.

    Returns:
        List of enabled calendar dictionaries, or None if not configured
    """
    config = get_calendar_config()
    if not config:
        return None

    return [cal for cal in config.get("calendars", []) if cal.get("enabled", True)]


@tool
def gmail_search(context: "AgentContext", query: str, max_results: int = 10) -> str:
    """Search for emails in Gmail using Google's search syntax.

    Args:
        query: Gmail search query (e.g., "from:example@gmail.com", "subject:meeting", "is:unread")
        max_results: Maximum number of results to return (default: 10)
    """
    try:
        # Get credentials for Gmail API
        creds = get_credentials(GMAIL_SCOPES, token_file="gmail_token.pickle")
        service = build("gmail", "v1", credentials=creds)

        # Execute the search query
        results = (
            service.users()
            .messages()
            .list(userId="me", q=query, maxResults=max_results)
            .execute()
        )
        messages = results.get("messages", [])

        if not messages:
            return "No emails found matching the query."

        # Get full message details for each result
        email_details = []
        for message in messages:
            msg = (
                service.users()
                .messages()
                .get(userId="me", id=message["id"], format="metadata")
                .execute()
            )

            # Extract headers
            headers = msg["payload"]["headers"]
            subject = next(
                (h["value"] for h in headers if h["name"].lower() == "subject"),
                "No Subject",
            )
            sender = next(
                (h["value"] for h in headers if h["name"].lower() == "from"),
                "Unknown Sender",
            )
            date = next(
                (h["value"] for h in headers if h["name"].lower() == "date"),
                "Unknown Date",
            )

            # Format the email details
            email_details.append(
                f"ID: {message['id']}\n"
                f"From: {sender}\n"
                f"Subject: {subject}\n"
                f"Date: {date}\n"
                f"Labels: {', '.join(msg.get('labelIds', []))}\n"
                f"Link: https://mail.google.com/mail/u/0/#inbox/{message['id']}\n"
            )

        # Return the formatted results
        return "Found the following emails:\n\n" + "\n---\n".join(email_details)

    except Exception as e:
        return f"Error searching Gmail: {str(e)}"


@tool
def gmail_read(context: "AgentContext", email_id: str) -> str:
    """Read the content of a specific email by its ID.

    Args:
        email_id: The ID of the email to read
    """
    try:
        # Get credentials for Gmail API
        creds = get_credentials(GMAIL_SCOPES, token_file="gmail_token.pickle")
        service = build("gmail", "v1", credentials=creds)

        # Get the full message
        message = (
            service.users()
            .messages()
            .get(userId="me", id=email_id, format="full")
            .execute()
        )

        # Extract headers
        headers = message["payload"]["headers"]
        subject = next(
            (h["value"] for h in headers if h["name"].lower() == "subject"),
            "No Subject",
        )
        sender = next(
            (h["value"] for h in headers if h["name"].lower() == "from"),
            "Unknown Sender",
        )
        date = next(
            (h["value"] for h in headers if h["name"].lower() == "date"), "Unknown Date"
        )
        to = next(
            (h["value"] for h in headers if h["name"].lower() == "to"),
            "Unknown Recipient",
        )

        # Extract message body
        body = ""
        if "parts" in message["payload"]:
            for part in message["payload"]["parts"]:
                if part["mimeType"] == "text/plain" and "data" in part["body"]:
                    import base64

                    body = base64.urlsafe_b64decode(part["body"]["data"]).decode(
                        "utf-8"
                    )
                    break
        elif "body" in message["payload"] and "data" in message["payload"]["body"]:
            import base64

            body = base64.urlsafe_b64decode(message["payload"]["body"]["data"]).decode(
                "utf-8"
            )

        # Format the email details
        email_details = (
            f"From: {sender}\n"
            f"To: {to}\n"
            f"Date: {date}\n"
            f"Subject: {subject}\n"
            f"Labels: {', '.join(message.get('labelIds', []))}\n\n"
            f"Body:\n{body}"
        )

        return email_details

    except Exception as e:
        return f"Error reading email: {str(e)}"


@tool
def gmail_send(
    context: "AgentContext",
    to: str,
    subject: str,
    body: str,
    cc: str = "",
    bcc: str = "",
) -> str:
    """Send an email via Gmail.

    Args:
        to: Email address(es) of the recipient(s), comma-separated for multiple
        subject: Subject line of the email
        body: Body text of the email
        cc: Email address(es) to CC, comma-separated for multiple (optional)
        bcc: Email address(es) to BCC, comma-separated for multiple (optional)
    """
    try:
        # Get credentials for Gmail API
        creds = get_credentials(GMAIL_SCOPES, token_file="gmail_token.pickle")
        service = build("gmail", "v1", credentials=creds)

        # Construct the email
        import base64
        from email.mime.text import MIMEText

        message = MIMEText(body)
        message["to"] = to
        message["subject"] = subject

        if cc:
            message["cc"] = cc
        if bcc:
            message["bcc"] = bcc

        # Get the sender's email address
        profile = service.users().getProfile(userId="me").execute()
        message["from"] = profile["emailAddress"]

        # Encode the message
        encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode()

        # Send the email
        send_message = (
            service.users()
            .messages()
            .send(userId="me", body={"raw": encoded_message})
            .execute()
        )

        return f"Email sent successfully. Message ID: {send_message['id']}"

    except Exception as e:
        return f"Error sending email: {str(e)}"


@tool
def calendar_list_events(
    context: "AgentContext",
    days: int = 7,
    calendar_id: str = None,
    start_date: str = None,
    end_date: str = None,
) -> str:
    """List upcoming events from Google Calendar for specific dates.

    For queries about a specific day (like "tomorrow" or "next Monday"):
    - Convert relative date references to specific YYYY-MM-DD format dates
    - Use both start_date AND end_date parameters set to the SAME date
    - Always verify events are on the requested date before including them in your response

    Example usage:
    - For "tomorrow": Use start_date="2025-04-02", end_date="2025-04-02"
    - For "next week": Use days=7 (without start_date/end_date)
    - For a date range: Use both start_date and end_date with different dates

    Args:
        days: Number of days to look ahead (default: 7)
        calendar_id: ID of the calendar to query (default: None, which uses all enabled calendars)
        start_date: Optional start date in YYYY-MM-DD format (overrides days parameter)
        end_date: Optional end date in YYYY-MM-DD format (required if start_date is provided)
    """
    try:
        # Check if calendar configuration exists
        config = get_calendar_config()
        if not config and not calendar_id:
            return (
                "No calendar configuration found. Please run calendar_setup first, "
                "or specify a calendar_id."
            )

        # Get credentials for Calendar API
        creds = get_credentials(CALENDAR_SCOPES, token_file="calendar_token.pickle")
        service = build("calendar", "v3", credentials=creds)

        # Calculate time range based on parameters
        if start_date and end_date:
            # Use the provided date range
            try:
                start_time = datetime.strptime(start_date, "%Y-%m-%d")
                end_time = datetime.strptime(end_date, "%Y-%m-%d")
                # Set end_time to the end of the day
                end_time = end_time.replace(hour=23, minute=59, second=59)
                date_range_description = f"from {start_date} to {end_date}"
            except ValueError:
                return "Invalid date format. Please use YYYY-MM-DD format for dates."
        else:
            # Use the days parameter
            now = datetime.utcnow()
            start_time = now
            end_time = now + timedelta(days=days)
            date_range_description = f"in the next {days} days"

        # Determine which calendars to query
        calendars_to_query = []
        if calendar_id:
            # Just query the specified calendar
            calendars_to_query.append({"id": calendar_id, "name": "Specified Calendar"})
        else:
            # Query all enabled calendars from config
            enabled_calendars = get_enabled_calendars()
            if not enabled_calendars:
                return "No enabled calendars found in configuration. Please run calendar_setup first."
            calendars_to_query = enabled_calendars

        # Get events from all calendars
        all_events = []

        for cal in calendars_to_query:
            events_result = (
                service.events()
                .list(
                    calendarId=cal["id"],
                    timeMin=start_time.isoformat() + "Z",
                    timeMax=end_time.isoformat() + "Z",
                    singleEvents=True,
                    orderBy="startTime",
                )
                .execute()
            )

            events = events_result.get("items", [])
            for event in events:
                event["calendar_name"] = cal.get("name", "Unknown Calendar")
                all_events.append(event)

        # Sort all events by start time
        all_events.sort(
            key=lambda x: x["start"].get("dateTime", x["start"].get("date"))
        )

        if not all_events:
            return f"No events found {date_range_description}."

        # Format events
        formatted_events = []
        for event in all_events:
            start = event["start"].get("dateTime", event["start"].get("date"))
            end = event["end"].get("dateTime", event["end"].get("date"))

            # Extract event date for comparison and filtering
            event_date = start.split("T")[0] if "T" in start else start

            # Format date/time
            if "T" in start:  # This is a datetime, not just a date
                start_dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
                end_dt = datetime.fromisoformat(end.replace("Z", "+00:00"))
                time_str = f"{start_dt.strftime('%Y-%m-%d %H:%M')} to {end_dt.strftime('%H:%M')}"
            else:
                time_str = f"{event_date} (all day)"

            # Get attendees if any
            attendees = []
            if "attendees" in event:
                attendees = [
                    attendee.get("email", "Unknown") for attendee in event["attendees"]
                ]

            # Format event
            event_text = (
                f"Event: {event.get('summary', 'Untitled Event')}\n"
                f"Calendar: {event['calendar_name']}\n"
                f"Time: {time_str}\n"
                f"Creator: {event['creator'].get('displayName', 'Unknown')}\n"
            )

            # Add location if present
            if "location" in event:
                event_text += f"Location: {event['location']}\n"

            # Add description if present
            if "description" in event and event["description"].strip():
                # Truncate long descriptions
                description = event["description"]
                if len(description) > 200:
                    description = description[:197] + "..."
                event_text += f"Description: {description}\n"

            # Add attendees if present
            if attendees:
                event_text += f"Attendees: {', '.join(attendees)}\n"

            # Add event ID
            event_text += f"ID: {event['id']}\n"

            formatted_events.append(event_text)

        return f"Upcoming events {date_range_description}:\n\n" + "\n---\n".join(
            formatted_events
        )

    except Exception as e:
        return f"Error listing calendar events: {str(e)}"


@tool
def calendar_create_event(
    context: "AgentContext",
    summary: str,
    start_time: str,
    end_time: str,
    description: str = "",
    location: str = "",
    attendees: str = "",
    calendar_id: str = None,
) -> str:
    """Create a new event in Google Calendar.

    Args:
        summary: Title/summary of the event
        start_time: Start time in ISO format (YYYY-MM-DDTHH:MM:SS) or date (YYYY-MM-DD) for all-day events
        end_time: End time in ISO format (YYYY-MM-DDTHH:MM:SS) or date (YYYY-MM-DD) for all-day events
        description: Description of the event (optional)
        location: Location of the event (optional)
        attendees: Comma-separated list of email addresses to invite (optional)
        calendar_id: ID of the calendar to add the event to (default: None, which uses primary calendar)
    """
    try:
        # If no calendar_id is specified, use the primary calendar from config or 'primary'
        if not calendar_id:
            config = get_calendar_config()
            if config:
                calendars = config.get("calendars", [])
                primary_calendars = [
                    cal
                    for cal in calendars
                    if cal.get("primary", False) and cal.get("enabled", True)
                ]
                if primary_calendars:
                    calendar_id = primary_calendars[0]["id"]
                else:
                    calendar_id = "primary"
            else:
                calendar_id = "primary"

        # Get credentials for Calendar API
        creds = get_credentials(CALENDAR_SCOPES, token_file="calendar_token.pickle")
        service = build("calendar", "v3", credentials=creds)

        # Determine if this is an all-day event
        is_all_day = "T" not in start_time

        # Create the event object
        event = {
            "summary": summary,
            "description": description,
            "location": location,
        }

        # Set start and end times
        if is_all_day:
            # All-day events don't need timezone info, just use the date
            event["start"] = {
                "date": start_time.split("T")[0] if "T" in start_time else start_time
            }
            event["end"] = {
                "date": end_time.split("T")[0] if "T" in end_time else end_time
            }
        else:
            # Get user's calendar timezone
            try:
                # Get the calendar's timezone from API
                calendar_info = (
                    service.calendars().get(calendarId=calendar_id).execute()
                )
                user_timezone = calendar_info.get("timeZone", "UTC")
            except Exception as e:
                # Log the error and fallback to UTC
                print(f"Error getting calendar timezone: {str(e)}")
                user_timezone = "UTC"

            # Check if timezone is already specified in the datetime strings
            # Safely check for timezone markers (Z, +, or - after time part)
            def has_timezone(dt_str):
                if dt_str.endswith("Z"):
                    return True

                # Check for proper ISO format with time part
                time_part_pos = dt_str.find("T")
                if time_part_pos == -1:
                    return False  # Not a datetime string with time

                # Standard format should be YYYY-MM-DDThh:mm:ss[.sss](+/-hh:mm or Z)
                # Look for +/- but make sure it's not the date separator
                # Also confirm we have proper time format with colons
                time_part = dt_str[time_part_pos + 1 :]
                if ":" not in time_part:
                    return False  # Not a properly formatted time

                # Look for timezone markers after the seconds
                for pos in range(
                    time_part_pos + 8, len(dt_str)
                ):  # At least hh:mm:ss after T
                    if dt_str[pos] in ("+", "-"):
                        return True

                return False

            has_timezone_start = has_timezone(start_time)
            has_timezone_end = has_timezone(end_time)

            # Handle start time
            if has_timezone_start:
                # User specified timezone, respect it
                event["start"] = {"dateTime": start_time}
            else:
                # No timezone in string, use calendar's timezone
                event["start"] = {"dateTime": start_time, "timeZone": user_timezone}

            # Handle end time
            if has_timezone_end:
                # User specified timezone, respect it
                event["end"] = {"dateTime": end_time}
            else:
                # No timezone in string, use calendar's timezone
                event["end"] = {"dateTime": end_time, "timeZone": user_timezone}

        # Add attendees if specified
        if attendees:
            attendee_list = [{"email": email.strip()} for email in attendees.split(",")]
            event["attendees"] = attendee_list

        # Create the event
        event = service.events().insert(calendarId=calendar_id, body=event).execute()

        # Try to get calendar name
        try:
            calendar_info = service.calendars().get(calendarId=calendar_id).execute()
            calendar_name = calendar_info.get("summary", calendar_id)
        except:  # noqa: E722
            calendar_name = calendar_id

        return (
            f"Event created successfully in calendar '{calendar_name}'.\n"
            f"Event ID: {event['id']}\n"
            f"Title: {summary}\n"
            f"Time: {start_time} to {end_time}"
        )

    except Exception as e:
        return f"Error creating calendar event: {str(e)}"


@tool
def calendar_delete_event(
    context: "AgentContext", event_id: str, calendar_id: str = None
) -> str:
    """Delete an event from Google Calendar.

    Args:
        event_id: ID of the event to delete
        calendar_id: ID of the calendar containing the event (default: None, requiring confirmation)
    """
    try:
        # Get credentials for Calendar API
        creds = get_credentials(CALENDAR_SCOPES, token_file="calendar_token.pickle")
        service = build("calendar", "v3", credentials=creds)

        # If no calendar_id provided, search in all enabled calendars
        if not calendar_id:
            enabled_calendars = get_enabled_calendars()
            if not enabled_calendars:
                return (
                    "No calendar configuration found. Please provide the calendar_id."
                )

            # First try to find the event to get its details before deletion
            event_found = False
            event_summary = "Unknown Event"

            for cal in enabled_calendars:
                try:
                    event = (
                        service.events()
                        .get(calendarId=cal["id"], eventId=event_id)
                        .execute()
                    )
                    calendar_id = cal["id"]
                    event_found = True
                    event_summary = event.get("summary", "Unknown Event")
                    break
                except:  # noqa: E722
                    continue

            if not event_found:
                return (
                    f"Event {event_id} not found in any of your configured calendars."
                )

            # Confirm deletion
            print(
                f"Found event '{event_summary}' in calendar '{cal.get('name', calendar_id)}'"
            )
            print("Are you sure you want to delete this event? (y/n)")
            response = input("> ").strip().lower()
            if response != "y":
                return "Event deletion cancelled."

        # Delete the event
        service.events().delete(calendarId=calendar_id, eventId=event_id).execute()

        return f"Event {event_id} deleted successfully."

    except Exception as e:
        return f"Error deleting calendar event: {str(e)}"


@tool
def calendar_search(
    context: "AgentContext", query: str, days: int = 90, calendar_id: str = None
) -> str:
    """Search for events in Google Calendar by keyword.

    This tool allows you to search for calendar events containing specific keywords
    in their title, description, or location.

    Args:
        query: The search term to look for in events
        days: Number of days to look ahead (default: 90)
        calendar_id: ID of the calendar to search (default: None, which searches all enabled calendars)
    """
    try:
        # Check if calendar configuration exists
        config = get_calendar_config()
        if not config and not calendar_id:
            return (
                "No calendar configuration found. Please run calendar_setup first, "
                "or specify a calendar_id."
            )

        # Get credentials for Calendar API
        creds = get_credentials(CALENDAR_SCOPES, token_file="calendar_token.pickle")
        service = build("calendar", "v3", credentials=creds)

        # Calculate time range
        now = datetime.utcnow()
        start_time = now - timedelta(days=days)
        end_time = now + timedelta(days=days)

        # Determine which calendars to query
        calendars_to_query = []
        if calendar_id:
            # Just query the specified calendar
            calendars_to_query.append({"id": calendar_id, "name": "Specified Calendar"})
        else:
            # Query all enabled calendars from config
            enabled_calendars = get_enabled_calendars()
            if not enabled_calendars:
                return "No enabled calendars found in configuration. Please run calendar_setup first."
            calendars_to_query = enabled_calendars

        # Get events from all calendars
        all_events = []

        for cal in calendars_to_query:
            events_result = (
                service.events()
                .list(
                    calendarId=cal["id"],
                    timeMin=start_time.isoformat() + "Z",
                    timeMax=end_time.isoformat() + "Z",
                    singleEvents=True,
                    orderBy="startTime",
                    # We can't use q parameter here because it would only search the summary
                    # Instead, we'll filter results after receiving them
                )
                .execute()
            )

            events = events_result.get("items", [])
            for event in events:
                event["calendar_name"] = cal.get("name", "Unknown Calendar")
                all_events.append(event)

        # Filter events that match the query
        query = query.lower()
        matching_events = []

        for event in all_events:
            # Check if query appears in summary (title)
            if query in (event.get("summary", "")).lower():
                matching_events.append(event)
                continue

            # Check if query appears in description
            if query in (event.get("description", "")).lower():
                matching_events.append(event)
                continue

            # Check if query appears in location
            if query in (event.get("location", "")).lower():
                matching_events.append(event)
                continue

            # Check if query appears in attendee emails or names
            if "attendees" in event:
                for attendee in event["attendees"]:
                    if (
                        query in attendee.get("email", "").lower()
                        or query in attendee.get("displayName", "").lower()
                    ):
                        matching_events.append(event)
                        break

        # Sort matching events by start time
        matching_events.sort(
            key=lambda x: x["start"].get("dateTime", x["start"].get("date"))
        )

        if not matching_events:
            return f"No events found matching '{query}' in the next {days} days."

        # Format events
        formatted_events = []
        for event in matching_events:
            start = event["start"].get("dateTime", event["start"].get("date"))
            end = event["end"].get("dateTime", event["end"].get("date"))

            # Format date/time
            if "T" in start:  # This is a datetime, not just a date
                start_dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
                end_dt = datetime.fromisoformat(end.replace("Z", "+00:00"))
                time_str = f"{start_dt.strftime('%Y-%m-%d %H:%M')} to {end_dt.strftime('%H:%M')}"
            else:
                time_str = f"{start} (all day)"

            # Get attendees if any
            attendees = []
            if "attendees" in event:
                attendees = [
                    attendee.get("email", "Unknown") for attendee in event["attendees"]
                ]

            # Format event
            event_text = (
                f"Event: {event.get('summary', 'Untitled Event')}\n"
                f"Calendar: {event['calendar_name']}\n"
                f"Time: {time_str}\n"
                f"Creator: {event['creator'].get('displayName', 'Unknown')}\n"
            )

            # Add location if present
            if "location" in event:
                event_text += f"Location: {event['location']}\n"

            # Add description if present
            if "description" in event and event["description"].strip():
                # Truncate long descriptions
                description = event["description"]
                if len(description) > 200:
                    description = description[:197] + "..."
                event_text += f"Description: {description}\n"

            # Add attendees if present
            if attendees:
                event_text += f"Attendees: {', '.join(attendees)}\n"

            # Add event ID
            event_text += f"ID: {event['id']}\n"

            formatted_events.append(event_text)

        return (
            f"Found {len(matching_events)} events matching '{query}' in the next {days} days:\n\n"
            + "\n---\n".join(formatted_events)
        )

    except Exception as e:
        return f"Error searching calendar events: {str(e)}"


@tool
def calendar_list_calendars(context: "AgentContext") -> str:
    """List available Google Calendars and their configuration status.

    This tool lists all calendars available to the user and indicates which ones
    are currently enabled in the configuration.

    Args:
        (No additional arguments needed)
    """
    try:
        # Get all available calendars from Google
        calendars = list_available_calendars()

        if not calendars:
            return "No calendars found in your Google account."

        # Get configured calendars
        config = get_calendar_config()
        enabled_calendar_ids = []

        if config:
            enabled_calendar_ids = [
                cal["id"]
                for cal in config.get("calendars", [])
                if cal.get("enabled", True)
            ]

        # Format the calendar list
        calendar_list = "Your Google Calendars:\n\n"

        for i, cal in enumerate(calendars, 1):
            is_enabled = cal["id"] in enabled_calendar_ids
            primary_indicator = " (primary)" if cal.get("primary", False) else ""
            enabled_indicator = " [ENABLED]" if is_enabled else " [NOT ENABLED]"

            calendar_list += (
                f"{i}. {cal['summary']}{primary_indicator}{enabled_indicator}\n"
            )
            if cal.get("description"):
                calendar_list += f"   Description: {cal['description']}\n"
            calendar_list += f"   ID: {cal['id']}\n"
            calendar_list += f"   Access Role: {cal['access_role']}\n\n"

        if not config:
            calendar_list += "\nNo calendar configuration found. Run calendar_setup to configure your calendars."

        return calendar_list

    except Exception as e:
        return f"Error listing calendars: {str(e)}"
