from typing import List, Dict, Tuple, Any


class Conversation:
    def __init__(self):
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
                if file_path not in included_files:
                    rendered_messages.append(
                        {
                            "role": "assistant",
                            "content": f"I've read the contents of the file: {file_path}. You can reference this file using the pointer '{file_path}'.",
                        }
                    )
                    included_files.add(file_path)
            elif message["role"] == "file_edit":
                file_path, edit_operation = message["content"]
                diff = self._generate_diff(file_path, edit_operation)
                rendered_messages.append(
                    {
                        "role": "assistant",
                        "content": f"I've made the following edit to the file {file_path}:\n{diff}",
                    }
                )
            elif message["role"] in ["user", "assistant"]:
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

        try:
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
                end = edit_operation.get("end", 0)
                file_content = self._read_file_content(file_path)
                deleted_text = file_content[start:end]
                return f"- {deleted_text} (deleted from position {start} to {end})"
            else:
                return f"Unsupported edit operation: {operation_type}"
        except Exception as e:
            return f"Error generating diff: {str(e)}"

    def add_file_read(self, file_path: str) -> None:
        """
        Add a file read operation to the conversation.

        Args:
            file_path (str): The path of the file that was read.
        """
        self.messages.append({"role": "file_read", "content": file_path})
        if file_path not in self.file_read_order:
            self.file_read_order.append(file_path)

    def add_file_edit(self, file_path: str, edit_operation: Any) -> None:
        """
        Add a file edit operation to the conversation.

        Args:
            file_path (str): The path of the file that was edited.
            edit_operation (Any): The edit operation to apply to the file.
        """
        self.edits.append((file_path, edit_operation))
        self.messages.append(
            {"role": "file_edit", "content": (file_path, edit_operation)}
        )

    def _read_file_content(self, file_path: str) -> str:
        """
        Read the current content of a file from disk.

        Args:
            file_path (str): The path of the file to read.

        Returns:
            str: The content of the file, or an empty string if the file doesn't exist.
        """
        try:
            with open(file_path, "r") as file:
                return file.read()
        except FileNotFoundError:
            return ""

    def add_message(self, role: str, content: str) -> None:
        """
        Add a chat message to the conversation history.

        Args:
            role (str): The role of the message sender (e.g., 'user', 'assistant').
            content (str): The content of the message.
        """
        if role not in ["user", "assistant"]:
            raise ValueError("Invalid role. Must be 'user' or 'assistant'.")
        self.messages.append({"role": role, "content": content})

    def get_chat_history(self) -> List[Dict[str, str]]:
        """
        Get the full chat history.

        Returns:
            List[Dict[str, str]]: A list of all chat messages.
        """
        return self.messages

    def verify_edits(self) -> List[str]:
        """
        Verify that recorded edits match the current state of files on disk.

        Returns:
            List[str]: A list of inconsistencies found, if any.
        """
        inconsistencies = []
        for file_path, edit_operation in self.edits:
            try:
                current_content = self._read_file_content(file_path)
                operation_type = edit_operation.get("operation")

                if operation_type == "replace":
                    old_text = edit_operation.get("old", "")
                    new_text = edit_operation.get("new", "")
                    if old_text in current_content:
                        inconsistencies.append(
                            f"File {file_path}: Expected replacement not found"
                        )
                    elif new_text not in current_content:
                        inconsistencies.append(
                            f"File {file_path}: Replacement text not found"
                        )
                elif operation_type == "insert":
                    new_text = edit_operation.get("text", "")
                    if new_text not in current_content:
                        inconsistencies.append(
                            f"File {file_path}: Inserted text not found"
                        )
                elif operation_type == "delete":
                    start = edit_operation.get("start", 0)
                    end = edit_operation.get("end", 0)
                    deleted_text = current_content[start:end]
                    if deleted_text:
                        inconsistencies.append(
                            f"File {file_path}: Deleted text still present"
                        )
            except Exception as e:
                inconsistencies.append(
                    f"Error verifying edits for {file_path}: {str(e)}"
                )

        return inconsistencies
