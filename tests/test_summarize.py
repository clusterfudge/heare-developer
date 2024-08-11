import unittest
from heare.developer.summarize import (
    extract_key_elements,
    summarize_file,
    analyze_code_structure,
)


class TestSummarize(unittest.TestCase):
    def test_extract_key_elements(self):
        test_code = '''
"""
This is a test file docstring.
"""
import os
from datetime import datetime

GLOBAL_VAR = 42

class TestClass:
    """
    This is a test class docstring.
    """
    class_var = "test"
    
    def method1(self):
        """This is method1 docstring."""
        pass
    
    def method2(self, param):
        """This is method2 docstring."""
        pass

def test_function(arg1, arg2) -> str:
    """
    This is test_function docstring.
    """
    return "test"

if __name__ == "__main__":
    print("This is the main execution block")
'''
        result = extract_key_elements(test_code)

        self.assertEqual(result["file_docstring"], "This is a test file docstring.")
        self.assertEqual(result["imports"], ["os", "datetime.datetime"])
        self.assertEqual(result["global_vars"], ["GLOBAL_VAR"])

        self.assertEqual(len(result["classes"]), 1)
        test_class = result["classes"][0]
        self.assertEqual(test_class["name"], "TestClass")
        self.assertEqual(test_class["docstring"], "This is a test class docstring.")
        self.assertEqual(len(test_class["methods"]), 2)
        self.assertEqual(test_class["methods"][0]["name"], "method1")
        self.assertEqual(
            test_class["methods"][0]["docstring"], "This is method1 docstring."
        )
        self.assertEqual(test_class["methods"][1]["name"], "method2")
        self.assertEqual(
            test_class["methods"][1]["docstring"], "This is method2 docstring."
        )
        self.assertEqual(test_class["class_vars"], ["class_var"])

        self.assertEqual(len(result["functions"]), 1)
        test_function = result["functions"][0]
        self.assertEqual(test_function["name"], "test_function")
        self.assertEqual(test_function["params"], ["arg1", "arg2"])
        self.assertEqual(test_function["returns"], "str")
        self.assertEqual(test_function["docstring"], "This is test_function docstring.")

    def test_analyze_code_structure(self):
        test_code = '''
"""
This is a test file docstring.
"""
import os
from datetime import datetime

GLOBAL_VAR = 42

class TestClass:
    """
    This is a test class docstring.
    """
    class_var = "test"
    
    def method1(self):
        """This is method1 docstring."""
        pass
    
    def method2(self, param):
        """This is method2 docstring."""
        pass

def test_function(arg1, arg2) -> str:
    """
    This is test_function docstring.
    """
    return "test"

if __name__ == "__main__":
    print("This is the main execution block")
'''
        result = analyze_code_structure(test_code)

        self.assertEqual(result["loc"], 31)  # 31 lines of code
        self.assertEqual(result["num_classes"], 1)
        self.assertEqual(
            result["num_functions"], 3
        )  # 1 standalone function + 2 methods
        self.assertTrue(result["has_main"])

    def test_summarize_file(self):
        test_code = '''
"""
This is a test file docstring.
"""
import os
from datetime import datetime

GLOBAL_VAR = 42

class TestClass:
    """
    This is a test class docstring.
    """
    class_var = "test"
    
    def method1(self):
        """This is method1 docstring."""
        pass
    
    def method2(self, param):
        """This is method2 docstring."""
        pass

def test_function(arg1, arg2) -> str:
    """
    This is test_function docstring.
    """
    return "test"

if __name__ == "__main__":
    print("This is the main execution block")
'''
        summary = summarize_file(test_code)

        expected_summary = """File Structure:
  Lines of code: 31
  Number of classes: 1
  Number of functions: 3
  Contains main execution block

File Docstring: This is a test file docstring.

Imports:
  - os
  - datetime.datetime

Classes:
  - TestClass
    Docstring: This is a test class docstring.
    Methods:
      - method1
        Docstring: This is method1 docstring.
      - method2
        Docstring: This is method2 docstring.
    Class Variables:
      - class_var

Functions:
  - test_function(arg1, arg2)
    Returns: str
    Docstring: This is test_function docstring.

Global Variables:
  - GLOBAL_VAR"""

        self.assertEqual(summary.strip(), expected_summary.strip())


if __name__ == "__main__":
    unittest.main()
