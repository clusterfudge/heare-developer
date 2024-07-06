import unittest
from unittest.mock import MagicMock
from heare.developer.prompt import build_tree, render_tree, render_sandbox_content, estimate_token_count, create_system_message

class TestPrompt(unittest.TestCase):

    def test_build_tree(self):
        mock_sandbox = MagicMock()
        mock_sandbox.list_sandbox.return_value = [
            ('file1.txt', 'READ'),
            ('dir1/file2.txt', 'WRITE'),
            ('dir1/subdir/file3.txt', 'LIST'),
        ]

        expected_tree = {
            'file1.txt': {'path': 'file1.txt', 'permission': 'READ'},
            'dir1': {
                'file2.txt': {'path': 'dir1/file2.txt', 'permission': 'WRITE'},
                'subdir': {
                    'file3.txt': {'path': 'dir1/subdir/file3.txt', 'permission': 'LIST'}
                }
            }
        }

        result = build_tree(mock_sandbox)
        self.assertEqual(result, expected_tree)

    def test_render_tree(self):
        tree = {
            'file1.txt': {'path': 'file1.txt', 'permission': 'READ'},
            'dir1': {
                'file2.txt': {'path': 'dir1/file2.txt', 'permission': 'WRITE'},
                'subdir': {
                    'file3.txt': {'path': 'dir1/subdir/file3.txt', 'permission': 'LIST'}
                }
            }
        }

        expected_output = """dir1/
  file2.txt (WRITE)
  subdir/
    file3.txt (LIST)
file1.txt (READ)
"""

        result = render_tree(tree)
        self.assertEqual(result, expected_output)

    def test_render_sandbox_content(self):
        mock_sandbox = MagicMock()
        mock_sandbox.list_sandbox.return_value = [
            ('file1.txt', 'READ'),
            ('dir1/file2.txt', 'WRITE'),
        ]

        expected_output = """<sandbox_contents>
dir1/
  file2.txt (WRITE)
file1.txt (READ)
</sandbox_contents>
"""

        result = render_sandbox_content(mock_sandbox, False)
        self.assertEqual(result, expected_output)

    def test_estimate_token_count(self):
        text = "This is a sample text with ten words in it."
        result = estimate_token_count(text)
        self.assertAlmostEqual(result, 13, delta=1)  # 10 words * 1.3 ≈ 13 tokens

    def test_create_system_message(self):
        mock_sandbox = MagicMock()
        mock_sandbox.list_sandbox.return_value = [
            ('file1.txt', 'READ'),
            ('dir1/file2.txt', 'WRITE'),
        ]

        result = create_system_message(mock_sandbox)
        self.assertIn("You are an AI assistant with access to a sandbox environment.", result)
        self.assertIn("<sandbox_contents>", result)
        self.assertIn("file1.txt (READ)", result)
        self.assertIn("dir1/", result)
        self.assertIn("file2.txt (WRITE)", result)
        self.assertIn("</sandbox_contents>", result)
        self.assertIn("You can read, write, and list files/directories, as well as execute some bash commands.", result)

if __name__ == '__main__':
    unittest.main()