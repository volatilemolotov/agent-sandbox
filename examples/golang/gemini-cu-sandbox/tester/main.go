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

// tester is an integration test client for the gemini-cu-sandbox HTTP server.
//
// Usage:
//
//	Router mode: go run ./tester <router_base_url> <sandbox_id>
//	Local mode:  go run ./tester <container_base_url>
package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
	"strings"
)

func mustJSON(v any) []byte {
	b, err := json.Marshal(v)
	if err != nil {
		log.Fatal(err)
	}
	return b
}

func decodeJSON(body []byte, v any) {
	if err := json.Unmarshal(body, v); err != nil {
		log.Fatalf("decode JSON: %v (body: %s)", err, body)
	}
}

func doRequest(method, url string, headers map[string]string, body []byte) (int, []byte) {
	var bodyReader io.Reader
	if body != nil {
		bodyReader = bytes.NewReader(body)
	}
	req, err := http.NewRequest(method, url, bodyReader)
	if err != nil {
		log.Fatalf("build request: %v", err)
	}
	if body != nil {
		req.Header.Set("Content-Type", "application/json")
	}
	for k, v := range headers {
		req.Header.Set(k, v)
	}
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		log.Fatalf("%s %s: %v", method, url, err)
	}
	defer resp.Body.Close()
	respBody, _ := io.ReadAll(resp.Body)
	return resp.StatusCode, respBody
}

func testHealthCheck(baseURL string, headers map[string]string) {
	fmt.Println("--- Testing Health Check endpoint ---")
	status, body := doRequest("GET", baseURL+"/", headers, nil)
	if status != http.StatusOK {
		log.Fatalf("health check: expected 200, got %d", status)
	}
	var result map[string]string
	decodeJSON(body, &result)
	if result["status"] != "ok" {
		log.Fatalf("health check: expected status=ok, got %q", result["status"])
	}
	fmt.Println("Health check successful!")
	fmt.Println("Response JSON:", string(body))
}

func testAgentWithoutAPIKey(baseURL string, headers map[string]string) {
	fmt.Println("\n--- Testing Agent endpoint (without API key) ---")
	payload := map[string]string{"query": "what is the weather today"}
	status, body := doRequest("POST", baseURL+"/agent", headers, mustJSON(payload))
	if status != http.StatusOK {
		log.Fatalf("agent (no key): expected 200, got %d", status)
	}
	var result map[string]any
	decodeJSON(body, &result)
	fmt.Println("Agent command execution requested successfully!")
	fmt.Println("Response JSON:", string(body))

	exitCode, _ := result["exit_code"].(float64)
	if int(exitCode) != 0 {
		log.Fatalf("agent (no key): expected exit_code=0, got %v", exitCode)
	}
	stdout, _ := result["stdout"].(string)
	apiKeyError := strings.Contains(stdout, "API key not valid") ||
		strings.Contains(stdout, "GEMINI_API_KEY") ||
		strings.Contains(stdout, "PERMISSION_DENIED") ||
		strings.Contains(stdout, "DefaultCredentialsError")
	if !apiKeyError {
		log.Fatal("agent (no key): expected API key error in stdout, not found")
	}
	fmt.Println("Test successful: Agent exited gracefully with expected API key error message.")
}

func testAgentWithAPIKey(baseURL string, headers map[string]string) {
	fmt.Println("\n--- Testing Agent endpoint (with API key) ---")
	payload := map[string]string{
		"query": "Navigate to https://www.example.com and tell me what the heading says.",
	}
	status, body := doRequest("POST", baseURL+"/agent", headers, mustJSON(payload))
	if status != http.StatusOK {
		log.Fatalf("agent (with key): expected 200, got %d", status)
	}
	var result map[string]any
	decodeJSON(body, &result)
	fmt.Println("Agent command execution requested successfully!")
	fmt.Println("Response JSON:", string(body))

	exitCode, _ := result["exit_code"].(float64)
	if int(exitCode) != 0 {
		log.Fatalf("agent (with key): expected exit_code=0, got %v", exitCode)
	}
	stdout, _ := result["stdout"].(string)
	if !strings.Contains(stdout, "Example Domain") {
		log.Fatal("agent (with key): expected 'Example Domain' in stdout")
	}
	fmt.Println("Test successful: Agent navigated to the page and extracted the heading.")
}

func main() {
	var baseURL string
	headers := make(map[string]string)

	switch len(os.Args) {
	case 3:
		// Router mode: traffic is routed to the sandbox via the sandbox-router.
		fmt.Println("--- Running in Router Mode ---")
		baseURL = os.Args[1]
		headers["X-Sandbox-ID"] = os.Args[2]
		headers["X-Sandbox-Namespace"] = "default"
		headers["X-Sandbox-Port"] = "8080"
	case 2:
		// Local Docker mode: direct connection to the container.
		fmt.Println("--- Running in Local Docker Mode ---")
		baseURL = os.Args[1]
	default:
		fmt.Fprintln(os.Stderr, "Usage:")
		fmt.Fprintln(os.Stderr, "  Router Mode: tester <router_base_url> <sandbox_id>")
		fmt.Fprintln(os.Stderr, "  Local Docker Mode: tester <container_base_url>")
		os.Exit(1)
	}

	testHealthCheck(baseURL, headers)

	if os.Getenv("GEMINI_API_KEY") != "" {
		testAgentWithAPIKey(baseURL, headers)
	} else {
		fmt.Println("\n--- Skipping testAgentWithAPIKey: GEMINI_API_KEY not set ---")
		testAgentWithoutAPIKey(baseURL, headers)
	}
}
