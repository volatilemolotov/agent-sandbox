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

import rl_production_loop

# See ../test_rl_poc_local.py for why __ray_metadata__.modified_class is
# used here: it's Ray's own escape hatch back to the plain, undecorated
# class, so these actors' logic can be exercised directly without
# ray.init() or a real cluster. .remote()/ray.get() calls inside the
# methods under test are handled by constructing instances via __new__
# (bypassing __init__'s own real SecureEnvironmentActor.remote() calls)
# and patching ray.get to pass its argument straight through.
_PlainSecureEnvironmentActor = rl_production_loop.SecureEnvironmentActor.__ray_metadata__.modified_class
_PlainRolloutWorkerActor = rl_production_loop.RolloutWorkerActor.__ray_metadata__.modified_class
_PlainRLPolicyTrainer = rl_production_loop.RLPolicyTrainer.__ray_metadata__.modified_class


class SecureEnvironmentActorTest(unittest.TestCase):
    def _actor_with_mock_sandbox(self):
        actor = _PlainSecureEnvironmentActor.__new__(_PlainSecureEnvironmentActor)
        actor.env_id = "env-sandbox-w0-e0"
        actor.sandbox = mock.MagicMock()
        actor.client = mock.MagicMock()
        actor.t_adopted = 1000.0
        return actor

    @mock.patch("rl_production_loop.random.choice", return_value=True)
    @mock.patch("rl_production_loop.random.random", return_value=0.25)
    def test_step_parses_stdout_as_reward_on_success(self, mock_random, mock_choice):
        actor = self._actor_with_mock_sandbox()
        actor.sandbox.commands.run.return_value = mock.Mock(stdout="12.5\n", exit_code=0)

        observation, reward, done = actor.step(2)

        actor.sandbox.files.write.assert_called_once_with(
            "agent_action.py", "import random; print(2 + 10)"
        )
        self.assertEqual(observation, [0.25, 0.25, 0.25, 0.25])
        self.assertEqual(reward, 12.5)
        self.assertTrue(done)

    @mock.patch("rl_production_loop.random.choice", return_value=False)
    @mock.patch("rl_production_loop.random.random", return_value=0.1)
    def test_step_keeps_default_reward_on_nonzero_exit(self, mock_random, mock_choice):
        actor = self._actor_with_mock_sandbox()
        actor.sandbox.commands.run.return_value = mock.Mock(stdout="", exit_code=1)

        _, reward, done = actor.step(2)

        self.assertEqual(reward, -1.0)
        self.assertFalse(done)

    @mock.patch("rl_production_loop.random.choice", return_value=False)
    @mock.patch("rl_production_loop.random.random", return_value=0.1)
    def test_step_keeps_default_reward_on_unparseable_stdout(self, mock_random, mock_choice):
        actor = self._actor_with_mock_sandbox()
        actor.sandbox.commands.run.return_value = mock.Mock(stdout="not-a-number", exit_code=0)

        _, reward, _ = actor.step(2)

        self.assertEqual(reward, -1.0)

    def test_cleanup_releases_the_claimed_sandbox(self):
        actor = self._actor_with_mock_sandbox()
        actor.sandbox.claim_name = "claim-123"

        actor.cleanup()

        actor.client.delete_sandbox.assert_called_once_with("claim-123")

    @mock.patch("k8s_agent_sandbox.SandboxClient")
    def test_init_claims_from_the_native_template_and_pool(self, mock_sandbox_client_cls):
        mock_client = mock_sandbox_client_cls.return_value

        actor = _PlainSecureEnvironmentActor("env-0")

        self.assertIs(actor.client, mock_client)
        mock_client.create_sandbox.assert_called_once_with(
            template="ray-native-template", warmpool="ray-native-pool"
        )


class RolloutWorkerActorTest(unittest.TestCase):
    def _worker_with_mock_envs(self, n=2):
        worker = _PlainRolloutWorkerActor.__new__(_PlainRolloutWorkerActor)
        worker.worker_id = 0
        worker.envs = [mock.MagicMock() for _ in range(n)]
        worker.policy_weights = None
        return worker

    def test_sync_weights_stores_the_given_weights(self):
        worker = self._worker_with_mock_envs()
        worker.sync_weights({"layer1": [1, 2, 3]})
        self.assertEqual(worker.policy_weights, {"layer1": [1, 2, 3]})

    @mock.patch("rl_production_loop.ray.get", side_effect=lambda futures: futures)
    @mock.patch("rl_production_loop.random.random", side_effect=[0.9, 0.1])
    def test_collect_rollouts_aggregates_trajectories(self, mock_random, mock_ray_get):
        worker = self._worker_with_mock_envs(n=2)
        worker.envs[0].step.remote.return_value = ([0.1], -1.0, False)
        worker.envs[1].step.remote.return_value = ([0.2], 1.0, False)

        rollouts = worker.collect_rollouts(num_steps=1)

        worker.envs[0].step.remote.assert_called_once_with(1)  # random()=0.9 > 0.5 -> action 1
        worker.envs[1].step.remote.assert_called_once_with(0)  # random()=0.1 <= 0.5 -> action 0
        self.assertEqual(rollouts, [([0.1], 1, -1.0), ([0.2], 0, 1.0)])

    @mock.patch("rl_production_loop.ray.get", side_effect=lambda futures: futures)
    @mock.patch("rl_production_loop.random.random", return_value=0.9)
    def test_collect_rollouts_truncates_when_any_env_reports_done(self, mock_random, mock_ray_get):
        worker = self._worker_with_mock_envs(n=1)
        worker.envs[0].step.remote.return_value = ([0.1], 1.0, True)

        rollouts = worker.collect_rollouts(num_steps=5)

        # the loop must have broken after the first step, not run all 5
        self.assertEqual(worker.envs[0].step.remote.call_count, 1)
        self.assertEqual(len(rollouts), 1)

    @mock.patch("rl_production_loop.ray.get", side_effect=lambda futures: futures)
    def test_shutdown_envs_cleans_up_every_env(self, mock_ray_get):
        worker = self._worker_with_mock_envs(n=2)
        worker.shutdown_envs()
        for env in worker.envs:
            env.cleanup.remote.assert_called_once()


class RLPolicyTrainerTest(unittest.TestCase):
    def _trainer_with_mock_workers(self, n=2):
        trainer = _PlainRLPolicyTrainer.__new__(_PlainRLPolicyTrainer)
        trainer.weights = {"layer1": [1.0, 2.0]}
        trainer.workers = [mock.MagicMock() for _ in range(n)]
        return trainer

    @mock.patch("rl_production_loop.ray.get", side_effect=lambda futures: futures)
    def test_train_episode_broadcasts_weights_and_collects_from_every_worker(self, mock_ray_get):
        trainer = self._trainer_with_mock_workers()
        for w in trainer.workers:
            w.collect_rollouts.remote.return_value = []

        trainer.train_episode(steps_per_worker=10)

        for w in trainer.workers:
            w.sync_weights.remote.assert_called_once_with(trainer.weights)
            w.collect_rollouts.remote.assert_called_once_with(10)

    @mock.patch("rl_production_loop.ray.get", side_effect=lambda futures: futures)
    def test_train_episode_aggregates_rewards_and_updates_weights(self, mock_ray_get):
        trainer = self._trainer_with_mock_workers(n=2)
        trainer.workers[0].collect_rollouts.remote.return_value = [([0], 1, 1.0), ([0], 0, -1.0)]
        trainer.workers[1].collect_rollouts.remote.return_value = [([0], 1, 2.0)]

        total_rewards = trainer.train_episode(steps_per_worker=10)

        self.assertEqual(total_rewards, 2.0)  # 1.0 + -1.0 + 2.0
        for actual, expected in zip(trainer.weights["layer1"], [1.01, 2.01]):
            self.assertAlmostEqual(actual, expected)

    @mock.patch("rl_production_loop.ray.get", side_effect=lambda futures: futures)
    def test_shutdown_all_workers_shuts_down_every_worker(self, mock_ray_get):
        trainer = self._trainer_with_mock_workers()
        trainer.shutdown_all_workers()
        for w in trainer.workers:
            w.shutdown_envs.remote.assert_called_once()


if __name__ == "__main__":
    unittest.main()
