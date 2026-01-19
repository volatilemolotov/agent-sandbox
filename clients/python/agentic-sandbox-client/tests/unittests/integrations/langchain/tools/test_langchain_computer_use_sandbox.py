from agentic_sandbox.sandbox_client import ExecutionResult

from agentic_sandbox.integrations.sandbox_utils.tools import (
    sandbox_result_to_json,
    sandbox_error_to_json,
)
from agentic_sandbox.integrations.langchain.tools import (
    create_computer_use_sandbox_tool,
)
from test_utils.integrations.sandbox_tests_base import SandboxTestBase


class TestLangchainComputerUseSandboxTool(SandboxTestBase):

    def test_success(self, result_success):

        self._set_execution_result(result_success)
        result = self._execute_in_sandbox()
        expected_result = sandbox_result_to_json(result_success)
        assert result == expected_result

    def test_failure(self, result_failure):

        self._set_execution_result(result_failure)
        result = self._execute_in_sandbox()
        expected_result = sandbox_result_to_json(result_failure)
        assert result == expected_result

    def test_sandbox_error(self, result_error):

        self._set_execution_error(result_error)
        result = self._execute_in_sandbox()
        expected_result = sandbox_error_to_json(result_error)
        assert result == expected_result

    def _execute_in_sandbox(self):
        tool = create_computer_use_sandbox_tool(self.sandbox_settings_mock)
        result = tool.invoke("some query")
        return result
