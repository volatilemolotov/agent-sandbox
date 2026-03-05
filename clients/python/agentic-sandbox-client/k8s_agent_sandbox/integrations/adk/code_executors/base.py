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

from typing import ClassVar
from abc import (
    ABC,
    abstractmethod,
)
import logging

from google.adk.agents.invocation_context import InvocationContext
from google.adk.code_executors.code_execution_utils import (
    CodeExecutionResult,
    CodeExecutionInput,
)
from google.adk.code_executors.base_code_executor import BaseCodeExecutor

from k8s_agent_sandbox.sandbox_client import ExecutionResult
from k8s_agent_sandbox.integrations.sandbox_settings import BaseSandboxSettings
from k8s_agent_sandbox.integrations.adapter.base import (
    create_sandbox_error_message_with_traceback,
    SANDBOX_ERROR_MESSAGE,
)
from k8s_agent_sandbox.integrations.adapter.base import BaseSandboxIntegrationAdapter

logger = logging.getLogger(__name__)


class BaseADKSandboxCodeExecutor(BaseCodeExecutor, ABC):
    """
    A subclass of ADK's 'BaseCodeExecutor' that can interact with Agent Sandbox.

    Attributes:
        SANDBOX_ADAPTER_CLS: Class of the adapter that has to hadnle actual execution of a sandbox.

    Args:
        sandbox_settings: Settings for a sandbox to create.
    """

    SANDBOX_ADAPTER_CLS: ClassVar[type[BaseSandboxIntegrationAdapter]]

    def __init__(
        self,
        sandbox_settings: BaseSandboxSettings,
    ):
        super().__init__()
        self._sandbox_settings = sandbox_settings
        self._adapter = self.__class__.SANDBOX_ADAPTER_CLS(self._sandbox_settings)

    def execute_code(
        self,
        invocation_context: InvocationContext,
        code_execution_input: CodeExecutionInput,
    ) -> CodeExecutionResult:
        """
        Executes code in a sandbox.
        """

        try:
            result = self._execute_code(
                code=code_execution_input.code,
            )
        except Exception as e:
            logger.exception(SANDBOX_ERROR_MESSAGE)
            return sandbox_error_to_code_executor_error(e)

        return sandbox_result_to_code_executor_result(result)

    @abstractmethod
    def _execute_code(self, code: str, timeout: int = 60) -> ExecutionResult:
        """Implementation of the executor login"""


def sandbox_result_to_code_executor_result(result: ExecutionResult):
    """Creates code executor result from sandbox execution result"""
    return CodeExecutionResult(
        stdout=result.stdout,
        stderr=result.stderr,
    )


def sandbox_error_to_code_executor_error(error: Exception):
    """Creates code executor result from sandbox execution error"""
    message = create_sandbox_error_message_with_traceback(error)

    return CodeExecutionResult(
        stderr=message,
    )
