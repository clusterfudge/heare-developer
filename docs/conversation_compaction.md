# Conversation Compaction

## Overview

The conversation compaction feature addresses the issue of conversations becoming too long over time, which can:
1. Exceed token context limits
2. Increase latency and API costs
3. Make it difficult to maintain focus on current topics

When a conversation becomes too long, the compactor automatically creates a summary of the conversation and starts a new conversation from that summary, preserving important context while reducing token usage.

## How It Works

### Process Flow

1. **Token Counting**: Each conversation's tokens are counted using Anthropic's `/v1/count_tokens` API
2. **Threshold Check**: When the token count exceeds the configured threshold (default: 100,000 tokens)
3. **Summary Generation**: The conversation is sent to Claude to create a comprehensive summary
4. **New Conversation**: A new conversation is started with the summary as the initial context
5. **Metadata Preservation**: Relationship between original and compacted conversations is recorded

### Compaction Summary

The summary is designed to preserve key information:
- Important decisions and conclusions
- Current state of development/discussion
- Pending questions or tasks
- Recent context relevant to future messages

## Configuration

### CLI Options

```
--disable-compaction    Disable automatic conversation compaction
```

### Token Threshold

The default token threshold is 100,000 tokens. To customize this, you can:

1. Modify the `DEFAULT_TOKEN_THRESHOLD` constant in `compacter.py`
2. Or create a configuration file at `~/.config/hdev/config.json` with:
   ```json
   {
     "compaction": {
       "token_threshold": 50000
     }
   }
   ```

## Technical Implementation

### Key Components

1. **ConversationCompacter** (`compacter.py`):
   - Handles token counting and threshold checks
   - Generates conversation summaries
   - Creates new compacted conversations

2. **AgentContext** (`context.py`):
   - Integrates compaction into the conversation flushing process
   - Stores and manages compaction metadata

### Metadata

When a conversation is compacted, metadata is stored including:
- Original session ID
- Original message and token counts
- Summary token count
- Compaction ratio
- Timestamp

### Benefits

- **Efficiency**: Reduces token usage while preserving important context
- **Cost Savings**: Fewer tokens means lower API costs
- **Improved Focus**: Keeps conversations focused on current topics
- **Context Window Management**: Prevents hitting context window limits

## Related Features

- **History Viewing**: The `history.py` module shows compaction relationships
- **Context Flushing**: Works with the existing context flush mechanism
- **Memory Management**: Complements the memory system for long-term knowledge persistence

## Future Improvements

- Auto-adjust compaction threshold based on model context window
- Prioritize which parts of conversations to retain in summaries
- Track topics across compacted conversations
- Implement progressive compaction for very long-running sessions