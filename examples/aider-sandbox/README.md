# Aider in Agent Sandbox

SAMPLE_TEXT

## Set up

SAMPLE_TEXT

```bash
kind create cluster --name agent-sandbox
```

## Deploy Aider

SAMPLE_TEXT

```bash
docker build -t aider-sandbox:v1 .
kind load docker-image aider-sandbox:v1 --name agent-sandbox
```

```bash
export OPENAI_API_KEY=<OPENAI_API_KEY>
export NAMESPACE=default

kubectl create secret generic llm-secrets --from-literal=openai-api-key=${OPENAI_API_KEY} --namespace=${NAMESPACE}
```

SAMPLE_TEXT

```bash
kubectl apply -f template.yaml
kubectl apply -f warmpool.yaml
kubectl apply -f claim.yaml
```

## Test the environment

SAMPLE_TEXT

```bash
sandbox_name=$(kubectl get sandboxclaim user-session-aider -o jsonpath='{.status.sandbox.name}')
kubectl port-forward ${sandbox_name} 8501:8501
```

SAMPLE_TEXT

```txt
Q: Can you please say what is this project about?

A: Based on the file summaries you provided, this project appears to be related to managing Kubernetes resources, specifically focusing on sandbox environments. It includes various components for handling sandbox templates, claims, warm pools, and lifecycle management. The project seems to involve both Go and Python codebases, with functionalities for Kubernetes client interactions, sandbox management, and possibly some form of resource orchestration or automation within Kubernetes clusters. The presence of files related to OpenTelemetry suggests that there might be tracing or monitoring capabilities integrated into the project as well.
```

## Clean up

SAMPLE_TEXT

```bash
kind delete cluster --name agent-sandbox
```
