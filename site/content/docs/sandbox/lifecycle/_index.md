---
title: "Agent Sandbox Shutdown Time"
linkTitle: "Agent Sandbox Shutdown Time"
weight: 2
description: >
  Set up a specific time when the Sandbox must be deleted.
---
{{% include-file file="additional/examples/analytics-tool/README.md" %}}

## Sandbox Expiration

In many agentic workflows, you don't need a sandbox running indefinitely. To prevent resource leaks, runaway tasks, or unbounded compute costs, you need a way to ensure that a session is automatically terminated after a specific deadline.

While standard sandboxes run until manually deleted, configuring a `shutdownTime` allows you to schedule an exact expiration timestamp. Once this timestamp is reached, the sandbox and its associated resources are automatically garbage-collected by the control plane.

### Prerequisites

This guide assumes you have a running Kubernetes cluster. Because we are leveraging standard Kubernetes manifests and `kubectl`, this workflow is natively supported across both **macOS** and **Linux** environments (such as a local KinD cluster, Minikube, or Docker Desktop).

- A running Kubernetes cluster.
- The `kubectl` CLI tool installed and configured to point to your cluster.
- The [Agent Sandbox Controller](https://github.com/kubernetes-sigs/agent-sandbox?tab=readme-ov-file#installation) installed.

### Scheduled Shutdown

Unlike manual termination, setting a `shutdownTime` provides a guaranteed, hard deadline for the sandbox's lifecycle. This is ideal for ephemeral CI/CD test runs, untrusted code execution with strict timeouts, or simple cost-control mechanisms.

#### Basic Workflow Example with kubectl

The following example demonstrates how to define a sandbox claim with an explicit `shutdownTime`, apply it directly to your cluster using `kubectl`, and verify the scheduled cleanup.

Define the shutdown time (in this example it's the current time plus 1 minute):

```bash
SHUTDOWN_TIME=$(date -u -v+1M +%Y-%m-%dT%H:%M:%SZ)
```

Apply an example sandbox with the `shutdownPolicy` and `shutdownTime`:

```bash
cat <<EOF | kubectl apply -f -
apiVersion: agents.x-k8s.io/v1alpha1
kind: Sandbox
metadata:
  name: dynamic-ephemeral-sandbox
spec:
  replicas: 1
  shutdownPolicy: Delete
  shutdownTime: "${SHUTDOWN_TIME}"
  podTemplate:
    spec:
      containers:
      - name: workspace
        image: alpine:latest
        command: ["sleep", "infinity"]
EOF
```

Verify that the sandbox is deleted:

```bash
kubectl get sandboxclaim dynamic-ephemeral-sandbox
sleep 60
kubectl get sandboxclaim dynamic-ephemeral-sandbox
```

#### Basic Workflow Example with Python SDK

Using `k8s_agent_sandbox` SDK you can specify the following attributes:
- `sandbox_ready_timeout`: Seconds to wait for the sandbox to be ready. 
- `shutdown_after_seconds`: Optional TTL in seconds. When set, the claim's `spec.lifecycle` is populated with a `shutdownTime` of *now + shutdown_after_seconds* (UTC) and a `shutdownPolicy` of `"Delete"`, so the controller auto-deletes the claim on expiry. Must be a positive integer.

```python
from k8s_agent_sandbox import SandboxClient

client = SandboxClient()
sandbox = client.create_sandbox("simple-sandbox-template", sandbox_ready_timeout=5, shutdown_after_seconds=10)
payload = "echo 'Hello World!'"
response = sandbox.commands.run(payload)

print(response)
```
