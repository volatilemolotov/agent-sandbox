# Agent Sandbox with WarmPool and Python SDK on KIND

## Overview

This guide demonstrates how to set up and use Agent Sandbox on a local KIND (Kubernetes IN Docker) cluster with the following features:

- **Sandbox**: Core isolated environment for running untrusted code
- **SandboxTemplate**: Reusable blueprint for sandbox configurations
- **SandboxClaim**: Declarative API for requesting sandboxes
- **SandboxWarmPool**: Pre-warmed sandbox pool for sub-second startup times
- **Python SDK**: Programmatic sandbox management
- **gVisor Runtime**: Enhanced security isolation layer

## Prerequisites

Install the following tools on your local machine:

- Docker (20.10+)
- kubectl (1.28+)
- KIND (0.20+)
- Python 3.9+
- Git

## Step 1: Create KIND Cluster with gVisor Support

### 1.1 Install gVisor Runtime

First, install the gVisor runsc runtime on your host machine:

```bash
# Download and install runsc
(
  set -e
  ARCH=$(uname -m)
  URL=https://storage.googleapis.com/gvisor/releases/release/latest/${ARCH}
  wget ${URL}/runsc ${URL}/runsc.sha512 \
    ${URL}/containerd-shim-runsc-v1 ${URL}/containerd-shim-runsc-v1.sha512
  sha512sum -c runsc.sha512 \
    -c containerd-shim-runsc-v1.sha512
  rm -f *.sha512
  chmod a+rx runsc containerd-shim-runsc-v1
  sudo mv runsc containerd-shim-runsc-v1 /usr/local/bin
)
```

### 1.2 Create KIND Cluster Configuration

Create a KIND cluster configuration file that enables gVisor:

```bash
cat <<EOF > kind-config.yaml
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
nodes:
- role: control-plane
  extraMounts:
  - hostPath: /usr/local/bin/runsc
    containerPath: /usr/local/bin/runsc
  - hostPath: /usr/local/bin/containerd-shim-runsc-v1
    containerPath: /usr/local/bin/containerd-shim-runsc-v1
EOF
```

### 1.3 Create the Cluster

```bash
kind create cluster --name agent-sandbox-demo --config kind-config.yaml
```

### 1.4 Configure Containerd for gVisor

Configure the KIND cluster's containerd to support the gVisor runtime:

```bash
docker exec -it agent-sandbox-demo-control-plane bash -c 'cat <<EOF > /etc/containerd/config.toml
version = 2
[plugins."io.containerd.grpc.v1.cri".containerd.runtimes.runc]
  runtime_type = "io.containerd.runc.v2"
[plugins."io.containerd.grpc.v1.cri".containerd.runtimes.runsc]
  runtime_type = "io.containerd.runsc.v1"
EOF'

# Restart containerd
docker exec -it agent-sandbox-demo-control-plane systemctl restart containerd

# Wait for cluster to stabilize
kubectl wait --for=condition=Ready nodes --all --timeout=60s
```

### 1.5 Create RuntimeClass for gVisor

```bash
kubectl apply -f - <<EOF
apiVersion: node.k8s.io/v1
kind: RuntimeClass
metadata:
  name: gvisor
handler: runsc
EOF
```

## Step 2: Install Agent Sandbox Controller

### 2.1 Install Core Components

```bash
export AGENT_SANDBOX_VERSION="v0.1.0"

kubectl apply -f https://github.com/kubernetes-sigs/agent-sandbox/releases/download/${AGENT_SANDBOX_VERSION}/manifest.yaml
```

### 2.2 Install Extensions (SandboxTemplate, SandboxClaim, SandboxWarmPool)

```bash
kubectl apply -f https://github.com/kubernetes-sigs/agent-sandbox/releases/download/${AGENT_SANDBOX_VERSION}/extensions.yaml
```

### 2.3 Verify Installation

```bash
# Check that the controller is running
kubectl get pods -n agent-sandbox-system

# Wait for the controller to be ready
kubectl wait --for=condition=Ready pod -l app=agent-sandbox-controller -n agent-sandbox-system --timeout=120s
```

Expected output:
```
NAME                          READY   STATUS    RESTARTS   AGE
agent-sandbox-controller-0    1/1     Running   0          30s
```

## Step 3: Build and Load Python Runtime Sandbox Image

### 3.1 Clone the Agent Sandbox Repository

```bash
git clone https://github.com/kubernetes-sigs/agent-sandbox.git
cd agent-sandbox/examples/python-runtime-sandbox
```

### 3.2 Build the Sandbox Image

```bash
docker build -t python-runtime-sandbox:latest .
```

### 3.3 Load Image into KIND Cluster

```bash
kind load docker-image python-runtime-sandbox:latest --name agent-sandbox-demo
```

## Step 4: Create SandboxTemplate with gVisor

Create a SandboxTemplate that defines the sandbox blueprint with gVisor runtime:

```bash
kubectl apply -f - <<EOF
apiVersion: extensions.agents.x-k8s.io/v1alpha1
kind: SandboxTemplate
metadata:
  name: python-runtime-template
  namespace: default
spec:
  podTemplate:
    metadata:
      labels:
        sandbox: python-sandbox
    spec:
      runtimeClassName: gvisor  # Enable gVisor isolation
      containers:
      - name: python-runtime
        image: python-runtime-sandbox:latest
        imagePullPolicy: IfNotPresent
        ports:
        - containerPort: 8888
          protocol: TCP
        readinessProbe:
          httpGet:
            path: /
            port: 8888
          initialDelaySeconds: 2
          periodSeconds: 1
        resources:
          requests:
            cpu: "250m"
            memory: "512Mi"
            ephemeral-storage: "512Mi"
          limits:
            cpu: "500m"
            memory: "1Gi"
            ephemeral-storage: "1Gi"
      restartPolicy: OnFailure
EOF
```

### Verify SandboxTemplate

```bash
kubectl get sandboxtemplate
```

Expected output:
```
NAME                       AGE
python-runtime-template    5s
```

## Step 5: Configure SandboxWarmPool

Create a SandboxWarmPool to maintain pre-warmed pod instances for fast sandbox allocation:

```bash
kubectl apply -f - <<EOF
apiVersion: extensions.agents.x-k8s.io/v1alpha1
kind: SandboxWarmPool
metadata:
  name: python-warmpool
  namespace: default
spec:
  replicas: 2
  sandboxTemplateRef:
    name: python-runtime-template
EOF
```

### Verify WarmPool Creation

```bash
# Check WarmPool status
kubectl get sandboxwarmpool python-warmpool

# Check pre-warmed PODS (not Sandboxes - WarmPool creates pods directly)
kubectl get pods -l agents.x-k8s.io/pool

# Wait for pods to be ready
kubectl wait --for=condition=Ready pod -l agents.x-k8s.io/pool --timeout=60s
```

Expected output:
```
NAME                      READY   STATUS    RESTARTS   AGE
python-warmpool-xxxxx     1/1     Running   0          15s
python-warmpool-yyyyy     1/1     Running   0          15s
```

### Understanding How WarmPool Works

**Key Concepts:**

1. **WarmPool creates Pods, not Sandboxes**: The WarmPool pre-creates actual Pod resources that are ready to run, not Sandbox CRD resources.

2. **Instant claiming**: When you create a SandboxClaim, the controller:
   - Finds an available pre-warmed pod from the pool
   - Converts it into a Sandbox resource
   - Adds the annotation `agents.x-k8s.io/pod-name: <pod-name>` to track which pod was used
   - The entire process takes <1 second (vs. 10-30 seconds for cold start)

3. **Automatic replenishment**: After a pod is claimed, the WarmPool controller automatically creates a new pod to maintain the desired replica count.

4. **Pool identification**: Pods in the warm pool are labeled with:
   - `agents.x-k8s.io/pool=<pool-hash>` (e.g., `99619c39`)
   - `agents.x-k8s.io/sandbox-template-ref-hash=<template-hash>`
   
   When a pod is claimed, its labels change to:
   - `agents.x-k8s.io/sandbox-name-hash=<sandbox-hash>` (pool label is removed)

### Test WarmPool Performance

Create a SandboxClaim to see the WarmPool in action:

```bash
kubectl apply -f - <<EOF
apiVersion: extensions.agents.x-k8s.io/v1alpha1
kind: SandboxClaim
metadata:
  name: warmpool-test
  namespace: default
spec:
  sandboxTemplateRef:
    name: python-runtime-template
EOF
```

Observe the fast allocation:

```bash
# This should complete in <1 second
time kubectl wait --for=condition=Ready sandbox/warmpool-test --timeout=10s

# Verify which warm pod was used
kubectl get sandbox warmpool-test -o jsonpath='{.metadata.annotations.agents\.x-k8s\.io/pod-name}'

# Check that WarmPool is creating a replacement pod
kubectl get pods -l agents.x-k8s.io/pool
```

Expected behavior:
```
# Sandbox ready in <1 second
sandbox.agents.x-k8s.io/warmpool-test condition met

real    0m0.234s
user    0m0.045s
sys     0m0.012s

# Shows which pre-warmed pod was claimed
python-warmpool-xxxxx

# WarmPool creates new pod to replace the claimed one
NAME                      READY   STATUS    RESTARTS   AGE
python-warmpool-yyyyy     1/1     Running   0          2m
python-warmpool-zzzzz     1/1     Running   0          5s
```