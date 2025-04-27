# Conversation Compaction Feature (HDEV-34)

## Overview

This PR implements the conversation compaction feature requested in issue HDEV-34. It addresses the problem of conversations becoming too long by automatically summarizing them and starting a new conversation when they exceed a token threshold.

## Implementation Details

1. Created a new `ConversationCompacter` class in `compacter.py` that:
   - Counts tokens using Anthropic's `/v1/count_tokens` API
   - Generates conversation summaries
   - Creates new compacted conversations
   
2. Integrated compaction with the context flushing mechanism in `context.py`
3. Added CLI options to enable/disable compaction in `hdev.py`
4. Added comprehensive documentation in `docs/conversation_compaction.md`
5. Created unit tests in `tests/test_compaction.py`

## How to Use

By default, conversation compaction is enabled and will trigger automatically when a conversation exceeds the token threshold. To disable it, use:

```
hdev --disable-compaction
```

## Benefits

- Reduces token usage while preserving important context
- Lowers API costs for long conversations
- Keeps conversations focused on current topics
- Prevents hitting context window limits