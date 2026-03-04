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

from typing import (
    Any,
)
from google.genai import types
from google.adk.tools import BaseTool, ToolContext

from k8s_agent_sandbox.integrations.sandbox_utils import SandboxSettings
from k8s_agent_sandbox.integrations.executor import SandboxExecutorMixin


class BaseADKSandboxTool(BaseTool, SandboxExecutorMixin):
    """
    A subclass of ADK's 'BaseTool' that can interact with Agent Sandbox.
    Args:
        sandbox_settings: Settings to create a sandbox.
    """
    
    def __init__(
       self,
       sandbox_settings: SandboxSettings,
    ):
        executor_cls = self.__class__.get_sandbox_executer_class()
        super().__init__(
            name=executor_cls.TOOL_NAME,
            description=executor_cls.TOOL_DESCRIPTION
        )
        self._sandbox_settings = sandbox_settings
        self._executor = executor_cls(self._sandbox_settings)


    async def run_async(
        self, *, args: dict[str, Any], tool_context: ToolContext
    ) -> Any:
        return self._executor.execute_as_tool(**args)

    def _get_declaration(self):
        return types.FunctionDeclaration(
            name=self.name,
            description=self.description,
            parameters_json_schema=self._executor.__class__.INPUT_SCHEMA.model_json_schema(),
            response_json_schema=self._executor.__class__.RESULT_SCHEMA.model_json_schema(),
        )
 
