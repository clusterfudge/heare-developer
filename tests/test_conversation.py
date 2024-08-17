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
        self.assertEqual(len(chat_history), 5)
        self.assertEqual(chat_history[0]["role"], "user")
        self.assertEqual(chat_history[1]["role"], "assistant")
        self.assertEqual(chat_history[2]["role"], "file_read")
        self.assertEqual(chat_history[3]["role"], "assistant")
        self.assertEqual(chat_history[4]["role"], "file_edit")

    def test_invalid_edit_operation(self):
        self.conversation.add_file_read("test.txt", "Hello, world!")
        with self.assertRaises(ValueError):
            self.conversation.add_file_edit(
                "test.txt", {"operation": "invalid_operation"}
            )

    def test_render_for_llm(self):
        self.conversation.add_file_read("test.py", "print('Hello, World!')")
        edit_operation = {"operation": "replace", "old": "World", "new": "Python"}
        self.conversation.add_file_edit("test.py", edit_operation)
        self.conversation.add_message("user", "Please check the file content.")

        rendered = self.conversation.render_for_llm()
        self.assertEqual(len(rendered), 3)
        self.assertEqual(rendered[0]["role"], "file_content")
        self.assertIn("print('Hello, Python!')", rendered[0]["content"])
        self.assertEqual(rendered[1]["role"], "file_edit")
        self.assertIn("- World", rendered[1]["content"])
        self.assertIn("+ Python", rendered[1]["content"])
        self.assertEqual(
            rendered[2], {"role": "user", "content": "Please check the file content."}
        )

    def test_generate_diff(self):
        self.conversation.add_file_read("test.py", "print('Hello, World!')")
        edit_operation = {"operation": "replace", "old": "World", "new": "Python"}
        diff = self.conversation._generate_diff("test.py", edit_operation)
        self.assertEqual(diff, "- World\n+ Python")

    def test_file_read_order(self):
        self.conversation.add_file_read("test1.py", "print('Hello')")
        self.conversation.add_file_read("test2.py", "print('World')")
        self.conversation.add_file_read("test1.py", "print('Hello, again')")
        self.assertEqual(self.conversation.file_read_order, ["test1.py", "test2.py"])


if __name__ == "__main__":
    unittest.main()
