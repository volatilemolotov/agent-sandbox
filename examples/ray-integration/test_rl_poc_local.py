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

import unittest
from unittest import mock

import rl_poc_local

# @ray.remote wraps RLEnvironmentWorker in an ActorClass, whose normal
# interface only exposes .remote() (i.e. it needs a real Ray cluster).
# __ray_metadata__.modified_class is Ray's own escape hatch back to the
# plain, undecorated class, letting step()/teardown()'s actual logic be
# exercised directly without ray.init() or any real actor.
_PlainWorker = rl_poc_local.RLEnvironmentWorker.__ray_metadata__.modified_class


def _worker_with_mock_sandbox():
    worker = _PlainWorker.__new__(_PlainWorker)
    worker.sandbox = mock.MagicMock()
    worker.client = mock.MagicMock()
    return worker


class StepTest(unittest.TestCase):
    def test_exact_match_returns_success(self):
        worker = _worker_with_mock_sandbox()
        worker.sandbox.commands.run.return_value = mock.Mock(stdout="55\n", stderr="", exit_code=0)

        observation, reward, done = worker.step("print(fib(10))")

        worker.sandbox.files.write.assert_called_once_with("agent_action.py", "print(fib(10))")
        worker.sandbox.commands.run.assert_called_once_with("python agent_action.py", timeout=5)
        self.assertEqual(observation, {"stdout": "55", "stderr": "", "exit_code": 0})
        self.assertEqual(reward, 1.0)
        self.assertTrue(done)

    def test_nonzero_exit_code_is_penalized(self):
        worker = _worker_with_mock_sandbox()
        worker.sandbox.commands.run.return_value = mock.Mock(stdout="", stderr="Traceback", exit_code=1)

        _, reward, done = worker.step("raise Exception('boom')")

        self.assertEqual(reward, -1.0)
        self.assertFalse(done)

    def test_near_match_output_is_not_a_false_positive(self):
        # Guards the "avoid false positives (e.g. '155' or '55 0')" comment
        # in the source: a superstring of "55" must not count as a match.
        worker = _worker_with_mock_sandbox()
        worker.sandbox.commands.run.return_value = mock.Mock(stdout="155", stderr="", exit_code=0)

        _, reward, done = worker.step("print(155)")

        self.assertEqual(reward, 0.0)
        self.assertFalse(done)


class TeardownTest(unittest.TestCase):
    def test_deletes_all_claims(self):
        worker = _worker_with_mock_sandbox()
        worker.teardown()
        worker.client.delete_all.assert_called_once()


class InitTest(unittest.TestCase):
    @mock.patch("rl_poc_local.SandboxClient")
    def test_claims_from_the_given_warmpool_via_a_tunnel(self, mock_sandbox_client_cls):
        mock_client = mock_sandbox_client_cls.return_value

        worker = _PlainWorker("ray-pool")

        self.assertIs(worker.client, mock_client)
        config = mock_sandbox_client_cls.call_args.kwargs["connection_config"]
        self.assertIsInstance(config, rl_poc_local.SandboxLocalTunnelConnectionConfig)
        self.assertTrue(mock_sandbox_client_cls.call_args.kwargs["cleanup"])
        mock_client.create_sandbox.assert_called_once_with(
            warmpool="ray-pool", shutdown_after_seconds=3600
        )


if __name__ == "__main__":
    unittest.main()
