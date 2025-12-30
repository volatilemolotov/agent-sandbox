from langchain.tools import tool

from agentic_sandbox.integrations.base import with_sandbox
from agentic_sandbox.integrations.python_sandbox import (
    TOOL_DESCRIPTION,
    run_python_code_in_sandbox,
)


def create_python_sandbox_tool(sandbox_settings, description=TOOL_DESCRIPTION):
    """
    Create Langchain tool that runs Python code inside Agent Sandbox

    Args:
        sandbox_settings: Settings to create a sandbox.
        description: Tool description.

    """

    @tool(description=description)
    @with_sandbox(sandbox_settings)
    def execute_python_code_in_sandbox(code: str, **kwargs) -> dict: 
        sandbox_params = kwargs["sandbox"]
        result = run_python_code_in_sandbox(sandbox_params.settings, code)  
        return {"status": "success", "stdout": result.stdout, "stderr": result.stderr, "exit_code": result.exit_code}

    return execute_python_code_in_sandbox


