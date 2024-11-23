from heare.developer.toolbox import Toolbox
from heare.developer.sandbox import Sandbox, SandboxMode
from heare.developer.tools import ALL_TOOLS


def test_schemas_are_consistent():
    """Test that schemas() returns consistent results and matches expected format"""
    sandbox = Sandbox(".", mode=SandboxMode.ALLOW_ALL)
    toolbox = Toolbox(sandbox)

    # Get schemas from toolbox
    generated_schemas = toolbox.schemas()

    # Test schema format
    for schema in generated_schemas:
        # Check required top-level fields
        assert "name" in schema
        assert "description" in schema
        assert "input_schema" in schema

        input_schema = schema["input_schema"]
        assert "type" in input_schema
        assert input_schema["type"] == "object"
        assert "properties" in input_schema
        assert "required" in input_schema

        # Check properties format
        for prop_name, prop in input_schema["properties"].items():
            assert "type" in prop
            assert "description" in prop

        # Check required is a list and all required properties exist
        assert isinstance(input_schema["required"], list)
        for req_prop in input_schema["required"]:
            assert req_prop in input_schema["properties"]


def test_agent_schema_matches_schemas():
    """Test that agent_schema matches schemas()"""
    sandbox = Sandbox(".", mode=SandboxMode.ALLOW_ALL)
    toolbox = Toolbox(sandbox)

    assert (
        toolbox.agent_schema == toolbox.schemas()
    ), "agent_schema should be identical to schemas()"


def test_schemas_match_tools():
    """Test that schemas() generates a schema for each tool"""
    sandbox = Sandbox(".", mode=SandboxMode.ALLOW_ALL)
    toolbox = Toolbox(sandbox)

    schemas = toolbox.schemas()
    tool_names = {tool.__name__ for tool in ALL_TOOLS}
    schema_names = {schema["name"] for schema in schemas}

    assert tool_names == schema_names, "Schema names should match tool names"
