# sandbox_env/gymnasium_env.py
from __future__ import annotations

import time
import gymnasium as gym
from gymnasium import spaces
from typing import Optional

from k8s_agent_sandbox import SandboxClient
from k8s_agent_sandbox.models import (
    SandboxLocalTunnelConnectionConfig,
    SandboxGatewayConnectionConfig,
    SandboxInClusterConnectionConfig,
    SandboxDirectConnectionConfig,
)

from .reward_fn import RewardFn


# Connection config factory — keeps __init__ signature clean
_CONNECTION_MODES = {
    "tunnel":     lambda cfg: SandboxLocalTunnelConnectionConfig(**cfg),
    "gateway":    lambda cfg: SandboxGatewayConnectionConfig(**cfg),
    "in_cluster": lambda cfg: SandboxInClusterConnectionConfig(**cfg),
    "direct":     lambda cfg: SandboxDirectConnectionConfig(**cfg),
}


class SandboxEnv(gym.Env):
    """
    A Gymnasium-compatible environment backed by a Kubernetes Agent Sandbox.

    Each episode provisions (or claims from a warmpool) a fresh isolated pod.
    The agent submits shell commands as actions; observations are the resulting
    stdout/stderr text.

    Args:
        reward_fn:      A RewardFn instance that scores each (action, obs, info, task).
        template:       Name of the SandboxTemplate (or warmpool-backed template) to use.
        namespace:      Kubernetes namespace.
        connection_mode: One of "tunnel" (local/KinD), "gateway" (GKE),
                         "in_cluster", or "direct".
        connection_cfg: Extra kwargs forwarded to the connection config constructor
                        (e.g. {"gateway_name": "my-gw"} or {"api_url": "http://..."}).
        max_episode_steps: Hard truncation limit per episode.
        max_obs_length:    Max characters kept from stdout/stderr.
    """

    metadata = {"render_modes": []}

    def __init__(
        self,
        reward_fn: RewardFn,
        warmpool: str = "simple-sandbox-warmpool",
        namespace: str = "default",
        connection_mode: str = "tunnel",
        connection_cfg: Optional[dict] = None,
        max_episode_steps: int = 20,
        max_obs_length: int = 4096,
    ):
        super().__init__()

        if not isinstance(reward_fn, RewardFn):
            raise TypeError(f"reward_fn must be a RewardFn instance, got {type(reward_fn)}")
        if connection_mode not in _CONNECTION_MODES:
            raise ValueError(f"connection_mode must be one of {list(_CONNECTION_MODES)}")

        self.reward_fn         = reward_fn
        self.warmpool          = warmpool
        self.namespace         = namespace
        self.max_episode_steps = max_episode_steps
        self.max_obs_length    = max_obs_length

        # Build the SDK client once — it's reused across episodes
        conn = _CONNECTION_MODES[connection_mode](connection_cfg or {})
        self._client = SandboxClient(connection_config=conn)

        self._sandbox       = None
        self._current_task  = ""
        self._step_count    = 0

        # Gymnasium spaces — text-native; wrap with TokenizedWrapper for RLlib/SB3
        self.observation_space = spaces.Text(max_length=max_obs_length)
        self.action_space      = spaces.Text(max_length=2048)

    # ── Gymnasium API ──────────────────────────────────────────────────────────

    def reset(
        self,
        seed: Optional[int] = None,
        options: Optional[dict] = None,
    ):
        super().reset(seed=seed)
        options = options or {}

        # Tear down the previous sandbox if one exists
        self._close_sandbox()

        # Claim a fresh sandbox (from warmpool if template has one configured)
        self._sandbox = self._client.create_sandbox(
            warmpool=self.warmpool,
            namespace=self.namespace,
        )

        self._current_task = options.get("task", "")
        self._step_count   = 0

        # Let the reward function reset its internal state for the new episode
        self.reward_fn.reset(self._current_task)

        obs  = "Sandbox ready."
        info = {
            "sandbox_id": getattr(self._sandbox, "id", "unknown"),
            "task": self._current_task,
        }
        return obs, info

    def step(self, action: str):
        if self._sandbox is None:
            raise RuntimeError("Call reset() before step().")

        self._step_count += 1
        t0 = time.monotonic()

        try:
            result     = self._sandbox.commands.run(action)
            stdout     = result.stdout or ""
            stderr     = result.stderr or ""
            exit_code  = result.exit_code
        except Exception as exc:
            stdout     = ""
            stderr     = str(exc)
            exit_code  = -1

        elapsed_ms = int((time.monotonic() - t0) * 1000)

        # Observation: prefer stdout, fall back to stderr
        obs = (stdout if stdout else stderr)[: self.max_obs_length]

        info = {
            "exit_code":  exit_code,
            "stdout":     stdout,
            "stderr":     stderr,
            "elapsed_ms": elapsed_ms,
            "step":       self._step_count,
        }

        reward     = self.reward_fn(action, obs, info, self._current_task)
        terminated = False   # reward_fn drives termination logic via info
        truncated  = self._step_count >= self.max_episode_steps

        return obs, reward, terminated, truncated, info

    def close(self):
        self._close_sandbox()

    # ── Internals ─────────────────────────────────────────────────────────────

    def _close_sandbox(self):
        if self._sandbox is not None:
            try:
                self._sandbox.terminate()
            except Exception:
                pass  # best-effort cleanup
            self._sandbox = None
