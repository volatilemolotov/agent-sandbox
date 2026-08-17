// Copyright 2026 The Kubernetes Authors.
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

package main

import (
	"context"
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"os"
	"strings"
	"testing"
)

// runForUser/runReuse/main() orchestrate a real *sandbox.Client (a concrete
// SDK type, not an interface, so it can't be faked without a live cluster --
// that's what the e2e presubmit is for). chat(), resetHistory(), and the
// claim-cache file helpers don't touch that client at all, so they're
// covered here directly.

func TestChat_SendsExpectedHeadersAndBody(t *testing.T) {
	var gotPath, gotMethod string
	var gotHeaders http.Header
	var gotBody map[string]string

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		gotPath = r.URL.Path
		gotMethod = r.Method
		gotHeaders = r.Header.Clone()
		if err := json.NewDecoder(r.Body).Decode(&gotBody); err != nil {
			t.Errorf("failed to decode request body: %v", err)
		}
		json.NewEncoder(w).Encode(chatResponse{Owner: "alice", Reply: "I am alice's agent. Hi!", HistoryTurns: 1})
	}))
	defer server.Close()

	resp, err := chat(context.Background(), server.URL, "sb-1", "ns-1", "alice", "hello")
	if err != nil {
		t.Fatalf("chat() returned an error: %v", err)
	}

	if gotMethod != http.MethodPost {
		t.Errorf("got method %s, want POST", gotMethod)
	}
	if gotPath != "/chat" {
		t.Errorf("got path %s, want /chat", gotPath)
	}
	if got := gotHeaders.Get("X-Sandbox-ID"); got != "sb-1" {
		t.Errorf("got X-Sandbox-ID=%q, want sb-1", got)
	}
	if got := gotHeaders.Get("X-Sandbox-Namespace"); got != "ns-1" {
		t.Errorf("got X-Sandbox-Namespace=%q, want ns-1", got)
	}
	if got := gotHeaders.Get("X-Sandbox-Port"); got != agentPort {
		t.Errorf("got X-Sandbox-Port=%q, want %s", got, agentPort)
	}
	if got := gotHeaders.Get("X-Owner"); got != "alice" {
		t.Errorf("got X-Owner=%q, want alice", got)
	}
	if gotBody["prompt"] != "hello" {
		t.Errorf("got prompt=%q, want hello", gotBody["prompt"])
	}
	if resp.Owner != "alice" || resp.HistoryTurns != 1 {
		t.Errorf("got response %+v, unexpected fields", resp)
	}
}

func TestChat_NonSuccessStatusReturnsError(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusBadGateway)
		io.WriteString(w, "router down")
	}))
	defer server.Close()

	_, err := chat(context.Background(), server.URL, "sb-1", "ns-1", "alice", "hi")
	if err == nil {
		t.Fatal("expected an error for a 502 response, got nil")
	}
	if !strings.Contains(err.Error(), "502") || !strings.Contains(err.Error(), "router down") {
		t.Errorf("got error %q, want it to mention the status code and body", err)
	}
}

func TestChat_UnparseableResponseReturnsError(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		io.WriteString(w, "not json")
	}))
	defer server.Close()

	_, err := chat(context.Background(), server.URL, "sb-1", "ns-1", "alice", "hi")
	if err == nil {
		t.Fatal("expected a decode error, got nil")
	}
}

// resetHistory takes a *sandbox.Sandbox -- a concrete SDK type with only
// unexported fields and no exported constructor -- so it can't be
// constructed outside the sandbox package without a live cluster. Not
// unit-tested for the same reason runForUser/runReuse aren't: chat()
// already covers the identical request-building logic (headers, method,
// error handling) that resetHistory shares.

func TestClaimCachePath_IncludesOwnerName(t *testing.T) {
	got := claimCachePath("alice")
	if !strings.Contains(got, "alice") {
		t.Errorf("got path %q, want it to contain the owner name", got)
	}
	if !strings.HasSuffix(got, ".claim") {
		t.Errorf("got path %q, want a .claim suffix", got)
	}
	// Same owner must always resolve to the same path, or -reuse couldn't
	// find its own previously-cached claim on the next invocation.
	if got2 := claimCachePath("alice"); got != got2 {
		t.Errorf("claimCachePath is not stable: %q != %q", got, got2)
	}
}

func TestClaimCache_RoundTrip(t *testing.T) {
	owner := "test-owner-roundtrip"
	t.Cleanup(func() { clearCachedClaim(owner) })

	if got := readCachedClaim(owner); got != "" {
		t.Fatalf("got %q before writing anything, want empty", got)
	}

	if err := writeCachedClaim(owner, "claim-abc-123"); err != nil {
		t.Fatalf("writeCachedClaim failed: %v", err)
	}
	if got := readCachedClaim(owner); got != "claim-abc-123" {
		t.Errorf("got %q, want claim-abc-123", got)
	}

	clearCachedClaim(owner)
	if got := readCachedClaim(owner); got != "" {
		t.Errorf("got %q after clearing, want empty", got)
	}
}

func TestReadCachedClaim_TrimsWhitespace(t *testing.T) {
	owner := "test-owner-trim"
	t.Cleanup(func() { clearCachedClaim(owner) })

	if err := os.WriteFile(claimCachePath(owner), []byte("claim-xyz\n\n"), 0o600); err != nil {
		t.Fatalf("failed to write test fixture: %v", err)
	}
	if got := readCachedClaim(owner); got != "claim-xyz" {
		t.Errorf("got %q, want trimmed claim-xyz", got)
	}
}
