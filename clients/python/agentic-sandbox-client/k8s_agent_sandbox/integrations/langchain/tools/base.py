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

from typing import Any
import json

from langchain_core.tools import BaseTool

from k8s_agent_sandbox.integrations.sandbox_utils import SandboxSettings
from k8s_agent_sandbox.integrations.executor import SandboxExecutorMixin


class BaseLangChainSandboxTool(BaseTool, SandboxExecutorMixin):
    """
    A subclass of LangChain's 'BaseTool' that can interact with Agent Sandbox.
    Args:
        sandbox_settings: Settings to create a sandbox.
    """

    def __init__(self, sandbox_settings: SandboxSettings, **kwargs):
        executor_cls = self.__class__.get_sandbox_executer_class()

        # Since Langchain does not provilde ability to specify the result schema,
        # we just put its json-schema formatted version to the description.
        description = f"{executor_cls.TOOL_DESCRIPTION}\n" \
                      f"The JSON Schema of the result is:\n {json.dumps(executor_cls.RESULT_SCHEMA.model_json_schema())}"
        super().__init__(
            name=executor_cls.TOOL_NAME,
            description=description,
            args_schema=executor_cls.INPUT_SCHEMA,
            **kwargs,
        )
        self._sandbox_settings = sandbox_settings
        self._executor = executor_cls(self._sandbox_settings)

    def _run(self, *args: Any, **kwargs: Any) -> Any:
        return self._executor.execute_as_tool(*args, **kwargs)


