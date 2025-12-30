from agentic_sandbox.sandbox_client import ExecutionResult
from .sandbox_settings import SandboxSettings


TOOL_DESCRIPTION="""
Executes the code in a sandbox and returs execution results.

Args:
    code (str): Python code to execute.
"""

def run_python_code_in_sandbox(sandbox_settings: SandboxSettings, code: str) -> ExecutionResult:
    """The actual implementation of the Python sandbox that is used by the integration tools""" 

    with sandbox_settings.create_client() as sandbox:
        sandbox.write("main.py", code)

        result = sandbox.run("python3 main.py")

        return result
