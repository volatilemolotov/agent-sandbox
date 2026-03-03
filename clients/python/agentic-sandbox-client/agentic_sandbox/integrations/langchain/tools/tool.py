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

from langchain_core.tools import BaseTool
from pydantic import PrivateAttr

from agentic_sandbox.integrations.sandbox_utils import SandboxSettings


class LangchainSandboxTool(BaseTool):
    """
    Base class for Langchain tools that interact with Agent Sandbox.

    Subclasses must set ``name``, ``description``, and ``args_schema``,
    and implement ``_run``.  The sandbox dependency is stored as a typed
    private attribute so IDEs and type-checkers can surface it, while
    remaining invisible to the LLM's tool-call introspection.

    Args:
        sandbox_settings: Settings used to create a sandbox client.
    """

    _sandbox_settings: SandboxSettings = PrivateAttr()

    def __init__(self, sandbox_settings: SandboxSettings, **kwargs):
        super().__init__(**kwargs)
        self._sandbox_settings = sandbox_settings

    def _run(self, *args, **kwargs):
        raise NotImplementedError
