# Python SDK Quickstart

Agent Sandbox is a quick and easy way to start secure containers that will let agents run, execute code , call tools and interact with data. Using the SDK users can easily interact with the sandboxes without using kubernetes primitives.




Install the SDK:

```bash
pip install k8s-agent-sandbox
```
Start with a simple run command:

```python
from k8s_agent_sandbox import SandboxClient

client = SandboxClient()

sandbox = client.create_sandbox(
    template="python-sandbox-template",
    namespace="default",
)
result = sandbox.commands.run("echo 'Hello from Agent Sandbox!'")
print(result.stdout)
# Hello from Agent Sandbox!
```

Or write a file into the sandbox filesystem, then read it:

```python
sandbox.files.write(
    "hello.py",
    'print("Hello, World! Greetings from inside the sandbox.")\n',
)

result = sandbox.commands.run("python3 hello.py")
print(result.stdout)
# Hello, World! Greetings from inside the sandbox.
```


## References

- [Python SDK documentation](../../clients/python/agentic-sandbox-client/) — full API reference and connection modes.
- [Using Agent Sandbox as a Tool in ADK](../code-interpreter-agent-on-adk/) — integrate sandboxes into an AI agent.