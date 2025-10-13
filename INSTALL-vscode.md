# Agent-Sandbox Installation on GKE Autopilot

This guide provides step-by-step instructions for installing and running the agent-sandbox controller on Google Kubernetes Engine (GKE) Autopilot using the command line.

## Before You Begin

Ensure you have the following prerequisites installed and configured:

**Required Tools:**
- [Google Cloud SDK (gcloud)](https://cloud.google.com/sdk/docs/install)
- [kubectl](https://kubernetes.io/docs/tasks/tools/install-kubectl/) - version 1.29 or later
- [Git](https://git-scm.com/downloads)
- [Python 3](https://www.python.org/downloads/) - version 3.11 or later with pip

**GCP Setup:**
- Active Google Cloud Platform project with billing enabled
- Sufficient IAM permissions to create GKE clusters and push to Artifact Registry/Container Registry
- GKE API and Artifact Registry API enabled

**Set Default Configuration:**
```bash
# Set your project ID
export PROJECT_ID=<your-gcp-project-id>
gcloud config set project ${PROJECT_ID}

# Set your preferred region
export REGION=us-central1
gcloud config set compute/region ${REGION}
```

## Create GKE Autopilot Cluster

Create a GKE Autopilot cluster for running agent-sandbox:

```bash
gcloud container clusters create-auto agent-sandbox-cluster \
  --region=${REGION} \
  --release-channel=regular

# Get cluster credentials
gcloud container clusters get-credentials agent-sandbox-cluster \
  --region=${REGION}

# Verify cluster access
kubectl cluster-info
```

## Set Up Container Registry

Create an Artifact Registry repository to store the controller image:

```bash
# Create Artifact Registry repository
gcloud artifacts repositories create agent-sandbox \
  --repository-format=docker \
  --location=${REGION} \
  --description="Agent Sandbox Controller Images"

# Configure Docker authentication
gcloud auth configure-docker ${REGION}-docker.pkg.dev
```

Set the image prefix variable for later use:

```bash
export IMAGE_PREFIX="${REGION}-docker.pkg.dev/${PROJECT_ID}/agent-sandbox/"
```

## Build and Deploy Agent-Sandbox

### Clone the Repository

```bash
git clone https://github.com/kubernetes-sigs/agent-sandbox.git
cd agent-sandbox
```

### Set Up Python Virtual Environment

The deployment scripts require Python dependencies. Create a virtual environment to avoid conflicts:

```bash
# Create virtual environment
python3 -m venv .venv

# Activate virtual environment
source .venv/bin/activate

# Install required Python packages
pip install pyyaml
```

**Note:** You'll need to activate this virtual environment (`. .venv/bin/activate`) whenever you run the deployment scripts. To exit the virtual environment later, run `deactivate`.

### Build and Push Controller Image

Build the controller image and push it to your Artifact Registry:

```bash
./dev/tools/push-images --image-prefix=${IMAGE_PREFIX}
```

This command will:
1. Build the agent-sandbox controller container image
2. Tag it with the appropriate registry prefix
3. Push it to your Artifact Registry repository

### Deploy to GKE Autopilot

Deploy the controller to your GKE Autopilot cluster:

```bash
./dev/tools/deploy-to-kube --image-prefix=${IMAGE_PREFIX}
```

This command will:
1. Apply the Custom Resource Definitions (CRDs)
2. Create the `agent-sandbox-system` namespace
3. Deploy the controller with RBAC configurations
4. Create necessary services and webhooks

### Verify Installation

Check that the controller is running:

```bash
# Check controller pod status
kubectl get pods -n agent-sandbox-system

# Verify CRDs are installed
kubectl get crds | grep agents.x-k8s.io

# Check controller logs (StatefulSet pod)
kubectl logs -n agent-sandbox-system agent-sandbox-controller-0
```

You should see output showing the controller pod in a `Running` state with logs indicating "Starting EventSource" and "Starting Controller" messages.

**Note:** Keep your Python virtual environment activated for any subsequent deployment script operations. You can verify it's active by checking your shell prompt for `(.venv)` prefix.

## Deploy Example Sandbox

Once the controller is running, you can create a sample Sandbox resource.

### GKE Autopilot Storage Requirements

**Important:** GKE Autopilot automatically sets a 1Gi ephemeral storage limit if not explicitly specified. This is insufficient for most sandbox use cases (especially devcontainers that clone repos and install dependencies). You **must** add explicit ephemeral storage requests to your Sandbox specs.

There is **no way to configure Autopilot to use higher default ephemeral storage limits**. You must specify it in each Sandbox manifest.

### Example: VSCode Sandbox with Adequate Storage

```bash
# Navigate to examples directory
cd examples/vscode-sandbox

# Edit the existing vscode-sandbox.yaml to add ephemeral storage
# Open the file in your preferred editor
vi vscode-sandbox.yaml  # or vim, code, etc.
```

Modify the `spec.containers.resources` section to include ephemeral storage. The file should look like this:

```yaml
apiVersion: agents.x-k8s.io/v1alpha1
kind: Sandbox
metadata:
  name: sandbox-example
spec:
  containers:
  - name: devcontainer-main
    image: ghcr.io/coder/envbuilder
    resources:   # Add this line
      requests:   # Add this line
        cpu: "500m"   # Add this line
        memory: "2Gi"   # Add this line
        ephemeral-storage: "5Gi"  # Add this line
      limits:
        ephemeral-storage: "5Gi"  # Add this line
    env:
    - name: ENVBUILDER_GIT_URL
      value: https://github.com/kubernetes-sigs/agent-sandbox.git
    - name: ENVBUILDER_DEVCONTAINER_DIR
      value: examples/vscode-sandbox
    - name: ENVBUILDER_GIT_CLONE_SINGLE_BRANCH
      value: "true"
    - name: ENVBUILDER_INIT_SCRIPT
      value: /usr/local/bin/code-server-entrypoint
  # ... rest of the file
```

**Apply the modified sandbox:**

```bash
# Apply the sandbox
kubectl apply -f vscode-sandbox.yaml

# Wait for sandbox to be ready (this may take 2-5 minutes)
kubectl wait --for=condition=Ready pod sandbox-example --timeout=5m

# Check sandbox status
kubectl get sandboxes
kubectl get pod sandbox-example
```

### Verify the Sandbox is Running

Before attempting to access the sandbox, verify it's fully running:

```bash
# Check pod status - should show Running with 1/1 READY
kubectl get pod sandbox-example

# Check logs to ensure code-server started, it can take some time for the installation inside the pod to complete.
kubectl logs -f sandbox-example

# Look for "Running init command as user "root": ["/bin/sh" "-c" "/usr/local/bin/code-server-entrypoint"]" in the logs
# This confirms the server is ready to accept connections
```

### Accessing the Sandbox

Once the sandbox is running and code-server has started:

```bash
# Get and copy the VSCode password
kubectl exec sandbox-example -- cat /root/.config/code-server/config.yaml 
```

```bash
# Port-forward to access VSCode in browser
kubectl port-forward --address 0.0.0.0 pod/sandbox-example 13337

# Access in browser at http://localhost:13337
# If running remotely, replace localhost with your machine's IP
```

**Troubleshooting port-forward:**

If you get "connection refused" or timeout errors:

```bash
# 1. Check if the pod is actually running
kubectl get pod sandbox-example
# Status should be "Running", not "Error" or "CrashLoopBackOff"

# 2. Check container logs for errors
kubectl logs sandbox-example --tail=50

# 3. Verify code-server is listening on port 13337
kubectl exec sandbox-example -- netstat -tuln | grep 13337
# Should show: tcp  0  0 :::13337  :::*  LISTEN

# 4. If nothing is listening, check if envbuilder completed successfully
kubectl describe pod sandbox-example
# Look for events showing container startup issues

# 5. Check if ephemeral storage was actually applied
kubectl get pod sandbox-example -o jsonpath='{.spec.containers[0].resources}'
# Should show ephemeral-storage in both requests and limits
```

If the container keeps crashing with storage issues, you may need to increase ephemeral-storage to 10Gi.

## Uninstall

To remove agent-sandbox from your cluster:

```bash
# Delete all sandbox resources first
kubectl delete sandboxes --all

# Remove the controller
kubectl delete namespace agent-sandbox-system

# Delete CRDs
kubectl delete crd sandboxes.agents.x-k8s.io
kubectl delete crd sandboxclaims.extensions.agents.x-k8s.io
kubectl delete crd sandboxtemplates.extensions.agents.x-k8s.io
```

To delete the GKE cluster:

```bash
gcloud container clusters delete agent-sandbox-cluster \
  --region=${REGION} \
  --quiet
```

To delete the Artifact Registry repository:

```bash
gcloud artifacts repositories delete agent-sandbox \
  --location=${REGION} \
  --quiet
```

To clean up the local Python virtual environment:

```bash
# Deactivate if currently active
deactivate

# Remove virtual environment directory
rm -rf .venv
```

## Troubleshooting

**Pod evicted with "ephemeral local storage usage exceeds" error:**
- GKE Autopilot defaults to 1Gi ephemeral storage if not specified
- **Solution:** Always add explicit ephemeral-storage requests/limits to Sandbox specs (recommend 5Gi minimum for devcontainers)
- Check pod events: `kubectl describe pod <pod-name>`
- No cluster-wide configuration exists to change Autopilot's default ephemeral storage limit

**Python module not found errors:**
- Ensure virtual environment is activated: `source .venv/bin/activate`
- Reinstall dependencies: `pip install pyyaml`
- Check Python version: `python3 --version` (requires 3.11+)

**Controller pod not starting:**
- Check logs: `kubectl logs -n agent-sandbox-system agent-sandbox-controller-0`
- Verify image was pushed successfully: `gcloud artifacts docker images list ${REGION}-docker.pkg.dev/${PROJECT_ID}/agent-sandbox`
- Check RBAC permissions: `kubectl get clusterroles,clusterrolebindings | grep agent-sandbox`

**Image pull errors:**
- Ensure Artifact Registry authentication is configured: `gcloud auth configure-docker ${REGION}-docker.pkg.dev`
- Verify GKE service account has Artifact Registry Reader permissions

**CRD validation errors:**
- Regenerate CRDs if you modified API: `make all` then redeploy

**Webhook certificate issues:**
- The controller generates its own certificates. If issues persist, delete the namespace and redeploy.

**Sandbox pod logs not available:**
- The sandbox pod name matches the sandbox resource name
- View logs: `kubectl logs <sandbox-name>`
- If logs show "unable to retrieve container logs", the container likely crashed during startup - check `kubectl describe pod <sandbox-name>` for events and reason

**Port-forward connection refused or timeout:**
- Verify pod is Running: `kubectl get pod sandbox-example` (should show 1/1 READY)
- Check if application is listening: `kubectl exec sandbox-example -- netstat -tuln | grep 13337`
- View container logs: `kubectl logs sandbox-example --tail=100`
- For devcontainer sandboxes, envbuilder can take 5-10 minutes to clone repo, build container, and start code-server
- If code-server never starts, check ephemeral storage was applied: `kubectl get pod sandbox-example -o jsonpath='{.spec.containers[0].resources.requests.ephemeral-storage}'`
- Common issue: Container still initializing - wait longer and check logs for "HTTP server listening" message

## Advanced Configuration

**GKE Autopilot Ephemeral Storage Considerations:**

GKE Autopilot **cannot** be configured to set higher default ephemeral storage limits cluster-wide. The 1Gi default is hardcoded Autopilot behavior. You must explicitly set ephemeral storage in every Sandbox spec:

```yaml
spec:
  containers:
  - name: my-container
    resources:
      requests:
        ephemeral-storage: "5Gi"  # Required for devcontainers
      limits:
        ephemeral-storage: "5Gi"
```

**Recommended storage sizes:**
- Basic sandboxes: 2-3Gi
- Devcontainers with git clone: 5-10Gi
- Large projects or multi-language environments: 10-20Gi

**Resource Limits for Autopilot:**

GKE Autopilot automatically sets resource requests/limits, but you can specify them in your Sandbox spec:

```yaml
spec:
  resources:
    requests:
      memory: "256Mi"
      cpu: "250m"
    limits:
      memory: "512Mi"
      cpu: "500m"
```

## Additional Resources

- [GKE Autopilot Documentation](https://cloud.google.com/kubernetes-engine/docs/concepts/autopilot-overview)
- [Agent-Sandbox GitHub Repository](https://github.com/kubernetes-sigs/agent-sandbox)
- [Kubernetes SIG-Apps](https://github.com/kubernetes/community/tree/master/sig-apps)