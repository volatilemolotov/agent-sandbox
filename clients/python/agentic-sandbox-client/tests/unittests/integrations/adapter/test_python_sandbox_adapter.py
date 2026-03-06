from k8s_agent_sandbox.integrations.adapter import PythonCodeSandboxIntegrationAdapter
from test_utils.integrations.sandbox_tests_base import (
    SandboxResultTest,
    SandboxJsonResultTest,
)


class TestPythonSandboxAdapterResults(SandboxResultTest):
    def _execute_in_sandbox(self):
        adapter = PythonCodeSandboxIntegrationAdapter(self.sandbox_settings_mock)
        return adapter.execute(code="some_code")


class TestPythonSandboxAdapterAsToolResults(SandboxJsonResultTest):
    def _execute_in_sandbox(self):
        adapter = PythonCodeSandboxIntegrationAdapter(self.sandbox_settings_mock)
        return adapter.execute_as_tool(code="some_code")
