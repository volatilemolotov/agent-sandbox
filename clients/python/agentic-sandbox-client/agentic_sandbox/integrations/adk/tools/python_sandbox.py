from agentic_sandbox.integrations.python_sandbox import (
    TOOL_DESCRIPTION,
    run_python_code_in_sandbox,
)
from .base import SandboxTool 


def execute_python_code_in_sandbox(code: str, **kwargs) -> dict: 

    sandbox_params = kwargs["sandbox"]
    result = run_python_code_in_sandbox(sandbox_params.settings, code)  
    return {"status": "success", "stdout": result.stdout, "stderr": result.stderr, "exit_code": result.exit_code}


class PythonSandboxTool(SandboxTool):
    func = execute_python_code_in_sandbox
    description = TOOL_DESCRIPTION
