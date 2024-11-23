import unittest
from typing import Optional
from heare.developer.tools import tool
from heare.developer.sandbox import Sandbox


# Test fixtures
@tool
def simple_func(sandbox: Sandbox, arg1: str):
    """A simple function with one required argument.

    Args:
        arg1: First argument description
    """
    return arg1


@tool
def multi_arg_func(
    sandbox: Sandbox, required1: str, required2: int, optional1: Optional[bool] = None
):
    """A function with multiple arguments, some optional.

    Args:
        required1: First required argument
        required2: Second required argument
        optional1: First optional argument
    """
    return required1, required2, optional1


@tool
def no_docstring_func(sandbox: Sandbox, arg1: str, optional1: Optional[str] = None):
    return arg1


class TestToolDecorator(unittest.TestCase):
    def test_sandbox_parameter_validation(self):
        """Test that tool decorator validates sandbox parameter"""
        # Test missing sandbox parameter
        with self.assertRaises(ValueError) as cm:

            @tool
            def no_sandbox(arg1: str):
                pass

        self.assertIn("must be 'sandbox'", str(cm.exception))

        # Test wrong parameter name
        with self.assertRaises(ValueError) as cm:

            @tool
            def wrong_param_name(wrong_name: Sandbox, arg1: str):
                pass

        self.assertIn("must be 'sandbox'", str(cm.exception))

        # Test wrong parameter type
        with self.assertRaises(ValueError) as cm:

            @tool
            def wrong_param_type(sandbox: str, arg1: str):
                pass

        self.assertIn("must be annotated with 'Sandbox'", str(cm.exception))

        # Test valid sandbox parameter
        @tool
        def valid_func(sandbox: Sandbox, arg1: str):
            pass

        # Should not raise any exception

    def test_schema_basic_structure(self):
        """Test that schema() adds all expected top-level keys"""
        schema = simple_func.schema()
        self.assertIsInstance(schema, dict)
        self.assertIn("name", schema)
        self.assertIn("description", schema)
        self.assertIn("input_schema", schema)
        self.assertIn("properties", schema["input_schema"])
        self.assertIn("required", schema["input_schema"])

    def test_schema_name(self):
        """Test that schema name matches function name"""
        self.assertEqual(simple_func.schema()["name"], "simple_func")
        self.assertEqual(multi_arg_func.schema()["name"], "multi_arg_func")

    def test_schema_description(self):
        """Test that schema description comes from docstring"""
        self.assertEqual(
            simple_func.schema()["description"],
            "A simple function with one required argument.",
        )

    def test_schema_no_docstring(self):
        """Test handling of functions without docstrings"""
        schema = no_docstring_func.schema()
        self.assertEqual(schema["description"], "")
        self.assertIn("arg1", schema["input_schema"]["properties"])

    def test_required_parameters(self):
        """Test that non-Optional parameters are marked as required"""
        schema = multi_arg_func.schema()
        required = schema["input_schema"]["required"]
        self.assertIn("required1", required)
        self.assertIn("required2", required)
        self.assertNotIn("optional1", required)

    def test_optional_parameters(self):
        """Test that Optional parameters are not marked as required"""
        schema = multi_arg_func.schema()
        self.assertIn("optional1", schema["input_schema"]["properties"])
        self.assertNotIn("optional1", schema["input_schema"]["required"])

    def test_parameter_descriptions(self):
        """Test that parameter descriptions are extracted from docstring"""
        schema = multi_arg_func.schema()
        props = schema["input_schema"]["properties"]
        self.assertEqual(props["required1"]["description"], "First required argument")
        self.assertEqual(props["optional1"]["description"], "First optional argument")

    def test_sandbox_parameter_excluded(self):
        """Test that sandbox parameter is not included in schema"""
        schema = simple_func.schema()
        self.assertNotIn("sandbox", schema["input_schema"]["properties"])
        self.assertNotIn("sandbox", schema["input_schema"]["required"])

    def test_original_function_behavior(self):
        """Test that decorated function still works normally"""

        # Create a minimal sandbox mock
        class MockSandbox:
            pass

        sandbox = MockSandbox()

        # Test simple function
        self.assertEqual(simple_func(sandbox, "test"), "test")

        # Test multi-argument function
        result = multi_arg_func(sandbox, "test", 42)
        self.assertEqual(result, ("test", 42, None))

        # Test with optional argument
        result = multi_arg_func(sandbox, "test", 42, True)
        self.assertEqual(result, ("test", 42, True))


if __name__ == "__main__":
    unittest.main()
