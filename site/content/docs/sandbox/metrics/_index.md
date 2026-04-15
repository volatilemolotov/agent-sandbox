---
title: "Metrics"
linkTitle: "Metrics"
weight: 15
description: >
  Create a Sandbox and check its metrics.
---
## Local Observability and Telemetry Gathering

When building agentic workflows, you often need to inspect the latency, execution times, and network spans of your sandbox interactions. The `k8s_agent_sandbox` SDK integrates seamlessly with OpenTelemetry (OTel). 

Using OpenTelemetry's auto-instrumentation tools, you can surface rich metric and trace data directly in your local console for rapid debugging, all without writing any custom telemetry code or setting up external observability backends.

### Prerequisites

This guide assumes you have already configured your Kubernetes cluster with the Agent Sandbox controllers.

- Ensure your local environment has the SDK installed with tracing extras, alongside the OpenTelemetry CLI tools: `pip install "k8s-agent-sandbox[tracing]" opentelemetry-distro`.
- You have applied a basic SandboxTemplate (e.g., `simple-sandbox-template`) to your cluster.

### 1. The Client Execution Workflow

The client code remains completely standard. Because we will be using OpenTelemetry's CLI wrapper to inject the instrumentation at runtime, your Python script does not need any OTel-specific imports or bootstrapping logic. 

Save the following standard execution logic to a file named `main.py`.

```python
from k8s_agent_sandbox import SandboxClient

# 1. Initialize the client
client = SandboxClient()

# 2. Create the sandbox using your template
sandbox = client.create_sandbox("simple-sandbox-template")

# 3. Define and run a standard command
payload = "echo 'Hello World!'"
response = sandbox.commands.run(payload)

# 4. Print the execution response
print(response)
```

### 2. Bootstrapping and Execution

To actually generate and view the telemetry data, you must instruct OpenTelemetry on *where* to send the data and tell Python to load the tracing libraries. 

By setting the exporter environment variables to `console`, the data will be printed directly to your standard output. Wrapping your standard `python main.py` command with `opentelemetry-instrument` automatically bootstraps the tracing SDK.

Run the following commands in your terminal:

```bash
# 1. Route traces and metrics to the local terminal
export OTEL_TRACES_EXPORTER="console"
export OTEL_METRICS_EXPORTER="console"

# 2. Execute the script using the OTel auto-instrumentation wrapper
opentelemetry-instrument python main.py
```

### Expected Output

When you run the command above, you will see your standard application logs (e.g., creating the claim, starting the tunnel) alongside a large payload of JSON-formatted telemetry data. 

This output will include `resource_metrics` tracking the internal latency of the client, as well as `Span` objects detailing the precise duration of the HTTP requests made to the sandbox pod.
