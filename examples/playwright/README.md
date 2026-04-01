## Prerequisites

- A running Kubernetes cluster.
- The [**Agent Sandbox Controller**](https://github.com/kubernetes-sigs/agent-sandbox?tab=readme-ov-file#installation) installed.
- `kubectl` installed and configured locally.

## Setup: Deploying the Router

Before using the client, you must deploy the `sandbox-router`. This is a one-time setup.

1.  **Build and Push the Router Image:**

    For both Gateway Mode and Tunnel Mode, follow the instructions in [sandbox-router](../clients/python/agentic-sandbox-client/sandbox-router/README.md)
    to build, push, and apply the router image and resources.

2.  **Create a Sandbox Template:**
   
    Ensure a `SandboxTemplate` exists in your target namespace. In the `./source` directory run the following commands to build and deploy Playwright Sandbox Template:
    
    ```bash
    gcloud builds submit . # replace <PROJECT_ID> with your actual project id
    kubectl apply -f sandbox-template.yaml # replace <PROJECT_ID> with your actual project id
    ```

## Test
Create a Python virtual environment and install `k8s-agent-sandbox`:

```bash
python3 -m venv venv
. venv/bin/activate
pip install k8s-agent-sandbox
```
Run the example script:

```bash
python3 example.py https://kubernetes.io
```

The output should look like this:

```log
--- STDOUT ---
{"status": "success", "content": "Documentation\nKubernetes Blog\nTraining\nCareers\nPartners\nCommunity\nVersions\nEnglish\nProduction-Grade Container Orchestration\nLearn Kubernetes Basics\n\nKubernetes, also known as K8s, is an open source system for automating deployment, scaling, and management of containerized applications.\n\nIt groups containers that make up an application into logical units for easy management and discovery. Kubernetes builds upon 15 years of experience of running production workloads at Google, combined with best-of-breed ideas and practices from the community.\n\nPlanet scale\n\nDesigned on the same principles that allow Google to run billions of containers a week, Kubernetes can scale without increasing your operations team.\n\nNever outgrow\n\nWhether testing locally or running a global enterprise, Kubernetes flexibility grows with you to deliver your applications consistently and easily no matter how complex your need is.\n\nRun K8s anywhere\n\nKubernetes is open source giving you the freedom to take advantage of on-premises, hybrid, or public cloud infrastructure, letting you effortlessly move workloads to where it matters to you.\n\nTo download Kubernetes, visit the download section.\n\nWatch Video\nAttend upcoming KubeCon + CloudNativeCon events\nEurope (Amsterdam, Mar 23-26, 2026)\nNorth America (Salt Lake City, Nov 9-12, 2026)\nKubernetes Features\nAutomated rollouts and rollbacks\nKubernetes progressively rolls out changes to your application or its configuration, while monitoring application health to ensure it doesn't kill all your instances at the same time. If something goes wrong, Kubernetes will rollback the change for you. Take advantage of a growing ecosystem of deployment solutions.\nService discovery and load balancing\nNo need to modify your application to use an unfamiliar service discovery mechanism. Kubernetes gives Pods their own IP addresses and a single DNS name for a set of Pods, and can load-balance across them.\nStorage orchestration\nAutomatically mount the storage system of your "}

--- STDERR ---

--- EXIT CODE ---
-1
```
