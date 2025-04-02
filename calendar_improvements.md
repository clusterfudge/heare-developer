# Calendar Tool Improvements

## Problem Identified

When using the `calendar_list_events` tool to fetch events for a specific date (like "what's on my calendar for tomorrow?"), the current implementation has the following issues:

1. Events are displayed with timestamps that include the date, but this information is not prominently displayed or easily parsed by the LLM.
2. Events from different days may be mixed in the results, making it confusing which events are actually on the requested day.
3. The LLM sometimes misinterprets the dates when presenting the results.

## Recommended Changes

1. Add a distinct `Date: YYYY-MM-DD` field to each event display to make the date more explicit.
2. Organize events by date before displaying them.
3. Improve date filtering to strictly match the date range requested.

## Code Changes

In the `calendar_list_events` function, we need to make the following changes:

1. Add code to extract the event date for explicit display:
```python
# Extract event date for explicit display
event_date = start.split("T")[0] if "T" in start else start
            
# Format event
event_text = (
    f"Event: {event.get('summary', 'Untitled Event')}\n"
    f"Calendar: {event['calendar_name']}\n"
    f"Date: {event_date}\n"
    f"Time: {time_str}\n"
    f"Creator: {event['creator'].get('displayName', 'Unknown')}\n"
)
```

2. For clarity in the results, group events by date before displaying them:
```python
# Group events by date
events_by_date = {}
for event in all_events:
    start = event["start"].get("dateTime", event["start"].get("date"))
    event_date = start.split("T")[0] if "T" in start else start
    
    if event_date not in events_by_date:
        events_by_date[event_date] = []
    
    events_by_date[event_date].append(event)

# Create formatted output
formatted_output = []
for date in sorted(events_by_date.keys()):
    formatted_output.append(f"Events for {date}:")
    date_events = []
    
    for event in events_by_date[date]:
        # Format each event as before
        # ...
        date_events.append(event_text)
    
    formatted_output.append("\n---\n".join(date_events))

return f"Upcoming events {date_range_description}:\n\n" + "\n\n".join(formatted_output)
```

## LLM Prompt Improvement

When someone asks about events for a specific date like "tomorrow" or "on Wednesday", the LLM should:

1. Convert relative terms to explicit dates (e.g., "tomorrow" -> "2025-04-02")
2. Set both start_date and end_date to the same date to get only events for that specific day
3. When presenting results, clearly state which date the events are for (e.g., "Here are your events for tomorrow, April 2, 2025:")
4. Carefully check each event's date field to ensure it matches the requested date before including it in the summary