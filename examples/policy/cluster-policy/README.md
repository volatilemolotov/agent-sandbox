# User Guide: Protecting Sandboxes with Kyverno

## 1. Overview

This guide provides step-by-step instructions for configuring a Kyverno security policy on a Kubernetes cluster. The goal of this policy is to **prevent any user or process from granting new permissions to a ServiceAccount that is actively being used by a custom `Sandbox` resource.**

This acts as a critical security boundary, preventing accidental or malicious privilege escalation for sandboxed environments.

**How it Works:**  
The policy intercepts all `RoleBinding` and `ClusterRoleBinding` creation requests. If the request targets a `ServiceAccount` that is referenced by a running `Sandbox`, Kyverno will **block the request and return an error**.

---

## 2. Prerequisites

Before you begin, ensure you have the following:

- `kubectl` access to a Kubernetes cluster with permissions to install Helm charts and create `ClusterPolicy` resources.
- Helm v3+ installed on your local machine.
- The **Sandbox controller** must already be installed. This is crucial as it provides the `Sandbox` Custom Resource Definition (CRD) that the policy needs to recognize.

---

## 3. Configuration Steps

### Step 1: Install Kyverno

If you do not already have Kyverno installed, use the following Helm commands to deploy it to your cluster.

```bash
# 1. Add the official Kyverno Helm repository
helm repo add kyverno https://kyverno.github.io/kyverno/

# 2. Update your local Helm repositories
helm repo update

# 3. Install Kyverno into its own namespace
helm install kyverno kyverno/kyverno -n kyverno --create-namespace
```

You can verify the installation by checking the pods and CRDs in the kyverno namespace:

```bash
kubectl get pods -n kyverno
```

All pods should be in the `Running` state.

### Step 2: Verify Custom Resource Definitions (CRDs)

Ensure that the Kyverno CRDs are present in your cluster:

```bash
kubectl get crds | grep kyverno
```

If either CRD is not found, stop and resolve that issue before proceeding.

### Step 3: Create and Apply the Kyverno Policy

Apply the policy:

```bash
kubectl apply -f prevent-sandbox-binding-policy.yaml
```

## Understanding the Policy Fields

* `spec.validationFailureAction`: Enforce
Tells Kyverno to actively block any API request that violates the rule.

* `rules[].match`: Triggers on creation or update of any RoleBinding or ClusterRoleBinding.

* `rules[].validate.foreach`: Iterates over request.object.subjects, filtering for ServiceAccount types.

* `context.apiCall`: Calls the K8s API to check for Sandbox resources referencing the given ServiceAccount.

* `pattern`: The request is allowed only if the number of matching sandboxes is 0. If it’s 1 or more, the request is blocked.


### Step 4: Verify the Policy is Active

Check that the policy was successfully created and is ready:

```bash
kubectl get clusterpolicy prevent-sandbox-sa-binding

NAME         ADMISSION   BACKGROUND   READY   AGE   MESSAGE
prevent-sandbox-sa-binding   true        true         True    36s   Ready
```

Ensure `READY` is `True`.

## 4. Testing and Verification

To confirm the policy is working, simulate an attempt to grant new permissions to a protected `ServiceAccount`.

### A. Set Up the Test Scenario

Apply the `ServiceAccount` and `Sandbox` resources to the cluster.

```bash
kubectl apply -f - <<EOF
apiVersion: v1
kind: ServiceAccount
metadata:
  name: sandbox-sa
  namespace: sandbox-ns
---
apiVersion: agents.x-k8s.io/v1alpha1
kind: Sandbox
metadata:
  name: sandbox-example
  namespace: sandbox-ns
spec:
  podTemplate:
    metadata:
      labels:
        sandbox: my-sandbox
      annotations:
        test: "yes"
    spec:
      serviceAccountName: sandbox-sa
      containers:
      - name: my-container
        image: busybox
        command: ["/bin/sh", "-c", "sleep 3600"]
EOF
```


### B. Trigger the Policy (Expected Failure)

Apply a `RoleBinding` that should fail

```bash
kubectl apply -f - <<EOF
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: test-forbidden-binding
  namespace: sandbox-ns
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: Role
  name: view
subjects:
- kind: ServiceAccount
  name: sandbox-sa
  namespace: sandbox-ns
EOF
```

### C. Check the Expected Outcome
You should see an error like:
```bash
Error from server: error when creating "role-binding-fail.yaml": admission webhook "validate.kyverno.svc-fail" denied the request: 

resource RoleBinding/default/test-forbidden-binding was blocked due to the following policies 

prevent-sandbox-sa-binding:
  block-sandbox-sa-bindings: 'validation failure: validation error: Binding to a ServiceAccount
    that is actively in use by a Sandbox is forbidden...'
```

If you see this error, your security policy is successfully configured and enforced. ✅