# Python SDK Quickstart

This guide walks you through creating and interacting with an Agent Sandbox using the Python SDK.
By the end you will have created a sandbox, executed shell commands, and performed file operations.

## Prerequisites

Before starting, make sure the following infrastructure is in place:

1.  A running **Kubernetes cluster** with the [Agent Sandbox Controller](../../README.md#installation) installed.
2.  **kubectl** installed and configured to talk to your cluster.
3.  The [Sandbox Router](../../clients/python/agentic-sandbox-client/) deployed to the cluster.
4.  A [SandboxTemplate](../../clients/python/agentic-sandbox-client/) applied. This guide uses `python-sandbox-template`.

## Installation

1.  Create a Python virtual environment:

    ```bash
    python3 -m venv .venv
    source .venv/bin/activate
    ```

2.  Install the SDK:

    ```bash
    pip install k8s-agent-sandbox
    ```

## Step 1: Create a Client

Import the SDK and create a `SandboxClient`. By default it connects to the
cluster through your local `kubectl` configuration:

```python
from k8s_agent_sandbox import SandboxClient

client = SandboxClient()
```

## Step 2: Create a Sandbox

Spin up a sandbox from the template you applied in the prerequisites:

```python
sandbox = client.create_sandbox(
    template="python-sandbox-template",
    namespace="default",
)
```

The SDK sends a request to the controller, which provisions a pod on the cluster.
Once the call returns, the sandbox is ready to use.

## Step 3: Run a Command

Execute a shell command inside the sandbox and print the output:

```python
result = sandbox.commands.run("echo 'Hello from Agent Sandbox!'")
print(result.stdout)
# Hello from Agent Sandbox!
```

## Step 4: Write and Execute a File

Write a Python file into the sandbox filesystem, then run it:

```python
sandbox.files.write(
    "hello.py",
    'print("Hello, World! Greetings from inside the sandbox.")\n',
)

result = sandbox.commands.run("python3 hello.py")
print(result.stdout)
# Hello, World! Greetings from inside the sandbox.
```

## Step 5: Read a File

Read the file back from the sandbox:

```python
content = sandbox.files.read("hello.py")
print(content)
# print("Hello, World! Greetings from inside the sandbox.")
```

## Step 6: Terminate the Sandbox

When you are done, terminate the sandbox to free cluster resources:

```python
sandbox.terminate()
```

> **Note:** Always terminate sandboxes when you are finished. You can also use `client.delete_all()`
> to clean up every sandbox the client has created in the current session.

## Putting It All Together

Here is the complete script combining all the steps above:

```python
from k8s_agent_sandbox import SandboxClient

client = SandboxClient()

sandbox = client.create_sandbox(
    template="python-sandbox-template",
    namespace="default",
)

try:
    result = sandbox.commands.run("echo 'Hello from Agent Sandbox!'")
    print("Command output:", result.stdout)

    sandbox.files.write(
        "hello.py",
        'print("Hello, World! Greetings from inside the sandbox.")\n',
    )

    result = sandbox.commands.run("python3 hello.py")
    print("Script output:", result.stdout)

    content = sandbox.files.read("hello.py")
    print("File content:", content)

finally:
    sandbox.terminate()
    print("Sandbox terminated.")
```

## Cleanup

To verify that no sandbox resources remain on the cluster:

```bash
kubectl get sandboxes -n default
```

## References

- [Python SDK documentation](../../clients/python/agentic-sandbox-client/) — full API reference and connection modes.
- [Using Agent Sandbox as a Tool in ADK](../code-interpreter-agent-on-adk/) — integrate sandboxes into an AI agent.
