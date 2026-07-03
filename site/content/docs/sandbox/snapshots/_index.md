---
title: "Snapshots"
linkTitle: "Snapshots"
weight: 15
description: >
  Create a Sandbox and optimize the GKE cluster resource usage without losing the session data in your Sandbox.
---
## Sandbox Snapshots

In many agentic workflows, you don't need a sandbox running indefinitely, but you need to preserve the exact state of a session—including filesystem changes and memory state—to resume it later.

While standard sandboxes are ephemeral, the `PodSnapshotSandboxClient` allows you to manually "freeze" a gVisor-protected sandbox and restore that state upon resuming the suspended sandbox later.

## Prerequisites

This guide requires a GKE Autopilot cluster with a gVisor node pool. See [GKE Cluster Setup](https://docs.cloud.google.com/kubernetes-engine/docs/how-to/pod-snapshots) for infrastructure setup instructions.

- A GKE Autopilot cluster with a gVisor node pool and necessary CRDs applied.
- Google Cloud credentials configured in your environment.
- The [Agent Sandbox Controller]({{< ref "/docs/getting_started/overview" >}}) installed.
- The [Sandbox Router](https://github.com/kubernetes-sigs/agent-sandbox/blob/main/clients/python/agentic-sandbox-client/sandbox-router/README.md) deployed in your cluster.
- A `SandboxWarmPool` named `simple-sandbox-pool` applied to your cluster. See the [Python Runtime Sandbox]({{< ref "/docs/runtime-templates/python" >}}) guide for setup instructions.
- The [Python SDK]({{< ref "/docs/python-client" >}}) installed: `pip install k8s-agent-sandbox`.

### Suspend & Resume with Snapshots

Unlike automatic pausing, snapshots give you granular control over when state is saved. This is ideal for multi-turn agents where the environment needs to be "parked" between user prompts to save costs.

#### Basic Workflow Example

The following example demonstrates creating a sandbox, modifying its filesystem, taking a snapshot, and suspending/resuming it to restore the state.

> Note: this example uses `simple-sandbox-pool`, which you should create in your GKE cluster first (along with its backing `simple-sandbox-template`). See the [snapshots example source folder](https://github.com/kubernetes-sigs/agent-sandbox/tree/main/site/content/docs/sandbox/snapshots/source) for the matching `SandboxTemplate` manifest.

> [!NOTE]
> A sandbox can only be restored from its own previous snapshots (via the `suspend()` and `resume()` lifecycle).


{{< blocks/tabs name="basic-workflow-example" >}}
  {{< blocks/tab name="Python" codelang="python" >}}
import time
from k8s_agent_sandbox.gke_extensions.snapshots import PodSnapshotSandboxClient

SLEEP_TIME = 10
def sleep():
    print(f"sleep {SLEEP_TIME} sec.")
    time.sleep(SLEEP_TIME)

# 1. Initialize the snapshot-capable client
client = PodSnapshotSandboxClient()

# 2. Create the sandbox
sandbox = client.create_sandbox("simple-sandbox-pool")
print(sandbox)

# 3. Run a command that alters the filesystem (e.g., Playwright caching data)
response = sandbox.commands.run("mkdir -p /tmp/data && echo 'session_active' > /tmp/data/status.txt")
print(response)
sleep()

# 4. Snapshot the Sandbox
# This freezes the gVisor container state.
snapshot_response = sandbox.snapshots.create("my-trigger")
sleep()
assert snapshot_response is not None

print(f"Snapshot saved with ID: {snapshot_response.snapshot_uid}")

# 5. Suspend the Sandbox
# This takes a snapshot and sets the Sandbox's operatingMode to Suspended.
suspend_result = sandbox.suspend(snapshot_before_suspend=True)
assert suspend_result.success
sleep()

# 6. Later, Resume the Sandbox
# This sets the Sandbox's operatingMode back to Running and automatically restores the latest state.
resume_result = sandbox.resume()
assert resume_result.success
assert resume_result.restored_from_snapshot

# 7. Verify the filesystem state was preserved
response = sandbox.commands.run("cat /tmp/data/status.txt")
print(response.stdout) # Should output 'session_active'
  {{< /blocks/tab >}}
  {{< blocks/tab name="Go" codelang="go" >}}
package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"time"
)

const sandboxAPIBase = "http://sandbox-service.default.svc.cluster.local"

const sleepTime = 10 * time.Second

func sleep() {
	fmt.Printf("sleep %s\n", sleepTime)
	time.Sleep(sleepTime)
}

// --- PodSnapshotSandboxClient ---

type PodSnapshotSandboxClient struct {
	http    *http.Client
	baseURL string
}

func NewPodSnapshotSandboxClient() *PodSnapshotSandboxClient {
	return &PodSnapshotSandboxClient{http: &http.Client{}, baseURL: sandboxAPIBase}
}

func (c *PodSnapshotSandboxClient) CreateSandbox(warmPool string) (*Sandbox, error) {
	body, _ := json.Marshal(map[string]string{"warmpool": warmPool})
	resp, err := c.http.Post(c.baseURL+"/sandboxes", "application/json", bytes.NewReader(body))
	if err != nil {
		return nil, fmt.Errorf("create sandbox: %w", err)
	}
	defer resp.Body.Close()

	var result struct {
		ID string `json:"id"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return nil, fmt.Errorf("decode response: %w", err)
	}
	return &Sandbox{ID: result.ID, client: c}, nil
}

// --- Sandbox ---

type Sandbox struct {
	ID     string
	client *PodSnapshotSandboxClient
}

func (s *Sandbox) String() string { return fmt.Sprintf("Sandbox{ID: %s}", s.ID) }

func (s *Sandbox) Commands() *CommandService   { return &CommandService{sandbox: s} }
func (s *Sandbox) Snapshots() *SnapshotService { return &SnapshotService{sandbox: s} }

// SuspendResult mirrors the Python SDK's suspend() return value.
type SuspendResult struct {
	Success bool `json:"success"`
}

// Suspend freezes the sandbox's gVisor container state and sets its
// operatingMode to Suspended. When snapshotBeforeSuspend is true, a fresh
// snapshot is taken immediately before suspending.
func (s *Sandbox) Suspend(snapshotBeforeSuspend bool) (*SuspendResult, error) {
	body, _ := json.Marshal(map[string]bool{"snapshot_before_suspend": snapshotBeforeSuspend})
	url := fmt.Sprintf("%s/sandboxes/%s/suspend", s.client.baseURL, s.ID)
	resp, err := s.client.http.Post(url, "application/json", bytes.NewReader(body))
	if err != nil {
		return nil, fmt.Errorf("suspend: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		respBody, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("suspend: server returned status %d: %s", resp.StatusCode, respBody)
	}

	var result SuspendResult
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return nil, fmt.Errorf("decode response: %w", err)
	}
	return &result, nil
}

// ResumeResult mirrors the Python SDK's resume() return value.
type ResumeResult struct {
	Success              bool `json:"success"`
	RestoredFromSnapshot bool `json:"restored_from_snapshot"`
}

// Resume sets the sandbox's operatingMode back to Running and automatically
// restores the latest snapshot state.
func (s *Sandbox) Resume() (*ResumeResult, error) {
	url := fmt.Sprintf("%s/sandboxes/%s/resume", s.client.baseURL, s.ID)
	resp, err := s.client.http.Post(url, "application/json", nil)
	if err != nil {
		return nil, fmt.Errorf("resume: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		respBody, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("resume: server returned status %d: %s", resp.StatusCode, respBody)
	}

	var result ResumeResult
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return nil, fmt.Errorf("decode response: %w", err)
	}
	return &result, nil
}

// --- CommandService ---

type CommandService struct{ sandbox *Sandbox }

type CommandResult struct {
	Stdout   string
	Stderr   string
	ExitCode int
}

func (c *CommandService) Run(cmd string) (CommandResult, error) {
	body, _ := json.Marshal(map[string]string{"command": cmd})
	url := fmt.Sprintf("%s/sandboxes/%s/commands", c.sandbox.client.baseURL, c.sandbox.ID)
	resp, err := c.sandbox.client.http.Post(url, "application/json", bytes.NewReader(body))
	if err != nil {
		return CommandResult{}, fmt.Errorf("run command: %w", err)
	}
	defer resp.Body.Close()

	var result struct {
		Stdout   string `json:"stdout"`
		Stderr   string `json:"stderr"`
		ExitCode int    `json:"exit_code"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return CommandResult{}, fmt.Errorf("decode response: %w", err)
	}
	return CommandResult{Stdout: result.Stdout, Stderr: result.Stderr, ExitCode: result.ExitCode}, nil
}

func (r CommandResult) String() string {
	return fmt.Sprintf("CommandResult{ExitCode: %d, Stdout: %q}", r.ExitCode, r.Stdout)
}

// --- SnapshotService ---

type SnapshotService struct{ sandbox *Sandbox }

type SnapshotResponse struct {
	SnapshotUID string `json:"snapshot_uid"`
}

func (s *SnapshotService) Create(trigger string) (*SnapshotResponse, error) {
	body, _ := json.Marshal(map[string]string{"trigger": trigger})
	url := fmt.Sprintf("%s/sandboxes/%s/snapshots", s.sandbox.client.baseURL, s.sandbox.ID)
	resp, err := s.sandbox.client.http.Post(url, "application/json", bytes.NewReader(body))
	if err != nil {
		return nil, fmt.Errorf("create snapshot: %w", err)
	}
	defer resp.Body.Close()

	var result SnapshotResponse
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return nil, fmt.Errorf("decode response: %w", err)
	}
	return &result, nil
}

// --- main ---

func main() {
	// 1. Initialize the snapshot-capable client
	client := NewPodSnapshotSandboxClient()

	// 2. Create the sandbox
	sandbox, err := client.CreateSandbox("simple-sandbox-pool")
	if err != nil {
		panic(err)
	}
	fmt.Println(sandbox)

	// 3. Run a command that alters the filesystem
	response, err := sandbox.Commands().Run("mkdir -p /tmp/data && echo 'session_active' > /tmp/data/status.txt")
	if err != nil {
		panic(err)
	}
	fmt.Println(response)
	sleep()

	// 4. Snapshot the sandbox
	snapshotResponse, err := sandbox.Snapshots().Create("my-trigger")
	if err != nil {
		panic(err)
	}
	sleep()
	if snapshotResponse == nil {
		panic("snapshot response is nil")
	}
	fmt.Printf("Snapshot saved with ID: %s\n", snapshotResponse.SnapshotUID)

	// 5. Suspend the sandbox (takes one more snapshot immediately before suspending)
	suspendResult, err := sandbox.Suspend(true)
	if err != nil {
		panic(err)
	}
	if !suspendResult.Success {
		panic("suspend did not succeed")
	}
	sleep()

	// 6. Resume the same sandbox — this restores the latest snapshot state
	resumeResult, err := sandbox.Resume()
	if err != nil {
		panic(err)
	}
	if !resumeResult.Success {
		panic("resume did not succeed")
	}
	if !resumeResult.RestoredFromSnapshot {
		panic("resume did not restore from a snapshot")
	}

	// 7. Verify the filesystem state was preserved
	result, err := sandbox.Commands().Run("cat /tmp/data/status.txt")
	if err != nil {
		panic(err)
	}
	if result.ExitCode != 0 {
		panic(fmt.Errorf("command failed: exit code %d: %s", result.ExitCode, result.Stderr))
	}
	fmt.Print(result.Stdout) // Should output 'session_active'
}
  {{< /blocks/tab >}}
{{< /blocks/tabs >}}


