# Task: Create Conversation Class

## Description
Create a new `Conversation` class that maintains an internal representation of the conversation, including file read operations, structured edits, and chat messages. This class will work closely with file editing tools to ensure consistency between recorded operations and actual file states.

## Implementation Details
1. Create a new file `conversation.py` in the `heare/developer` directory.
2. Implement the `Conversation` class with the following features:
   - Track read files
   - Store a list of structured edits
   - Store chat history (messages)
   - Method to add a file read operation
   - Method to add a file edit operation (to be called by file editing tools)
   - Method to read current file content from disk
   - Method to add a chat message
   - Method to get the chat history
   - Method to render the conversation for LLM, including diffs for edit operations

## Integration with File Editing Tools
- File editing tools should be tightly coupled with the Conversation class
- File editing tools should call Conversation methods to record successful edits
- Consider implementing a verification method to ensure consistency between recorded edits and actual file states

## Tests
1. Test file creation and initialization of the `Conversation` class
2. Test adding a file read operation
3. Test adding a file edit operation
4. Test reading current file content from disk
5. Test multiple edits to the same file
6. Test adding a chat message
7. Test retrieving the chat history
8. Test rendering the conversation for LLM, including diffs
9. Test the complete workflow: adding messages, file reads, and edits, then rendering the conversation