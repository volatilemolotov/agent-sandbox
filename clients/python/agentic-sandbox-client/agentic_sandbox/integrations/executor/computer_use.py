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


from pydantic import Field

from agentic_sandbox.sandbox_client import ExecutionResult
from .base import (
    IntegrationSandboxExecutor,
    CommonBaseInputSchema,
    CommonExecutionResultSchema,
)


class ComputerUseSandboxIntegrationExecutor(IntegrationSandboxExecutor): 
    """
    Sandbox Executor that executes computer use queries.
    """
    
    TOOL_NAME = "execute_action_in_sandbox"
    TOOL_DESCRIPTION = "Executes natural language query in a sandbox and returns execution results."

    class INPUT_SCHEMA(CommonBaseInputSchema):
        query: str = Field(description="String with a natural language query to execute within the sandbox.")

    RESULT_SCHEMA=CommonExecutionResultSchema    
    
    def _execute_query(self, query: str, timeout: int = 60) -> ExecutionResult:
        with self._sandbox_settings.create_client() as sandbox:
            result = sandbox.agent(query, timeout)
            return result

    def execute(self, **args) -> ExecutionResult:
        return self._execute_query(**args)


