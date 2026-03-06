from k8s_agent_sandbox.integrations.adapter import ComputerUseSandboxIntegrationAdapter
from test_utils.integrations.sandbox_tests_base import (
    SandboxResultTest,
    SandboxJsonResultTest,
)


class TestComputerUseSandboxAdapterResults(SandboxResultTest):
    def _execute_in_sandbox(self):
        adapter = ComputerUseSandboxIntegrationAdapter(self.sandbox_settings_mock)
        return adapter.execute(query="some query")


class TestComputerUseSandboxAdapterAsToolResults(SandboxJsonResultTest):
    def _execute_in_sandbox(self):
        adapter = ComputerUseSandboxIntegrationAdapter(self.sandbox_settings_mock)
        return adapter.execute_as_tool(query="some query")
