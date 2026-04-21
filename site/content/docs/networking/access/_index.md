---
title: "Access"
linkTitle: "Access"
weight: 2
description: >
  How to connect to a running sandbox from your agent or application
---

## Prerequisites

- A running Kubernetes cluster with the [Agent Sandbox Controller]({{< ref "/docs/overview" >}}) installed.
- The [Sandbox Router](https://github.com/kubernetes-sigs/agent-sandbox/blob/main/clients/python/agentic-sandbox-client/sandbox-router/README.md) deployed in your cluster.
- A `SandboxTemplate` named `python-sandbox-template` applied to your cluster. See the [Python Runtime Sandbox]({{< ref "/docs/runtime-templates/python" >}}) guide for setup instructions.
- The [Python SDK]({{< ref "/docs/python-client" >}}) installed: `pip install k8s-agent-sandbox`.

All sandbox access flows through the [Sandbox Router](../#sandbox-router) --
a reverse proxy that routes requests to the correct sandbox pod using
`X-Sandbox-*` headers. The Python and Go client SDKs handle this automatically.

There are three connection modes, each suited to a different environment:

| Mode | When to use | How it connects |
|------|-------------|-----------------|
| **Gateway** | Production / cloud cluster | Client → Cloud load balancer → Router → Sandbox |
| **Local Tunnel** | Local development, Kind, Minikube | Client → `kubectl port-forward` → Router → Sandbox |
| **Direct** | In-cluster agents, custom domains | Client → provided URL → Router → Sandbox |

## Python client

### Gateway mode

Use when your cluster has a public Kubernetes
[Gateway](https://gateway-api.sigs.k8s.io/) IP. The client discovers the
address automatically.

```python
from k8s_agent_sandbox import SandboxClient
from k8s_agent_sandbox.models import SandboxGatewayConnectionConfig

client = SandboxClient(
    connection_config=SandboxGatewayConnectionConfig(
        gateway_name="external-http-gateway",
    )
)

sandbox = client.create_sandbox(template="python-sandbox-template", namespace="default")
try:
    print(sandbox.commands.run("echo 'Hello from Cloud!'").stdout)
finally:
    sandbox.terminate()
```

### Local tunnel mode

Use for local development. The client automatically opens a `kubectl port-forward`
tunnel to the Router Service -- no public IP needed.

```python
from k8s_agent_sandbox import SandboxClient
from k8s_agent_sandbox.models import SandboxLocalTunnelConnectionConfig

client = SandboxClient(
    connection_config=SandboxLocalTunnelConnectionConfig()
)

sandbox = client.create_sandbox(template="python-sandbox-template", namespace="default")
try:
    print(sandbox.commands.run("echo 'Hello from Local!'").stdout)
finally:
    sandbox.terminate()
```

### Direct mode

Use when your agent runs inside the cluster, or when connecting through a
custom domain.

```python
from k8s_agent_sandbox import SandboxClient
from k8s_agent_sandbox.models import SandboxDirectConnectionConfig

client = SandboxClient(
    connection_config=SandboxDirectConnectionConfig(
        api_url="http://sandbox-router-svc.default.svc.cluster.local:8080"
    )
)

sandbox = client.create_sandbox(template="python-sandbox-template", namespace="default")
try:
    sandbox.commands.run("ls -la")
finally:
    sandbox.terminate()
```

### Async client

For async applications (FastAPI, aiohttp, async agent orchestrators), install
the async extras and use `AsyncSandboxClient`. Local Tunnel mode is not
supported in async -- use Direct or Gateway instead.

```bash
pip install "k8s-agent-sandbox[async]"
```

```python
import asyncio
from k8s_agent_sandbox import AsyncSandboxClient
from k8s_agent_sandbox.models import SandboxDirectConnectionConfig

async def main():
    config = SandboxDirectConnectionConfig(
        api_url="http://sandbox-router-svc.default.svc.cluster.local:8080"
    )
    async with AsyncSandboxClient(connection_config=config) as client:
        sandbox = await client.create_sandbox(
            template="python-sandbox-template",
            namespace="default",
        )
        result = await sandbox.commands.run("echo 'Hello from async!'")
        print(result.stdout)

asyncio.run(main())
```

### Custom port

If your sandbox runtime listens on a port other than `8888`, set `server_port`:

```python
client = SandboxClient(
    connection_config=SandboxLocalTunnelConnectionConfig(server_port=3000)
)
```

## Raw HTTP

If you are not using a client SDK, send requests directly to the Router with
the three routing headers:

```bash
curl http://<gateway-ip>/your/path \
  -H "X-Sandbox-ID: my-sandbox" \
  -H "X-Sandbox-Namespace: default" \
  -H "X-Sandbox-Port: 8888"
```

The router forwards the request to
`my-sandbox.default.svc.cluster.local:8888/your/path` and streams the
response back.
