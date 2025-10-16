# Agent-Sandbox Installation on kind

This guide provides step-by-step instructions for installing and running the agent-sandbox controller on kind (Kubernetes in Docker) for local development and testing.

## Before You Begin

Ensure you have the following prerequisites installed:

**Required Tools:**
- [Go](https://golang.org/doc/install)
- [make](https://www.gnu.org/software/make/)
- [Python 3](https://www.python.org/downloads/) with pip
- [Docker](https://docs.docker.com/get-docker/)
- [Docker buildx plugin](https://github.com/docker/buildx?tab=readme-ov-file#installing)
- [kind](https://kind.sigs.k8s.io/docs/user/quick-start/#installation)
- [kubectl](https://kubernetes.io/docs/tasks/tools/install-kubectl/)

**Verify installations:**
```bash
go version
make --version
python3 --version
docker --version
kind --version
kubectl version --client
```

## Deploy Agent-Sandbox to kind

### Clone the Repository

```bash
git clone https://github.com/kubernetes-sigs/agent-sandbox.git
cd agent-sandbox
```

### Set Up Python Environment

The deployment scripts require Python with pyyaml:

```bash
# Create virtual environment
python3 -m venv .venv

# Activate virtual environment
source .venv/bin/activate

# Install required packages
pip install pyyaml
```

**Note:** Keep the virtualenv activated for all make commands. Deactivate with `deactivate` when done.

### Deploy to kind

With the virtualenv activated, deploy using the Makefile target:

```bash
make deploy-kind
```

This command will:
1. Create a kind cluster named `agent-sandbox` (if it doesn't exist)
2. Build the controller container image
3. Load the image into the kind cluster
4. Deploy the controller to the cluster in the `agent-sandbox-system` namespace

### Verify Installation

Check that the controller is running:

```bash
# Check controller pod status
kubectl get pods -n agent-sandbox-system

# Verify CRDs are installed
kubectl get crds | grep agents.x-k8s.io

# Check controller logs
kubectl logs -n agent-sandbox-system -l control-plane=controller-manager -f
```

You should see the controller pod in `Running` state.

## Uninstall

Remove agent-sandbox from your cluster:

```bash
# Delete all sandbox resources
kubectl delete sandboxes --all

# Remove the controller and namespace
kubectl delete namespace agent-sandbox-system

# Delete CRDs
kubectl delete crd sandboxes.agents.x-k8s.io
```

Delete the kind cluster:

```bash
kind delete cluster --name agent-sandbox
```

## Troubleshooting

**Python module not found errors:**
- Activate virtual environment: `source .venv/bin/activate`
- Reinstall dependencies: `pip install pyyaml`
- Verify Python version: `python3 --version` (requires 3.11+)

**Controller pod not starting:**
- Check logs: `kubectl logs -l app=agent-sandbox-controller`
- Verify RBAC permissions: `kubectl get clusterroles,clusterrolebindings | grep agent-sandbox`
- Check if CRDs are properly installed: `kubectl get crds | grep agents`
- Verify the image is correct: `kubectl get statefulset agent-sandbox-controller -o yaml | grep image:`

**Storage issues:**
- kind uses local Docker storage - ensure Docker has enough disk space
- Check Docker disk usage: `docker system df`
- Clean up unused images: `docker system prune`
- Verify PVC is bound: `kubectl get pvc`

**Out of memory errors:**
- kind uses Docker resources - check Docker resource limits in Docker Desktop settings
- Increase Docker memory allocation (recommend 8GB+ for development)
- Reduce sandbox resource requests if needed

**Building the Controller Binary:**

To build just the controller binary:

```bash
make build
```

Binary will be at `bin/manager`.

**Regenerating CRDs and RBAC:**

After modifying `api/` or `controllers/` directories:

```bash
make all
```

## Additional Resources

- [Agent-Sandbox GitHub Repository](https://github.com/kubernetes-sigs/agent-sandbox)
- [Agent-Sandbox Development Guide](https://github.com/kubernetes-sigs/agent-sandbox/blob/main/docs/development.md)
- [kind Documentation](https://kind.sigs.k8s.io/)
- [Kubernetes SIG-Apps](https://github.com/kubernetes/community/tree/master/sig-apps)