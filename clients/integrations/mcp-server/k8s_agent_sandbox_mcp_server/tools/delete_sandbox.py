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

from fastmcp import Context


async def delete_sandbox(
    ctx: Context,
    sandbox_claim_name: str,
    namespace: str,
):
    """
    Delete a target sandbox.

    Args:
        sandbox_claim_name: Name of a target sandbox claim.
        namespace: Kubernetes namespace for the target sandbox claim.
    """
    client = ctx.lifespan_context["client"]

    await client.delete_sandbox(sandbox_claim_name, namespace=namespace)
