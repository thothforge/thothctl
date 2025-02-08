from ...src.check_environment.check_environment import (
    get_tool_version,
    is_tool,
    load_tools,
)


def test_is_tool():
    assert (
        is_tool(
            {"name": "terraform", "version": "1.8.1"},
        )
        == True
    )


def test_is_tool_not_found():
    assert is_tool({"name": "non-existent-tool", "version": "1.0.0"}) == False


def test_get_tool_version():
    tools = [{"name": "terraform", "version": "1.8.1"}]
    versions = get_tool_version(tools)
    assert versions["terraform"] == "1.8.1"


# Sample data for testing
version_tools = """
[
  {
    "name": "terraform",
    "version": "1.8.1"
  },
  {
    "name": "terragrunt",
    "version": "0.54.12"
  },
  {
    "name": "thothctl",
    "version": "2.8.4"
  }
]
"""


def test_load_tools_generic_mode():
    """
    Test that load_tools returns the correct tools in generic mode.
    """

    tools = load_tools(mode="generic")
    assert isinstance(tools, list)
    assert len(tools) == 13


def test_load_tools_custom_mode():
    """
    Test that load_tools returns the correct tools in custom mode.
    """

    # Create a temporary tools.json file
    tools_file = "tools.json"
    with open(tools_file, "w") as f:
        f.write('{"custom_tool": {"name": "Custom Tool"}}')

    tools = load_tools(mode="custom")
    assert isinstance(tools, dict)
    assert len(tools) == 1
    assert "custom_tool" in tools
