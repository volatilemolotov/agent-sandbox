---
title: "Fine-Grained Network Control"
linkTitle: "Fine-Grained Network Control"
weight: 1
description: >
  Control sandbox ingress and egress traffic with Kubernetes NetworkPolicy
---

Agent Sandbox uses Kubernetes
[NetworkPolicy](https://kubernetes.io/docs/concepts/services-networking/network-policies/)
resources for fine-grained ingress and egress control. A single shared
NetworkPolicy is created **per `SandboxTemplate`**. Any update to a template's
network rules is enforced across **all existing and future sandboxes** created
from that template, instantly via the underlying CNI.

## Secure-by-default policy

When `spec.networkPolicy` is **omitted** (and management is `Managed`), the
controller applies a strict default policy:

### Ingress

| Source | Action |
|--------|--------|
| Sandbox Router (`app: sandbox-router`) | Allow |
| Everything else | Deny |

Only the Sandbox Router can reach sandbox pods. All other pod-to-pod ingress is
blocked.

### Egress

| Destination | Action |
|-------------|--------|
| Public internet (`0.0.0.0/0`, `::/0`) | Allow |
| `10.0.0.0/8` (private Class A) | Block |
| `172.16.0.0/12` (private Class B) | Block |
| `192.168.0.0/16` (private Class C) | Block |
| `169.254.0.0/16` (link-local / metadata server) | Block |
| `fc00::/7` (IPv6 ULA) | Block |

Sandboxes **can** call external APIs, pull packages, and reach public services.
They **cannot** reach internal cluster services, the cloud metadata endpoint, or
other pods on the private network.

### DNS

Internal CoreDNS typically runs on a private IP (in `10.0.0.0/8`), so it is
blocked by the default egress rules. To ensure sandboxes can still resolve
public domains, the controller automatically configures:

- `dnsPolicy: None` on the sandbox pod
- Public nameservers: `8.8.8.8` (Google) and `1.1.1.1` (Cloudflare)

This prevents agents from enumerating internal service names via DNS while still
allowing normal public domain resolution.

> **Note:** The automatic DNS override only applies in secure-by-default mode.
> Custom policies and Unmanaged mode leave DNS untouched for compatibility with
> air-gapped or proxy environments.

## Custom network policies

To define your own rules, set `spec.networkPolicy` on the `SandboxTemplate`:

```yaml
apiVersion: extensions.agents.x-k8s.io/v1alpha1
kind: SandboxTemplate
metadata:
  name: my-template
spec:
  networkPolicyManagement: Managed   # default
  networkPolicy:
    ingress:
      - from:
          - podSelector:
              matchLabels:
                app: sandbox-router
          - podSelector:
              matchLabels:
                app: my-monitoring-agent
    egress:
      - to:
          - ipBlock:
              cidr: 0.0.0.0/0
              except:
                - 10.0.0.0/8
                - 172.16.0.0/12
                - 192.168.0.0/16
                - 169.254.0.0/16
      - to:
          - ipBlock:
              cidr: 10.96.5.10/32   # allow a specific internal service
        ports:
          - protocol: TCP
            port: 443
  podTemplate:
    spec:
      containers:
        - name: sandbox
          image: my-image:latest
```

When custom rules are provided, the controller uses them as-is. You have full
control over `ingress` and `egress` rules. The `podSelector` and `policyTypes`
fields are managed by the controller and cannot be overridden -- this ensures
the policy always targets the correct pods and enforces both ingress and egress.

> **Warning:** The policy enforces a strict **Default Deny** ingress posture.
> If your pod uses sidecars (e.g. Istio proxy, monitoring agents) that listen
> on their own ports, the NetworkPolicy will **block** traffic to them. You must
> explicitly allow traffic to sidecar ports in `ingress`, otherwise sidecars may
> fail health checks.

## Unmanaged mode

If you want to manage networking entirely outside Agent Sandbox -- for example
using [Cilium](https://cilium.io/) network policies or a service mesh -- set
`networkPolicyManagement` to `Unmanaged`:

```yaml
apiVersion: extensions.agents.x-k8s.io/v1alpha1
kind: SandboxTemplate
metadata:
  name: cilium-managed
spec:
  networkPolicyManagement: Unmanaged
  podTemplate:
    spec:
      containers:
        - name: sandbox
          image: my-image:latest
```

In this mode the controller:

- **Skips** all NetworkPolicy creation
- **Deletes** any previously managed policy for this template
- **Does not** override DNS settings

This gives your external networking tool full control.

## API reference

The networking configuration lives in `SandboxTemplateSpec`:

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `networkPolicyManagement` | `Managed` \| `Unmanaged` | `Managed` | Whether the controller manages the NetworkPolicy |
| `networkPolicy` | object | `nil` (secure default) | Custom ingress/egress rules |
| `networkPolicy.ingress` | `[]NetworkPolicyIngressRule` | -- | List of allowed ingress sources |
| `networkPolicy.egress` | `[]NetworkPolicyEgressRule` | -- | List of allowed egress destinations |

## Examples

### Allow only specific external APIs

Restrict egress to a known set of public CIDR ranges:

```yaml
networkPolicy:
  ingress:
    - from:
        - podSelector:
            matchLabels:
              app: sandbox-router
  egress:
    - to:
        - ipBlock:
            cidr: 104.18.0.0/16    # Example: API provider range
      ports:
        - protocol: TCP
          port: 443
```

### Allow a local LLM endpoint

Use `hostAliases` to route traffic to an internal LLM (e.g. Ollama) without
opening DNS holes:

```yaml
apiVersion: extensions.agents.x-k8s.io/v1alpha1
kind: SandboxTemplate
metadata:
  name: local-llm
spec:
  networkPolicy:
    ingress:
      - from:
          - podSelector:
              matchLabels:
                app: sandbox-router
    egress:
      - to:
          - ipBlock:
              cidr: 10.96.5.10/32   # Internal LLM service IP
        ports:
          - protocol: TCP
            port: 11434
  podTemplate:
    spec:
      hostAliases:
        - ip: "10.96.5.10"
          hostnames:
            - "ollama.local"
      containers:
        - name: sandbox
          image: my-image:latest
```

### Completely block all network access

Provide empty ingress and egress arrays to deny all traffic:

```yaml
networkPolicy:
  ingress: []
  egress: []
```

## How policies are applied

1. The `SandboxTemplateReconciler` watches all `SandboxTemplate` resources.
2. For each template with `Managed` policy, it creates a `NetworkPolicy` named
   `<template-name>-network-policy` in the same namespace.
3. The policy targets sandbox pods via the label
   `agents.x-k8s.io/sandbox-template-ref-hash`.
4. On template updates, the controller compares the existing policy spec with
   the desired state and issues an update only if they differ.
5. The `NetworkPolicy` is owned by the `SandboxTemplate`, so deleting a
   template automatically garbage-collects its policy.
