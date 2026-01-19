from agentic_sandbox.integrations.sandbox_utils.tools import (
    COMMON_COMPUTER_USE_TOOL_DOCSTRING_DESCRIPTION,
)
from agentic_sandbox.integrations.sandbox_utils.computer_use_sandbox import (
    execute_computer_use_query_tool_and_handle_errors,
)
from .base import PredefinedSandboxFunctionTool


def execute_computer_use_query_in_sandbox_tool_fn(
    query: str, timeout: int = 60, **kwargs
) -> dict:
    sandbox_settings = kwargs["sandbox"]

    return execute_computer_use_query_tool_and_handle_errors(
        sandbox_settings,
        query,
        timeout=timeout,
    )


class ComputerUseSandboxTool(PredefinedSandboxFunctionTool):
    func = execute_computer_use_query_in_sandbox_tool_fn
    description = COMMON_COMPUTER_USE_TOOL_DOCSTRING_DESCRIPTION
