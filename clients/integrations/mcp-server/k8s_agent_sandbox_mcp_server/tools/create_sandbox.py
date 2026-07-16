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

from pydantic import (
    BaseModel,
    Field,
)

from fastmcp import Context
from ..settings import Settings


class CreateSandboxOutputSchema(BaseModel):
    sandbox_claim_name: str = Field(description="Name of a created sandbox claim.")

async def create_sandbox(
    ctx: Context,
    warmpool: str,
    namespace: str,
    sandbox_ready_timeout: int = 180,
    labels: dict[str, str] | None = None,
    shutdown_after_seconds: int | None = None,
    pod_labels: dict[str, str] | None = None,
    pod_annotations: dict[str, str] | None = None,
) -> CreateSandboxOutputSchema:
    """Create a new sandbox.

    Args:
        warmpool: The name of the warmpool to use.
        namespace: The Kubernetes namespace to create the sandbox in.
        sandbox_ready_timeout: Timeout in seconds to wait for the sandbox to be ready.
        labels: Additional labels for the sandbox.
        shutdown_after_seconds: Time in seconds after which the sandbox automatically shuts down.
        pod_labels: Additional labels for the pod.
        pod_annotations: Additional annotations for the pod.
    """

    client = ctx.lifespan_context["client"]
    settings: Settings = ctx.lifespan_context["settings"]

    labels = labels or {}

    labels[settings.session_id_label_key] = ctx.session_id

    sandbox = await client.create_sandbox(
        warmpool,
        namespace=namespace,
        sandbox_ready_timeout=sandbox_ready_timeout,
        labels=labels,
        shutdown_after_seconds=shutdown_after_seconds,
        pod_labels=pod_labels,
        pod_annotations=pod_annotations,
    )

    return CreateSandboxOutputSchema(sandbox_claim_name=sandbox.claim_name)

