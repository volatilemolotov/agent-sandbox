---
title: "Documentation"
linkTitle: "Documentation"
weight: 20
menu:
  main:
    weight: 20
---

## What is Agent Sandbox?

**Agent Sandbox** is a Kubernetes-native platform for running isolated, stateful, singleton workloads — purpose-built for AI agent runtimes. Instead of wrestling with Deployments or StatefulSets that weren't designed for long-lived, single-container sessions, Agent Sandbox gives you a declarative `Sandbox` CRD that manages the full lifecycle of each workload: provisioning, stable networking, persistent storage, pausing, and cleanup.

## Get Started in Minutes

**Prerequisites:** A running Kubernetes cluster with the Agent Sandbox controller installed.

```bash
pip install k8s-agent-sandbox
```

```python
from k8s_agent_sandbox import SandboxClient
from k8s_agent_sandbox.models import SandboxLocalTunnelConnectionConfig

client = SandboxClient(
    connection_config=SandboxLocalTunnelConnectionConfig()
)

sandbox = client.create_sandbox(template="python-sandbox-template", namespace="default")
try:
    result = sandbox.commands.run("echo 'Hello from Agent Sandbox!'")
    print(result.stdout)
finally:
    sandbox.terminate()
```

Prefer Go? Install the Go client:

```bash
go get sigs.k8s.io/agent-sandbox/clients/go/sandbox
```

```go
client, err := sandbox.NewClient(ctx, sandbox.Options{})
if err != nil { log.Fatal(err) }
defer client.DeleteAll(ctx)

sb, err := client.CreateSandbox(ctx, "my-sandbox-template", "default")
if err != nil { log.Fatal(err) }

result, err := sb.Run(ctx, "echo 'Hello from Agent Sandbox!'")
fmt.Println(result.Stdout)
```

## Agent Sandbox building blocks

- **Sandbox** — The core CRD. A single stateful pod with a stable hostname, persistent storage, and a managed lifecycle.
- **SandboxTemplate** — A reusable blueprint that defines the container image, resources, and runtime configuration for a class of Sandboxes.
- **SandboxClaim** — A user-facing request to allocate a Sandbox from a template, abstracting away the underlying configuration details.
- **SandboxWarmPool** — A pre-warmed pool of Sandbox Pods held ready for instant allocation, eliminating cold-start latency at scale.

## How to use the docs

- **[Overview]({{< ref "docs/overview" >}})** — Architecture deep-dive, installation instructions, and the full feature set of the `Sandbox` CRD.
- **[Python Client]({{< ref "docs/python-client" >}})** — API reference and examples for the `k8s-agent-sandbox` Python SDK (Gateway, Tunnel, Direct, and Async modes).
- **[Runtime Templates]({{< ref "docs/runtime-templates" >}})** — Pre-built container image templates for common runtimes (Python, computer-use, and more).
- **[Examples]({{< ref "docs/examples" >}})** — End-to-end walkthroughs for real-world patterns: JupyterLab, LangChain, Chrome sandboxes, gVisor, VS Code, and more.
- **[Guides]({{< ref "docs/guides" >}})** — Operational topics including performance assessment, load testing, and controller tuning.
