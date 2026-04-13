---
title: "Agent Sandbox Custom Docker Image"
linkTitle: "Agent Sandbox Custom Docker Image"
weight: 15
description: >
  Create a Sandbox with custom dependencies.
---
## Architecture

The Agent Sandbox architecture separates the **Template** (the definition) from the **Claim** (your Python request) for a very specific reason: **speed**.
When a user applies a `SandboxTemplate` to a Kubernetes cluster, the controller typically spins up a `SandboxWarmPool`. These are pre-initialized, running pods that have already pulled your specific Docker image. When a `Python` script calls `client.create_sandbox("sandbox-template")`, it instantly grabs one of these pre-warmed pods.

## Workarounds

### 1. Install dependencies via sandbox.commands.run() function

```python
from k8s_agent_sandbox import SandboxClient
client = SandboxClient()
sandbox = client.create_sandbox("python-base-template")
# Dynamically install a package before running your main logic
sandbox.commands.run("pip install custom-package==1.0.0")
response = sandbox.commands.run("python -c 'import custom_package; print(\"Success!\")'")
```

### \[NOT FOR PUBLISHING\] 2. Use `kubernetes` Python SDK to create a new SandboxTemplate instance

We can create a Python script that uses `kubernetes` SDK to deploy a custom template, or update an existing template with our custom Docker image.
