"""An in-process stand-in for ``k8s_agent_sandbox``'s async client.

The fake speaks the same surface the provider actually uses — ``commands.run``,
``files.read``/``files.write``, ``status()``, plus the client's create/get/delete — and
backs it with the local machine: "the pod is this host". That keeps the real
:class:`K8sHttpTransport` and :class:`K8sSandboxSession` code under test, including the
shell probes the SDK runs during ``start()``, without needing a cluster.

Deliberate fidelity choices:

* ``commands.run`` takes a command *string* and runs it through ``sh -c``, mirroring the
  in-pod HTTP server, so the provider's ``shlex.join`` round-trip is exercised.
* ``ExecutionResult`` carries ``str``, not ``bytes`` — the same lossiness as the JSON
  ``execute`` endpoint.
* ``files.write`` does **not** create parent directories, so a provider that forgets to
  ``mkdir`` first fails here the way it would against a real server.
"""

from __future__ import annotations

import asyncio
import os
import uuid
from pathlib import Path

from k8s_agent_sandbox.exceptions import SandboxNotFoundError
from k8s_agent_sandbox.models import ExecutionResult


class FakeCommands:
    def __init__(self, sandbox: "FakeAsyncSandbox") -> None:
        self._sandbox = sandbox

    async def run(self, command: str, timeout: int = 60) -> ExecutionResult:
        self._sandbox.assert_live()
        self._sandbox.commands_run.append(command)

        proc = await asyncio.create_subprocess_exec(
            "sh",
            "-c",
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd="/",
            env={**os.environ, "HOME": str(self._sandbox.home)},
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except (asyncio.TimeoutError, TimeoutError):
            proc.kill()
            await proc.wait()
            raise

        return ExecutionResult(
            stdout=stdout.decode("utf-8", errors="replace"),
            stderr=stderr.decode("utf-8", errors="replace"),
            exit_code=proc.returncode if proc.returncode is not None else -1,
        )


class FakeFilesystem:
    def __init__(self, sandbox: "FakeAsyncSandbox") -> None:
        self._sandbox = sandbox

    async def read(
        self, path: str, timeout: int = 60, allow_unsafe_paths: bool = False
    ) -> bytes:
        self._sandbox.assert_live()
        _reject_relative(path, allow_unsafe_paths)
        self._sandbox.files_read.append(path)
        return Path(path).read_bytes()

    async def write(
        self,
        path: str,
        content: bytes | str,
        timeout: int = 60,
        allow_unsafe_paths: bool = False,
    ) -> None:
        self._sandbox.assert_live()
        _reject_relative(path, allow_unsafe_paths)
        self._sandbox.files_written.append(path)
        if isinstance(content, str):
            content = content.encode("utf-8")
        target = Path(path)
        if not target.parent.is_dir():
            # Matches a server that will not implicitly create directories.
            raise FileNotFoundError(f"no such directory: {target.parent}")
        target.write_bytes(content)


class FakeAsyncSandbox:
    def __init__(self, claim_name: str, sandbox_id: str, namespace: str, home: Path) -> None:
        self.claim_name: str | None = claim_name
        self.sandbox_id = sandbox_id
        self.namespace = namespace
        self.home = home
        self.commands = FakeCommands(self)
        self.files = FakeFilesystem(self)
        self.terminated = False

        self.commands_run: list[str] = []
        self.files_read: list[str] = []
        self.files_written: list[str] = []

    @property
    def is_active(self) -> bool:
        return not self.terminated

    def assert_live(self) -> None:
        if self.terminated:
            raise SandboxNotFoundError(f"sandbox '{self.sandbox_id}' has been terminated")

    async def status(self) -> tuple[str, str]:
        if self.terminated:
            return "SandboxNotFound", "Sandbox object not found in Kubernetes."
        return "SandboxReady", ""

    async def close_connection(self) -> None:
        return None

    async def terminate(self) -> None:
        self.terminated = True


class FakeAsyncSandboxClient:
    """Stands in for ``AsyncSandboxClient``."""

    def __init__(self, home: Path) -> None:
        self._home = home
        self._sandboxes: dict[tuple[str, str], FakeAsyncSandbox] = {}
        self._warm_pools: dict[tuple[str, str], str] = {}
        self.created: list[dict[str, object]] = []

    async def create_sandbox(
        self,
        warmpool: str,
        namespace: str = "default",
        sandbox_ready_timeout: int = 180,
        labels: dict[str, str] | None = None,
        *,
        shutdown_after_seconds: int | None = None,
        volume_claim_templates: list[dict] | None = None,
        pod_labels: dict[str, str] | None = None,
        pod_annotations: dict[str, str] | None = None,
    ) -> FakeAsyncSandbox:
        claim_name = f"sandbox-claim-{uuid.uuid4().hex[:8]}"
        sandbox_id = f"{warmpool}-{uuid.uuid4().hex[:5]}"
        self.created.append(
            {
                "warmpool": warmpool,
                "namespace": namespace,
                "labels": labels,
                "shutdown_after_seconds": shutdown_after_seconds,
                "pod_labels": pod_labels,
            }
        )
        sandbox = FakeAsyncSandbox(claim_name, sandbox_id, namespace, self._home)
        self._sandboxes[(namespace, claim_name)] = sandbox
        self._warm_pools[(namespace, claim_name)] = warmpool
        return sandbox

    async def get_sandbox(
        self,
        claim_name: str,
        namespace: str = "default",
        resolve_timeout: int = 30,
        warmpool_name: str | None = None,
    ) -> FakeAsyncSandbox:
        sandbox = self._sandboxes.get((namespace, claim_name))
        if sandbox is None or sandbox.terminated:
            raise SandboxNotFoundError(f"claim '{claim_name}' not found in '{namespace}'")
        existing_pool = self._warm_pools.get((namespace, claim_name))
        if warmpool_name is not None and existing_pool != warmpool_name:
            raise ValueError(
                f"SandboxClaim '{claim_name}' references warmpool '{existing_pool}', "
                f"not '{warmpool_name}'. Refusing to reattach."
            )
        return sandbox

    async def delete_sandbox(self, claim_name: str, namespace: str = "default") -> None:
        sandbox = self._sandboxes.pop((namespace, claim_name), None)
        self._warm_pools.pop((namespace, claim_name), None)
        if sandbox is not None:
            await sandbox.terminate()

    def drop_claim(self, claim_name: str, namespace: str = "default") -> None:
        """Simulate the claim disappearing underneath us (TTL expiry, node loss)."""
        self._sandboxes.pop((namespace, claim_name), None)
        self._warm_pools.pop((namespace, claim_name), None)


def _reject_relative(path: str, allow_unsafe_paths: bool) -> None:
    # The real client's sanitizer strips a leading "/", so an absolute workspace path
    # only survives with allow_unsafe_paths=True. Enforce that here so the provider
    # cannot silently regress to server-relative paths.
    if not allow_unsafe_paths and path.startswith("/"):
        raise ValueError(f"absolute path requires allow_unsafe_paths: {path}")
