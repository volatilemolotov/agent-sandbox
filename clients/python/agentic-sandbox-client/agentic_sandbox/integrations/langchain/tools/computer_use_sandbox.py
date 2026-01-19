from agentic_sandbox.integrations.sandbox_utils.tools import (
    COMMON_COMPUTER_USE_TOOL_DOCSTRING_DESCRIPTION,
)
from agentic_sandbox.integrations.sandbox_utils.computer_use_sandbox import (
    execute_computer_use_query_tool_and_handle_errors,
)
from .tool import sandbox_tool


def create_computer_use_sandbox_tool(
    sandbox_settings, description=COMMON_COMPUTER_USE_TOOL_DOCSTRING_DESCRIPTION
):
    """
    Create Langchain tool that executes Computer Use queries inside the Agent Sandbox.

    Args:
        sandbox_settings: Settings to create a sandbox.
        description: Tool description.

    """
    return sandbox_tool(sandbox_settings, description)(execute_query_in_sandbox)


def execute_query_in_sandbox(code: str, **kwargs) -> dict:
    sandbox_settings = kwargs["sandbox"]
    return execute_computer_use_query_tool_and_handle_errors(sandbox_settings, code)
