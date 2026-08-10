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

import rl_poc_prod
from k8s_agent_sandbox.models import SandboxGatewayConnectionConfig

# See test_rl_poc_local.py for why __ray_metadata__.modified_class is used:
# it's Ray's own escape hatch back to the plain, undecorated class, so
# step()/teardown() can be exercised directly without ray.init() or a real
# actor. rl_poc_prod.py's step()/teardown() are identical to
# rl_poc_local.py's -- only the connection config in __init__ differs
# (Gateway vs. local tunnel) -- so this mirrors that file's coverage plus
# the config-specific __init__ behavior below.
_PlainWorker = rl_poc_prod.RLEnvironmentWorker.__ray_metadata__.modified_class


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

        self.assertEqual(observation, {"stdout": "55", "stderr": "", "exit_code": 0})
        self.assertEqual(reward, 1.0)
        self.assertTrue(done)

    def test_nonzero_exit_code_is_penalized(self):
        worker = _worker_with_mock_sandbox()
        worker.sandbox.commands.run.return_value = mock.Mock(stdout="", stderr="Traceback", exit_code=1)

        _, reward, done = worker.step("raise Exception('boom')")

        self.assertEqual(reward, -1.0)
        self.assertFalse(done)


class TeardownTest(unittest.TestCase):
    def test_deletes_all_claims(self):
        worker = _worker_with_mock_sandbox()
        worker.teardown()
        worker.client.delete_all.assert_called_once()


class InitTest(unittest.TestCase):
    @mock.patch("rl_poc_prod.SandboxClient")
    def test_claims_from_the_given_warmpool_via_the_gateway(self, mock_sandbox_client_cls):
        mock_client = mock_sandbox_client_cls.return_value

        worker = _PlainWorker("ray-pool")

        self.assertIs(worker.client, mock_client)
        config = mock_sandbox_client_cls.call_args.kwargs["connection_config"]
        self.assertIsInstance(config, SandboxGatewayConnectionConfig)
        self.assertEqual(config.gateway_name, "external-http-gateway")
        self.assertEqual(config.gateway_namespace, "default")
        self.assertTrue(mock_sandbox_client_cls.call_args.kwargs["cleanup"])
        mock_client.create_sandbox.assert_called_once_with(
            warmpool="ray-pool", shutdown_after_seconds=3600
        )


if __name__ == "__main__":
    unittest.main()
