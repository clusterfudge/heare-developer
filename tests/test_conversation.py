import unittest
from heare.developer.conversation import Conversation


class TestConversation(unittest.TestCase):
    def setUp(self):
        self.conversation = Conversation()

    def test_initialization(self):
        self.assertEqual(self.conversation.files, {})
        self.assertEqual(self.conversation.edits, [])
        self.assertEqual(self.conversation.messages, [])

    def test_add_file_read(self):
        self.conversation.add_file_read("test.txt", "Hello, world!")
        self.assertEqual(
            self.conversation.get_latest_file_state("test.txt"), "Hello, world!"
        )

    def test_add_file_edit_replace(self):
        self.conversation.add_file_read("test.txt", "Hello, world!")
        self.conversation.add_file_edit(
            "test.txt", {"operation": "replace", "old": "world", "new": "universe"}
        )
        self.assertEqual(
            self.conversation.get_latest_file_state("test.txt"), "Hello, universe!"
        )

    def test_add_file_edit_insert(self):
        self.conversation.add_file_read("test.txt", "Hello, world!")
        self.conversation.add_file_edit(
            "test.txt", {"operation": "insert", "position": 7, "text": "beautiful "}
        )
        self.assertEqual(
            self.conversation.get_latest_file_state("test.txt"),
            "Hello, beautiful world!",
        )

    def test_add_file_edit_delete(self):
        self.conversation.add_file_read("test.txt", "Hello, beautiful world!")
        self.conversation.add_file_edit(
            "test.txt", {"operation": "delete", "start": 7, "end": 16}
        )
        self.assertEqual(
            self.conversation.get_latest_file_state("test.txt"), "Hello, world!"
        )

    def test_multiple_edits(self):
        self.conversation.add_file_read("test.txt", "Hello, world!")
        self.conversation.add_file_edit(
            "test.txt", {"operation": "replace", "old": "world", "new": "universe"}
        )
        self.conversation.add_file_edit(
            "test.txt", {"operation": "replace", "old": "Hello", "new": "Greetings"}
        )
        self.assertEqual(
            self.conversation.get_latest_file_state("test.txt"), "Greetings, universe!"
        )

    def test_add_message(self):
        self.conversation.add_message("user", "Hello, AI!")
        self.assertEqual(len(self.conversation.messages), 1)
        self.assertEqual(
            self.conversation.messages[0], {"role": "user", "content": "Hello, AI!"}
        )

    def test_get_chat_history(self):
        self.conversation.add_message("user", "Hello, AI!")
        self.conversation.add_message("assistant", "Hello! How can I help you today?")
        chat_history = self.conversation.get_chat_history()
        self.assertEqual(len(chat_history), 2)
        self.assertEqual(chat_history[0], {"role": "user", "content": "Hello, AI!"})
        self.assertEqual(
            chat_history[1],
            {"role": "assistant", "content": "Hello! How can I help you today?"},
        )

    def test_complete_workflow(self):
        # Add messages
        self.conversation.add_message("user", "Can you read and edit a file for me?")
        self.conversation.add_message(
            "assistant", "Certainly! What file would you like me to work with?"
        )

        # Add file read
        self.conversation.add_file_read("example.txt", "This is an example file.")
        self.conversation.add_message(
            "assistant",
            "I've read the file 'example.txt'. Its content is: 'This is an example file.'",
        )

        # Add file edit
        self.conversation.add_file_edit(
            "example.txt",
            {"operation": "replace", "old": "an example", "new": "a sample"},
        )
        self.assertEqual(
            self.conversation.get_latest_file_state("example.txt"),
            "This is a sample file.",
        )

        # Verify chat history
        chat_history = self.conversation.get_chat_history()
        self.assertEqual(len(chat_history), 3)

    def test_invalid_edit_operation(self):
        self.conversation.add_file_read("test.txt", "Hello, world!")
        with self.assertRaises(ValueError):
            self.conversation.add_file_edit(
                "test.txt", {"operation": "invalid_operation"}
            )


if __name__ == "__main__":
    unittest.main()
