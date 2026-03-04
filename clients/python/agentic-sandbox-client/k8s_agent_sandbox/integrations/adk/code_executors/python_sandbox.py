# Copyright 2026 The Kubernetes Authors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from google.adk.agents.invocation_context import InvocationContext
from google.adk.code_executors.code_execution_utils import CodeExecutionInput
from google.adk.code_executors.code_execution_utils import CodeExecutionResult

from k8s_agent_sandbox.integrations.executor import PythonCodeSandboxIntegrationExecutor
from .base import (
    BaseADKSandboxCodeExecutor,
    sandbox_result_to_code_executor_result,
    sandbox_error_to_code_executor_error,
)


class PythonADKSandboxCodeExecutor(BaseADKSandboxCodeExecutor):
    """
    An ADK agent code executor that executes Python code in the Agent Sandbox

    Args:
        sandbox_settings: Settings for a sandbox to create.
    """
    
    def execute_code(
        self,
        invocation_context: InvocationContext,
        code_execution_input: CodeExecutionInput,
    ) -> CodeExecutionResult:
        """
        Executes code in a sandbox.
        """

        try:
            result = self._executor.execute(
                code=code_execution_input.code,
            )
        except Exception as e:
            return sandbox_error_to_code_executor_error(e)

        return sandbox_result_to_code_executor_result(result)
    
    @classmethod
    def get_sandbox_executer_class(cls) -> type[PythonCodeSandboxIntegrationExecutor]:
        return PythonCodeSandboxIntegrationExecutor
