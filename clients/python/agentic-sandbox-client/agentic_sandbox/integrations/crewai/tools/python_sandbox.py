from typing import Type
from pydantic import BaseModel, Field

from agentic_sandbox.integrations.sandbox_utils.python_sandbox import (
    execute_python_tool_and_handle_errors,
)

from agentic_sandbox.integrations.sandbox_utils.tools import (
    COMMON_CODE_TOOL_DESCRIPTION,
    COMMON_CODE_TOOL_CODE_ARG_DESCRIPTION,
    COMMON_TOOL_RESULT_DESCRIPTION,
)
from .base import CrewAISandboxTool


TOOL_DESCRIPTION = f"""
{COMMON_CODE_TOOL_DESCRIPTION}
Returns:
{COMMON_TOOL_RESULT_DESCRIPTION}
"""

class PythonSandboxInput(BaseModel):
    """Input schema for Python Sandbox Tool."""
    code: str = Field(..., description=COMMON_CODE_TOOL_CODE_ARG_DESCRIPTION)

class PythonSandboxTool(CrewAISandboxTool):
    name: str = "Python sandbox"
    description: str = TOOL_DESCRIPTION
    args_schema: Type[BaseModel] = PythonSandboxInput

    def _run(self, code: str) -> dict:
        result = execute_python_tool_and_handle_errors(self._sandbox_settings, code)
        return result
