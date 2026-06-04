# Copyright 2025 The Kubernetes Authors.
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

"""
n8n → Agent Sandbox Bridge

Exposes a simple HTTP API that n8n calls to execute code inside an isolated
Kubernetes sandbox pod. One request = one ephemeral sandbox: claim, run, release.
"""

import logging
import os

from fastapi import FastAPI, HTTPException
from k8s_agent_sandbox import SandboxClient
from k8s_agent_sandbox.models import SandboxInClusterConnectionConfig
from pydantic import BaseModel

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(title="n8n Agent Sandbox Bridge", version="1.0.0")

WARMPOOL_NAME = os.environ.get("WARMPOOL_NAME", "n8n-sandbox-warmpool")
SANDBOX_NAMESPACE = os.environ.get("SANDBOX_NAMESPACE", "n8n-demo")


class ExecuteRequest(BaseModel):
    # Shell command to run directly, e.g. "echo hello"
    command: str | None = None
    # Multi-line Python source; written to /app/run.py then executed
    script: str | None = None


class ExecuteResponse(BaseModel):
    stdout: str
    stderr: str
    exit_code: int


@app.get("/healthz", summary="Liveness / readiness probe")
def healthz():
    return {"status": "ok"}


@app.post("/execute", response_model=ExecuteResponse, summary="Run code in a sandbox")
def execute(req: ExecuteRequest):
    """
    Claim a pre-warmed sandbox, execute the given command or Python script,
    return stdout/stderr/exit_code, then release the sandbox.
    """
    if not req.command and not req.script:
        raise HTTPException(
            status_code=400,
            detail="Provide either 'command' (shell string) or 'script' (Python source).",
        )

    # SandboxInClusterConnectionConfig connects directly to each sandbox pod via
    # cluster-internal DNS: http://{sandbox-id}.{namespace}.svc.cluster.local:8888
    # No router sidecar needed.
    client = SandboxClient(
        connection_config=SandboxInClusterConnectionConfig()
    )

    logger.info(
        "Claiming sandbox from warmpool=%s namespace=%s", WARMPOOL_NAME, SANDBOX_NAMESPACE
    )
    sandbox = client.create_sandbox(warmpool=WARMPOOL_NAME, namespace=SANDBOX_NAMESPACE)
    logger.info("Sandbox %s ready", sandbox.id)

    try:
        if req.script:
            # Write the Python source into the sandbox filesystem, then run it.
            sandbox.files.write("run.py", req.script.encode())
            result = sandbox.commands.run("python3 /app/run.py")
        else:
            result = sandbox.commands.run(req.command)

        logger.info(
            "Sandbox %s exited with code %d", sandbox.id, result.exit_code
        )
        return ExecuteResponse(
            stdout=result.stdout,
            stderr=result.stderr,
            exit_code=result.exit_code,
        )
    finally:
        sandbox.terminate()
        logger.info("Sandbox %s released", sandbox.id)
