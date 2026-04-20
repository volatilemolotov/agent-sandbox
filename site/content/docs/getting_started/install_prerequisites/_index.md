---
title: "Agent Sandbox in KinD cluster"
linkTitle: "Agent Sandbox in KinD"
weight: 2
description: >
  This guide shows how to create a [Kubernetes in Docker (KinD)](https://kind.sigs.k8s.io/) cluster to install Agent Sandbox.
---

# Prerequisites

* [docker](https://docs.docker.com/engine/install/) or [podman](https://podman.io/docs/installation) installed.
* [kind](https://kubernetes.io/docs/tasks/tools/#kind) CLI tool.
* [kubectl](https://kubernetes.io/docs/tasks/tools/#kubectl) CLI tool.


1. Run command to create a cluster in KinD:
   ```sh
   kind create cluster --name agent-sandbox-test
   ```

2. Install the agent-sandbox controller and its CRDs with the following command:
   ```sh
   # Replace "vX.Y.Z" with a specific version tag (e.g., "v0.1.0") from
   # https://github.com/kubernetes-sigs/agent-sandbox/releases
   export VERSION="vX.Y.Z"
   
   # To install only the core components:
   kubectl apply -f https://github.com/kubernetes-sigs/agent-sandbox/releases/download/${VERSION}/manifest.yaml
   
   # To install the extensions components:
   kubectl apply -f https://github.com/kubernetes-sigs/agent-sandbox/releases/download/${VERSION}/extensions.yaml
   ```

3. Before using the client, you must deploy the `sandbox-router`. Follow these [instructions](https://github.com/kubernetes-sigs/agent-sandbox/blob/main/clients/python/agentic-sandbox-client/sandbox-router/README.md).

4. Create a Sandbox Template. For example the [python-runtime-sandbox](https://github.com/kubernetes-sigs/agent-sandbox/blob/main/examples/python-runtime-sandbox/).
    ```bash
    kubectl apply -f python-sandbox-template.yaml
    ```








