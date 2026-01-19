from google.adk.code_executors.code_execution_utils import CodeExecutionResult
from google.adk.code_executors.base_code_executor import BaseCodeExecutor

from agentic_sandbox.integrations.sandbox_utils import SandboxSettings
from agentic_sandbox.sandbox_client import ExecutionResult


class SandboxCodeExecutor(BaseCodeExecutor):
    """
    Base Agent Sandbox Code Executor.

    Args:
        sandbox_settings: Settings for a sandbox to create.
    """

    def __init__(self, sandbox_settings: SandboxSettings):
        super().__init__()
        self._sandbox_settings = sandbox_settings


def sandbox_result_to_code_executor_result(result: ExecutionResult):
    """Creates code executor result from sandbox execution result"""
    return CodeExecutionResult(
        stdout=result.stdout,
        stderr=result.stderr,
    )


def sandbox_error_to_code_executor_error(error: Exception):
    """Creates code executor result from sandbox execution error"""
    return CodeExecutionResult(
        stderr=f"Sandbox error: {str(error)}",
    )
