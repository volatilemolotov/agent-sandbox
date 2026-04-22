// Copyright 2025 The Kubernetes Authors.
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

// gemini-cu-sandbox is an HTTP API server that delegates browser tasks to the
// Gemini computer-use-preview agent, mirroring the Python gemini-cu-sandbox
// FastAPI example.
//
// Endpoints:
//
//	GET  /       health check
//	POST /agent  run the computer-use agent with a query
package main

import (
	"encoding/json"
	"errors"
	"fmt"
	"log"
	"net/http"
	"os"
	"os/exec"
	"strings"
)

func writeJSON(w http.ResponseWriter, status int, v any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(v)
}

func handleHealth(w http.ResponseWriter, _ *http.Request) {
	writeJSON(w, http.StatusOK, map[string]string{
		"status":  "ok",
		"message": "Sandbox Runtime is active.",
	})
}

type agentRequest struct {
	Query  string `json:"query"`
	APIKey string `json:"api_key,omitempty"`
}

type agentResponse struct {
	Stdout   string `json:"stdout"`
	Stderr   string `json:"stderr"`
	ExitCode int    `json:"exit_code"`
}

func handleAgent(w http.ResponseWriter, r *http.Request) {
	var req agentRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeJSON(w, http.StatusBadRequest, agentResponse{Stderr: "invalid request body", ExitCode: 1})
		return
	}

	// Build a copy of the environment for the subprocess.
	env := os.Environ()
	envMap := make(map[string]int, len(env))
	for i, e := range env {
		if k, _, ok := strings.Cut(e, "="); ok {
			envMap[k] = i
		}
	}

	setEnv := func(key, val string) {
		entry := key + "=" + val
		if i, exists := envMap[key]; exists {
			env[i] = entry
		} else {
			envMap[key] = len(env)
			env = append(env, entry)
		}
	}

	setEnv("PLAYWRIGHT_HEADLESS", "1")
	if req.APIKey != "" {
		setEnv("GEMINI_API_KEY", req.APIKey)
	}

	// Verify GEMINI_API_KEY is available.
	hasKey := false
	for _, e := range env {
		if strings.HasPrefix(e, "GEMINI_API_KEY=") && len(e) > len("GEMINI_API_KEY=") {
			hasKey = true
			break
		}
	}
	if !hasKey {
		writeJSON(w, http.StatusOK, agentResponse{
			Stderr:   "GEMINI_API_KEY not found in request or environment variables. Please set it via request or environment variable (e.g., K8s secret).",
			ExitCode: 1,
		})
		return
	}

	cmd := exec.Command("python", "computer-use-preview/main.py", "--query", req.Query)
	cmd.Dir = "/app"
	cmd.Env = env

	var stdout, stderr strings.Builder
	cmd.Stdout = &stdout
	cmd.Stderr = &stderr

	err := cmd.Run()
	exitCode := 0
	if err != nil {
		var exitErr *exec.ExitError
		if errors.As(err, &exitErr) {
			exitCode = exitErr.ExitCode()
		} else {
			log.Printf("agent execution error: %v", err)
			writeJSON(w, http.StatusOK, agentResponse{
				Stderr:   fmt.Sprintf("failed to execute command: %v", err),
				ExitCode: 1,
			})
			return
		}
	}
	writeJSON(w, http.StatusOK, agentResponse{
		Stdout:   stdout.String(),
		Stderr:   stderr.String(),
		ExitCode: exitCode,
	})
}

func main() {
	mux := http.NewServeMux()
	mux.HandleFunc("GET /", handleHealth)
	mux.HandleFunc("POST /agent", handleAgent)

	addr := ":8080"
	log.Printf("Gemini CU Sandbox listening on %s", addr)
	if err := http.ListenAndServe(addr, mux); err != nil {
		log.Fatal(err)
	}
}
