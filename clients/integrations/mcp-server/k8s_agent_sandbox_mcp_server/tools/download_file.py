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

import base64

from pydantic import (
    BaseModel,
    Field,
)
from fastmcp import Context


class DownloadFileOutputSchema(BaseModel):
    content: str = Field(description="The content of a file.")
    bytes_read: int = Field(description="Bytes read from a file.")


async def download_file(
    ctx: Context,
    sandbox_claim_name: str,
    namespace: str,
    path: str,
    binary: bool = False,
    timeout: int = 60,
) -> DownloadFileOutputSchema:
    """
    Download a file from a sandbox.

    Args:
        sandbox_claim_name: Name of a target sandbox claim.
        namespace: Kubernetes namespace with a target sandbox.
        path: The target upload path.
        binary: When True, the content of a file is returned as a base64-encoded binary blob.
        timeout: Time is seconds to download the file until the timeout.
    """
    client = ctx.lifespan_context["client"]

    sandbox = await client.get_sandbox(sandbox_claim_name, namespace=namespace)

    try:
        content = await sandbox.files.read(path, timeout=timeout)
    except Exception as e:
        raise RuntimeError(f"Failed to read file from sandbox: {e}") from e

    try:
        if binary:
            final_content = base64.b64encode(content).decode("ascii")
        else:
            final_content = content.decode("utf-8")
    except Exception as e:
        raise ValueError(f"Failed to decode file content: {e}") from e

    return DownloadFileOutputSchema(
        content=final_content,
        bytes_read=len(content),
    )

