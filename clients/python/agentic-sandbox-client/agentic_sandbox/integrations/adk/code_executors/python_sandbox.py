from google.adk.agents.invocation_context import InvocationContext
from google.adk.code_executors.base_code_executor import BaseCodeExecutor
from google.adk.code_executors.code_execution_utils import CodeExecutionInput
from google.adk.code_executors.code_execution_utils import CodeExecutionResult
from google.adk.code_executors.base_code_executor import BaseCodeExecutor

from agentic_sandbox.integrations.sandbox_settings import SandboxSettings

class PythonSandboxCodeExecutor(BaseCodeExecutor):
    def __init__(self, sandbox_settings: SandboxSettings):
        super().__init__()
        self._sandbox_settings = sandbox_settings


    def execute_code(
          self,
          invocation_context: InvocationContext,
          code_execution_input: CodeExecutionInput,
      ) -> CodeExecutionResult:

        with self._sandbox_settings.create_client() as sandbox:
            # TODO: implement file upload and download

            sandbox.write("main.py",  code_execution_input.code)

            result = sandbox.run("python3 main.py")

            return CodeExecutionResult(
                stdout=result.stdout,
                stderr=result.stderr,
                output_files=[],
            )
    
