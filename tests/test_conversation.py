import unittest
from unittest.mock import patch, mock_open
from heare.developer.conversation import Conversation


class TestConversation(unittest.TestCase):
    def setUp(self):
        self.conversation = Conversation()

    def test_initialization(self):
        self.assertEqual(self.conversation.edits, [])
        self.assertEqual(self.conversation.messages, [])
        self.assertEqual(self.conversation.file_read_order, [])

    def test_add_file_read(self):
        file_path = "test.py"
        self.conversation.add_file_read(file_path)

        self.assertEqual(
            self.conversation.messages[-1], {"role": "file_read", "content": file_path}
        )
        self.assertEqual(self.conversation.file_read_order, [file_path])

    def test_add_file_edit(self):
        file_path = "test.py"
        edit_operation = {
            "operation": "replace",
            "old": "Hello, World!",
            "new": "Hello, Python!",
        }
        self.conversation.add_file_edit(file_path, edit_operation)

        self.assertEqual(self.conversation.edits[-1], (file_path, edit_operation))
        self.assertEqual(self.conversation.messages[-1]["role"], "file_edit")

    def test_read_file_content(self):
        file_path = "test.py"
        file_content = "print('Hello, World!')"

        with patch("builtins.open", mock_open(read_data=file_content)):
            content = self.conversation._read_file_content(file_path)

        self.assertEqual(content, file_content)

    def test_read_nonexistent_file(self):
        file_path = "nonexistent.py"
        content = self.conversation._read_file_content(file_path)
        self.assertEqual(content, "")

    def test_add_message(self):
        self.conversation.add_message("user", "What's the weather like?")
        self.conversation.add_message(
            "assistant",
            "I'm sorry, I don't have access to real-time weather information.",
        )

        self.assertEqual(len(self.conversation.messages), 2)
        self.assertEqual(
            self.conversation.messages[0],
            {"role": "user", "content": "What's the weather like?"},
        )
        self.assertEqual(
            self.conversation.messages[1],
            {
                "role": "assistant",
                "content": "I'm sorry, I don't have access to real-time weather information.",
            },
        )

    def test_get_chat_history(self):
        self.conversation.add_message("user", "Hello")
        self.conversation.add_message("assistant", "Hi there!")

        chat_history = self.conversation.get_chat_history()
        self.assertEqual(len(chat_history), 2)
        self.assertEqual(chat_history[0], {"role": "user", "content": "Hello"})
        self.assertEqual(chat_history[1], {"role": "assistant", "content": "Hi there!"})

    def test_render_for_llm(self):
        file_path = "test.py"
        file_content = "print('Hello, World!')"

        with patch("builtins.open", mock_open(read_data=file_content)):
            self.conversation.add_file_read(file_path)
            self.conversation.add_message("user", "Can you modify the file?")
            self.conversation.add_file_edit(
                file_path,
                {
                    "operation": "replace",
                    "old": "Hello, World!",
                    "new": "Hello, Python!",
                },
            )
            self.conversation.add_message("assistant", "I've updated the file for you.")

            rendered = self.conversation.render_for_llm()

        self.assertEqual(len(rendered), 4)
        self.assertEqual(rendered[0]["role"], "assistant")
        self.assertTrue(
            "I've read the contents of the file: test.py" in rendered[0]["content"]
        )
        self.assertEqual(rendered[1]["role"], "user")
        self.assertEqual(rendered[2]["role"], "assistant")
        self.assertTrue(
            "I've made the following edit to the file test.py" in rendered[2]["content"]
        )
        self.assertEqual(rendered[3]["role"], "assistant")
        self.assertEqual(rendered[3]["content"], "I've updated the file for you.")

    def test_generate_diff(self):
        file_path = "test.py"
        file_content = "print('Hello, World!')"
        edit_operation = {
            "operation": "replace",
            "old": "Hello, World!",
            "new": "Hello, Python!",
        }

        with patch("builtins.open", mock_open(read_data=file_content)):
            diff = self.conversation._generate_diff(file_path, edit_operation)

        self.assertEqual(diff, "- Hello, World!\n+ Hello, Python!")

    def test_verify_edits(self):
        file_path = "test.py"
        file_content = "print('Hello, Python!')"
        edit_operation = {
            "operation": "replace",
            "old": "Hello, World!",
            "new": "Hello, Python!",
        }

        self.conversation.add_file_edit(file_path, edit_operation)

        with patch("builtins.open", mock_open(read_data=file_content)):
            inconsistencies = self.conversation.verify_edits()

        self.assertEqual(inconsistencies, [])

    def test_verify_edits_with_inconsistency(self):
        file_path = "test.py"
        file_content = "print('Hello, World!')"  # Unchanged content
        edit_operation = {
            "operation": "replace",
            "old": "Hello, World!",
            "new": "Hello, Python!",
        }

        self.conversation.add_file_edit(file_path, edit_operation)

        with patch("builtins.open", mock_open(read_data=file_content)):
            inconsistencies = self.conversation.verify_edits()

        self.assertEqual(len(inconsistencies), 1)
        self.assertTrue("Expected replacement not found" in inconsistencies[0])


if __name__ == "__main__":
    unittest.main()
