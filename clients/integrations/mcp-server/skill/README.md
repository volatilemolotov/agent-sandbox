# k8s-agent-sandbox-mcp

## Prerequisites
- A Kubernetes cluster.
- [k8s-agent-sandbox CRDs and Router installed](https://github.com/kubernetes-sigs/agent-sandbox).
- The [mcp-server](https://github.com/kubernetes-sigs/agent-sandbox/tree/main/clients/integrations/mcp-server) deployed and reachable — see that repo's own deployment docs for how to run it.

## Setup
1. Deploy the mcp-server per the link above, and note its URL.
2. Install the skill (for example, `openclaw skills install @<owner>/k8s-agent-sandbox`)
3. Edit `mcp-config.json` in this skill's directory, setting `mcpServers.k8s-agent-sandbox.url` to that URL.
