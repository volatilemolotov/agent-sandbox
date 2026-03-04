from typing import Callable, Any
import textwrap
from enum import Enum

from pydantic import BaseModel, Field

from k8s_agent_sandbox.sandbox_client import ExecutionResult
from k8s_agent_sandbox.integrations import SandboxSettings

class CommonBaseInputSchema(BaseModel):
    timeout: int = Field(default=60, description="Timeout in seconds which stops execution with error when reached.")


class ExecutionResultStatus(str, Enum):
    SUCCESS = "success"
    FAILURE = "failure"
    ERROR = "error"


EXECUTION_RESULT_STATUS_DESCRIPTION=\
f"""
The execution status with the next possible values:
  * {ExecutionResultStatus.SUCCESS.value}: Execution is successful.
  * {ExecutionResultStatus.FAILURE.value}: Execution completed but with failure (non-zero return code).
  * {ExecutionResultStatus.ERROR.value}: Sandbox failed with unexpected internal error.
"""

class CommonExecutionResultSchema(BaseModel):
    status: ExecutionResultStatus = Field(description=EXECUTION_RESULT_STATUS_DESCRIPTION)
    exit_code: int | None = Field(description=f"Exit code of the executed process. Presented only when 'status' is not '{ExecutionResultStatus.ERROR.value}'.")
    stdout: str | None = Field(description=f"Stdout of the executed code. Presented only when 'status' is not '{ExecutionResultStatus.ERROR.value}'.")
    stderr: str | None = Field(description=f"Stderr of the executed code. Presented only when 'status' is not '{ExecutionResultStatus.ERROR.value}'.")
    sandbox_error: str | None = Field(description=f"Text of the sandbox internal error. Only present when 'status' is '{ExecutionResultStatus.ERROR.value}'.")


class IntegrationSandboxExecutor:
    """
    Base Sandbox Executor class. In can be subclassed in order implement some interaction with a sandbox.

    Args:
        sandbox_settings: Settings to create a sandbox.
    """

    TOOL_NAME: str
    TOOL_DESCRIPTION: str
    INPUT_SCHEMA: type[BaseModel]
    RESULT_SCHEMA: type[BaseModel]
    

    def __init__(self, sandbox_settings: SandboxSettings):
        self._sandbox_settings = sandbox_settings
    
    def execute_as_tool(self, **args: str) -> dict:
        """
        Execute sandbox as a common tool with JSON serializable results and errors.

        Args:
            timeout: Execution timeout.
            args: Tool parameters that has to be passed by the LLM when it calls this tool.
        
        Returns: 
            JSON serializable dict that can be handled by a common agent tool.
        """
        try:
            result = self.execute(**args,)
        except Exception as e:
            return sandbox_error_to_json(e)
        
        return sandbox_result_to_json(result)


    def execute(self, **args) -> ExecutionResult:
        """The actual implementation of sandbox execution"""
        raise NotImplementedError()


def sandbox_result_to_json(execution_result: ExecutionResult):
    """
    Convert sandbox result to a JSON serializable format
    that can be used by the most of the agent tools,
    """
    return {
        "status": (ExecutionResultStatus.SUCCESS.value if execution_result.exit_code == 0 else ExecutionResultStatus.FAILURE.value),
        "exit_code": execution_result.exit_code,
        "stdout": execution_result.stdout,
        "stderr": execution_result.stderr,
    }


def sandbox_error_to_json(error: Exception):
    """
    Return JSON serializable error message that
    can be used by the most of the agent tools.
    """
    return {
        "status": ExecutionResultStatus.ERROR.value,
        "stderr": str(error),
    }

class SandboxExecutorMixin: 
    @classmethod
    def get_sandbox_executer_class(cls) -> type[IntegrationSandboxExecutor]:
        """
        Returns an executor class which will be used to create and interact with a sandbox.

        """
        raise NotImplementedError()
