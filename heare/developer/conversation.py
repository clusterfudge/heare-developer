from typing import List, Dict, Tuple, Any


class Conversation:
    def __init__(self):
        self.files: Dict[str, str] = {}  # Dictionary to store file states
        self.edits: List[Tuple[str, Any]] = []  # List to store structured edits
        self.messages: List[Dict[str, str]] = []  # List to store chat messages

    def add_file_read(self, file_path: str, content: str) -> None:
        """
        Add a file read operation to the conversation.

        Args:
            file_path (str): The path of the file that was read.
            content (str): The content of the file.
        """
        self.files[file_path] = content

    def add_file_edit(self, file_path: str, edit_operation: Any) -> None:
        """
        Add a file edit operation to the conversation and update the file state.

        Args:
            file_path (str): The path of the file that was edited.
            edit_operation (Any): The edit operation to apply to the file.
        """
        self.edits.append((file_path, edit_operation))
        # Update the file content based on the edit operation
        self.files[file_path] = self._apply_edit(self.files[file_path], edit_operation)

    def get_latest_file_state(self, file_path: str) -> str:
        """
        Get the latest state of a file.

        Args:
            file_path (str): The path of the file.

        Returns:
            str: The latest content of the file, or None if the file doesn't exist.
        """
        return self.files.get(file_path, None)

    def add_message(self, role: str, content: str) -> None:
        """
        Add a chat message to the conversation history.

        Args:
            role (str): The role of the message sender (e.g., 'user', 'assistant').
            content (str): The content of the message.
        """
        self.messages.append({"role": role, "content": content})

    def get_chat_history(self) -> List[Dict[str, str]]:
        """
        Get the full chat history.

        Returns:
            List[Dict[str, str]]: A list of all chat messages.
        """
        return self.messages

    def _apply_edit(self, content: str, edit_operation: Dict[str, Any]) -> str:
        """
        Apply an edit operation to the content of a file.

        Args:
            content (str): The current content of the file.
            edit_operation (Dict[str, Any]): The edit operation to apply.

        Returns:
            str: The updated content after applying the edit operation.
        """
        operation_type = edit_operation.get("operation")

        if operation_type == "replace":
            old_text = edit_operation.get("old", "")
            new_text = edit_operation.get("new", "")
            return content.replace(old_text, new_text)

        elif operation_type == "insert":
            position = edit_operation.get("position", 0)
            new_text = edit_operation.get("text", "")
            return content[:position] + new_text + content[position:]

        elif operation_type == "delete":
            start = edit_operation.get("start", 0)
            end = edit_operation.get("end", len(content))
            return content[:start].rstrip() + " " + content[end:].lstrip()

        else:
            raise ValueError(f"Unsupported edit operation: {operation_type}")
