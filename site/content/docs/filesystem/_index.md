---
title: "Filesystem"
linkTitle: "Filesystem"
weight: 15
description: >
  Read, write, list, and transfer files inside sandboxes using the Python SDK.
---

The Agent Sandbox Python SDK (`k8s-agent-sandbox`) provides a `files` API on every sandbox instance for interacting with the sandbox filesystem. You can read and write files, list directories, check if paths exist, and upload or download data — all through the SDK without needing `kubectl exec`.

All file operations are also available as async methods via `AsyncSandboxClient`.

## Connect to a sandbox

```python
from k8s_agent_sandbox import SandboxClient

client = SandboxClient()
sandbox = client.create_sandbox(template="python-sandbox-template", namespace="default")
```

## Write a file

```python
sandbox.files.write("/home/user/hello.txt", "Hello from the SDK!")
```

## Read a file

```python
content = sandbox.files.read("/home/user/hello.txt")
print(content.decode())  # 'Hello from the SDK!'
```

## List directory contents

```python
entries = sandbox.files.list("/home/user")
for entry in entries:
    print(f"{entry.name} ({entry.type}, {entry.size} bytes)")
```

## Check if a path exists

```python
if sandbox.files.exists("/home/user/hello.txt"):
    print("File exists!")
```

## Clean up

```python
sandbox.terminate()
```
