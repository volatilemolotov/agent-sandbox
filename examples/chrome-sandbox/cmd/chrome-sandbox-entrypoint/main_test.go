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
	"net"
	"net/http"
	"testing"
	"time"
)

// Most of this file (Chrome.Run, VNCServer.Run/WaitForReady) shells out to
// real OS binaries (/start-chrome, Xtigervnc, xdpyinfo) that don't exist in
// a unit test environment and aren't dependency-injected, so they aren't
// covered here. Chrome.WaitForReady's URL is hardcoded to
// http://localhost:9222 too, but that's just a loopback TCP port, so its
// polling logic can be exercised for real by actually binding one.

func TestChromeWaitForReady_ReturnsOnceServerResponds200(t *testing.T) {
	// Bind to "localhost", the same hostname WaitForReady dials, rather than
	// hardcoding 127.0.0.1: if "localhost" ever resolved to the IPv6 loopback
	// first on some environment, a listener fixed to 127.0.0.1 would silently
	// never be reached, and the test would fail against a genuinely healthy
	// server. Using the identical hostname for both sides means whatever it
	// resolves to, they agree.
	listener, err := net.Listen("tcp", "localhost:9222")
	if err != nil {
		t.Skipf("port 9222 unavailable in this environment: %v", err)
	}
	defer listener.Close()

	mux := http.NewServeMux()
	mux.HandleFunc("/json/version", func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
		w.Write([]byte(`{"Browser":"HeadlessChrome"}`))
	})
	server := &http.Server{Handler: mux}
	go server.Serve(listener)
	defer server.Close()

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	c := &Chrome{}
	if err := c.WaitForReady(ctx); err != nil {
		t.Fatalf("WaitForReady returned an error against a healthy server: %v", err)
	}
}

func TestChromeWaitForReady_ReturnsContextErrorWhenCancelled(t *testing.T) {
	ctx, cancel := context.WithCancel(context.Background())
	cancel() // already cancelled -- must not try to dial anything

	c := &Chrome{}
	err := c.WaitForReady(ctx)
	if err != ctx.Err() {
		t.Fatalf("got error %v, want %v", err, ctx.Err())
	}
}

func TestVNCServerWaitForReady_ReturnsContextErrorWhenCancelled(t *testing.T) {
	ctx, cancel := context.WithCancel(context.Background())
	cancel() // already cancelled -- must not shell out to xdpyinfo

	v := &VNCServer{}
	err := v.WaitForReady(ctx)
	if err != ctx.Err() {
		t.Fatalf("got error %v, want %v", err, ctx.Err())
	}
}
