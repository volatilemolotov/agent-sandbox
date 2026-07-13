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

from ..settings import Settings
from fastmcp.resources import resource
from fastmcp.resources import ResourceResult, ResourceContent


@resource("sandboxes://{namespace}")
async def get_sandboxes(
    ctx: Context,
    namespace: str,
) -> ResourceResult:
    """
    Get all active sandboxes in the given namespace.
    """

    client = ctx.lifespan_context["client"]
    settings: Settings = ctx.lifespan_context["settings"]

    label_selector = f"{settings.session_id_label_key}={ctx.session_id}"

    found = await client.list_all_sandboxes(
        namespace=namespace, 
        label_selector=label_selector,
    )
    return ResourceResult(
        contents=[ResourceContent(content=cn) for cn in found]
    )
