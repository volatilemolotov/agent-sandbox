---
title: "Networking"
linkTitle: "Networking"
weight: 15
description: >
  Network architecture and connectivity for Agent Sandbox
---

Agent Sandbox provides a complete networking stack: a reverse-proxy router for
reaching sandboxes, a headless Service per sandbox for stable DNS identity, and
Kubernetes NetworkPolicy for fine-grained traffic control. Every sandbox runs
with a **secure-by-default** posture that you can customise per
`SandboxTemplate` or hand off to an external CNI.

## Network architecture

Traffic to and from sandboxes flows through a layered architecture:

```text
External Client / Agent
        |
        v
   +---------+
   | Gateway |  Kubernetes Gateway API (single stable IP)
   +----+----+
        |  HTTPRoute (all paths)
        v
 +--------------+
 |Sandbox Router|  Reverse proxy (reads X-Sandbox-* headers)
 +------+-------+
        |  Constructs: {id}.{namespace}.svc.cluster.local:{port}
        v
 +--------------+
 |Headless Svc  |  One per Sandbox, DNS resolves directly to pod IP
 +------+-------+
        |
        v
 +--------------+
 | Sandbox Pod  |  Target container
 +--------------+
```

### Headless Service

The core Sandbox controller creates a **headless Service** (ClusterIP: None) for
every Sandbox. The Service shares the Sandbox's name and namespace, so
Kubernetes DNS resolves `<sandbox-name>.<namespace>.svc.cluster.local` directly
to the pod IP. This gives each sandbox a stable DNS identity without allocating
a cluster IP.

### Sandbox Router

The Sandbox Router is a lightweight async reverse proxy (FastAPI + Uvicorn)
deployed as a Kubernetes Deployment. A single router instance handles **all**
sandboxes -- there are no per-sandbox routes or ingress rules to manage.

Clients reach a sandbox by sending a request to the Gateway with three headers:

| Header | Required | Default | Description |
|--------|----------|---------|-------------|
| `X-Sandbox-ID` | Yes | -- | Name of the target Sandbox |
| `X-Sandbox-Namespace` | No | `default` | Namespace the Sandbox runs in |
| `X-Sandbox-Port` | No | `8888` | Port on the sandbox pod to forward to |

The router constructs the internal Kubernetes FQDN from these headers, proxies
the request, and streams the response back.

**Example request:**

```bash
curl http://<gateway-ip>/my-endpoint \
  -H "X-Sandbox-ID: my-sandbox" \
  -H "X-Sandbox-Namespace: prod" \
  -H "X-Sandbox-Port: 9000"
# Proxied to: my-sandbox.prod.svc.cluster.local:9000/my-endpoint
```

This header-based routing design scales to thousands of sandboxes without
creating per-sandbox network infrastructure.
