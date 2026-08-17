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

import io
import subprocess
import unittest
import urllib.error
from contextlib import redirect_stdout
from unittest import mock

import workload


def _run(fn, *args):
    """Runs fn and returns its captured stdout as a string."""
    buf = io.StringIO()
    with redirect_stdout(buf):
        fn(*args)
    return buf.getvalue()


class FsAttemptTest(unittest.TestCase):
    def test_prints_ok_when_the_operation_succeeds(self):
        out = _run(workload.fs_attempt, "did a thing", lambda: None)
        self.assertIn("[ok]", out)
        self.assertIn("did a thing", out)

    def test_prints_fail_when_the_operation_raises(self):
        def boom():
            raise RuntimeError("disk full")

        out = _run(workload.fs_attempt, "did a thing", boom)
        self.assertIn("[fail]", out)
        self.assertIn("disk full", out)


class ExpectBlockedTest(unittest.TestCase):
    def test_prints_policy_ok_when_the_operation_raises(self):
        def denied():
            raise PermissionError("denied")

        out = _run(workload.expect_blocked, "read a secret", denied)
        self.assertIn("[policy-ok]", out)
        self.assertIn("blocked read a secret", out)

    def test_prints_policy_fail_when_the_operation_unexpectedly_succeeds(self):
        out = _run(workload.expect_blocked, "read a secret", lambda: None)
        self.assertIn("[policy-fail]", out)


class FilesystemProbeTest(unittest.TestCase):
    def test_write_workspace_writes_the_expected_path_and_content(self):
        m = mock.mock_open()
        with mock.patch("builtins.open", m):
            workload.write_workspace()
        m.assert_called_once_with("/workspace/hello.txt", "w", encoding="utf-8")
        m().write.assert_called_once_with("written by the sandboxed agent\n")

    def test_read_secret_reads_the_expected_path(self):
        m = mock.mock_open(read_data="secret")
        with mock.patch("builtins.open", m):
            workload.read_secret()
        m.assert_called_once_with("/etc/secret-config/token", "r", encoding="utf-8")

    def test_read_audit_state_lists_the_expected_path(self):
        with mock.patch("workload.os.listdir") as mock_listdir:
            workload.read_audit_state()
        mock_listdir.assert_called_once_with("/var/lib/nono-state/nono/audit")


class CredentialProbeTest(unittest.TestCase):
    def test_session_scoped_hex_token_reports_ok(self):
        with mock.patch.dict("os.environ", {"OPENAI_API_KEY": "a" * 64}):
            out = _run(workload.credential_probe)
        self.assertIn("[credential-ok]", out)

    def test_provider_shaped_key_reports_fail(self):
        with mock.patch.dict("os.environ", {"OPENAI_API_KEY": "sk-not-a-phantom-token"}):
            out = _run(workload.credential_probe)
        self.assertIn("[credential-fail]", out)

    def test_missing_key_reports_fail(self):
        with mock.patch.dict("os.environ", {}, clear=True):
            out = _run(workload.credential_probe)
        self.assertIn("[credential-fail]", out)


class ExpectHttpBlockedTest(unittest.TestCase):
    @mock.patch("workload.urllib.request.urlopen")
    def test_403_response_reports_policy_ok(self, mock_urlopen):
        mock_urlopen.side_effect = urllib.error.HTTPError(
            "http://x", 403, "Forbidden", {}, None)
        out = _run(workload.expect_http_blocked, "label", "GET", "http://x")
        self.assertIn("[policy-ok]", out)

    @mock.patch("workload.urllib.request.urlopen")
    def test_non_403_error_reports_policy_fail(self, mock_urlopen):
        mock_urlopen.side_effect = urllib.error.HTTPError(
            "http://x", 500, "Server Error", {}, None)
        out = _run(workload.expect_http_blocked, "label", "GET", "http://x")
        self.assertIn("[policy-fail]", out)
        self.assertIn("500", out)

    @mock.patch("workload.urllib.request.urlopen")
    def test_successful_response_reports_policy_fail(self, mock_urlopen):
        mock_response = mock.MagicMock(status=200)
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response
        out = _run(workload.expect_http_blocked, "label", "GET", "http://x")
        self.assertIn("[policy-fail]", out)
        self.assertIn("unexpectedly allowed", out)

    @mock.patch("workload.urllib.request.urlopen")
    def test_connect_denial_surfaced_as_generic_exception_with_403(self, mock_urlopen):
        mock_urlopen.side_effect = OSError("Tunnel connection failed: 403 Forbidden")
        out = _run(workload.expect_http_blocked, "label", "GET", "http://x")
        self.assertIn("[policy-ok]", out)

    @mock.patch("workload.urllib.request.urlopen")
    def test_unrelated_connection_error_reports_could_not_verify(self, mock_urlopen):
        mock_urlopen.side_effect = OSError("Connection refused")
        out = _run(workload.expect_http_blocked, "label", "GET", "http://x")
        self.assertIn("[policy-fail]", out)
        self.assertIn("could not verify", out)


def _completed(returncode=0, stdout="", stderr=""):
    return subprocess.CompletedProcess(args=["logcli"], returncode=returncode, stdout=stdout, stderr=stderr)


class ToolSandboxProbesTest(unittest.TestCase):
    def _run_probes(self, run_logcli_side_effect):
        with mock.patch("workload.run_logcli", side_effect=run_logcli_side_effect):
            return _run(workload.tool_sandbox_probes)

    def test_reports_tool_ok_for_the_expected_and_unexpected_paths(self):
        def side_effect(*args):
            if "delete" in args:
                return _completed(1, stderr="tool-sandbox denied logcli delete")
            if "labels" in args:
                return _completed(1, stdout="", stderr="403 forbidden")
            if "--limit=5000" in args:
                return _completed(1, stderr="tool-sandbox denied logcli: argv mismatch")
            # the one unmodified, allowed query
            return _completed(0, stdout="payments p99 latency exceeded 900ms\n")

        with mock.patch.dict("os.environ", {}, clear=True):
            out = self._run_probes(side_effect)

        self.assertIn("[tool-ok] Loki identity and address are absent from the agent loop", out)
        self.assertIn("[tool-ok] exact LogCLI incident query returned the seeded Loki log", out)
        self.assertIn("[tool-ok] L7 policy blocked LogCLI from the labels endpoint", out)
        self.assertIn("[tool-ok] invocation policy blocked altered LogCLI arguments", out)
        self.assertIn("[tool-ok] invocation policy blocked LogCLI deletion management", out)
        self.assertNotIn("[tool-fail]", out)

    def test_leaked_loki_env_var_reports_tool_fail(self):
        with mock.patch.dict("os.environ", {"LOKI_TOKEN": "leaked"}):
            out = self._run_probes(lambda *a: _completed(0, stdout="payments p99 latency exceeded 900ms\n"))
        self.assertIn("[tool-fail] a Loki credential or destination leaked into the agent loop", out)

    def test_query_without_expected_output_reports_tool_fail(self):
        with mock.patch.dict("os.environ", {}, clear=True):
            out = self._run_probes(lambda *a: _completed(0, stdout="unexpected output"))
        self.assertIn("[tool-fail] allowed LogCLI query", out)

    def test_labels_call_that_is_not_actually_denied_reports_tool_fail(self):
        with mock.patch.dict("os.environ", {}, clear=True):
            out = self._run_probes(lambda *a: _completed(0, stdout="payments p99 latency exceeded 900ms\n"))
        self.assertIn("[tool-fail] LogCLI L7 policy", out)


if __name__ == "__main__":
    unittest.main()
