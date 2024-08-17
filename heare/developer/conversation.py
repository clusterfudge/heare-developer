from typing import List, Dict, Tuple, Any


class Conversation:
    def __init__(self):
        self.files: Dict[str, str] = {}  # Dictionary to store file states
        self.edits: List[Tuple[str, Any]] = []  # List to store structured edits
        self.messages: List[Dict[str, str]] = []  # List to store chat messages
        self.file_read_order: List[str] = []  # List to store the order of file reads

    def render_for_llm(self) -> List[Dict[str, str]]:
        """
        Render the conversation for the LLM, including only the latest version of files
        and diffs for edit operations.

        Returns:
            List[Dict[str, str]]: A list of messages suitable for sending to the LLM.
        """
        rendered_messages = []
        included_files = set()
        for message in self.messages:
            if message["role"] == "file_read":
                file_path = message["content"]
                if file_path in self.files and file_path not in included_files:
                    rendered_messages.append(
                        {
                            "role": "file_content",
                            "content": f"File: {file_path}\nContent:\n{self.files[file_path]}",
                        }
                    )
                    included_files.add(file_path)
            elif message["role"] == "file_edit":
                file_path, edit_operation = message["content"]
                diff = self._generate_diff(file_path, edit_operation)
                rendered_messages.append(
                    {
                        "role": "file_edit",
                        "content": f"Edit to file: {file_path}\nDiff:\n{diff}",
                    }
                )
            else:
                rendered_messages.append(message)
        return rendered_messages

    def _generate_diff(self, file_path: str, edit_operation: Dict[str, Any]) -> str:
        """
        Generate a human-readable diff for a file edit operation.

        Args:
            file_path (str): The path of the file that was edited.
            edit_operation (Dict[str, Any]): The edit operation applied to the file.

        Returns:
            str: A human-readable diff of the changes.
        """
        operation_type = edit_operation.get("operation")
        old_content = self.files.get(file_path, "")
        self._apply_edit(old_content, edit_operation)

        if operation_type == "replace":
            old_text = edit_operation.get("old", "")
            new_text = edit_operation.get("new", "")
            return f"- {old_text}\n+ {new_text}"
        elif operation_type == "insert":
            position = edit_operation.get("position", 0)
            new_text = edit_operation.get("text", "")
            return f"+ {new_text} (inserted at position {position})"
        elif operation_type == "delete":
            start = edit_operation.get("start", 0)
            end = edit_operation.get("end", len(old_content))
            deleted_text = old_content[start:end]
            return f"- {deleted_text} (deleted from position {start} to {end})"
        else:
            return f"Unsupported edit operation: {operation_type}"

    def add_file_read(self, file_path: str, content: str) -> None:
        """
        Add a file read operation to the conversation.

        Args:
            file_path (str): The path of the file that was read.
            content (str): The content of the file.
        """
        self.files[file_path] = content
        self.messages.append({"role": "file_read", "content": file_path})
        if file_path not in self.file_read_order:
            self.file_read_order.append(file_path)

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
        self.messages.append(
            {"role": "file_edit", "content": (file_path, edit_operation)}
        )

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
