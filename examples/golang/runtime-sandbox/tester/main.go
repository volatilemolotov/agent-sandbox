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

// tester is an integration test client for the runtime-sandbox HTTP server.
//
// Usage:
//
//	go run ./tester <server_ip> <server_port>
package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"net/url"
	"os"
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

func get(baseURL, path string) (int, []byte) {
	resp, err := http.Get(baseURL + path)
	if err != nil {
		log.Fatalf("GET %s: %v", path, err)
	}
	defer resp.Body.Close()
	body, _ := io.ReadAll(resp.Body)
	return resp.StatusCode, body
}

func postJSON(baseURL, path string, payload any) (int, []byte) {
	resp, err := http.Post(baseURL+path, "application/json", bytes.NewReader(mustJSON(payload)))
	if err != nil {
		log.Fatalf("POST %s: %v", path, err)
	}
	defer resp.Body.Close()
	body, _ := io.ReadAll(resp.Body)
	return resp.StatusCode, body
}

func testHealthCheck(baseURL string) {
	fmt.Println("--- Testing Health Check endpoint ---")
	status, body := get(baseURL, "/")
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

func testExecute(baseURL string) {
	fmt.Println("\n--- Testing Execute endpoint ---")
	status, body := postJSON(baseURL, "/execute", map[string]string{"command": "echo 'hello world'"})
	if status != http.StatusOK {
		log.Fatalf("execute: expected 200, got %d", status)
	}
	var result map[string]any
	decodeJSON(body, &result)
	stdout, _ := result["stdout"].(string)
	if stdout != "hello world\n" {
		log.Fatalf("execute: expected stdout=%q, got %q", "hello world\n", stdout)
	}
	fmt.Println("Execute command successful!")
	fmt.Println("Response JSON:", string(body))
}

func testListFiles(baseURL string) {
	fmt.Println("\n--- Testing List Files endpoint ---")
	status, body := get(baseURL, "/list/.")
	if status != http.StatusOK {
		log.Fatalf("list files: expected 200, got %d", status)
	}
	var result []any
	decodeJSON(body, &result)
	fmt.Println("List files successful!")
	fmt.Println("Response JSON:", string(body))
}

func testExists(baseURL string) {
	fmt.Println("\n--- Testing Exists endpoint ---")

	status, body := get(baseURL, "/exists/.")
	if status != http.StatusOK {
		log.Fatalf("exists (.): expected 200, got %d", status)
	}
	var result map[string]any
	decodeJSON(body, &result)
	if result["exists"] != true {
		log.Fatalf("exists (.): expected exists=true, got %v", result["exists"])
	}
	fmt.Println("Exists check successful!")
	fmt.Println("Response JSON:", string(body))

	status, body = get(baseURL, "/exists/does_not_exist")
	if status != http.StatusOK {
		log.Fatalf("exists (missing): expected 200, got %d", status)
	}
	decodeJSON(body, &result)
	if result["exists"] != false {
		log.Fatalf("exists (missing): expected exists=false, got %v", result["exists"])
	}
	fmt.Println("Exists check (negative) successful!")
	fmt.Println("Response JSON:", string(body))
}

func testPathTraversal(baseURL string) {
	fmt.Println("\n--- Testing Path Traversal ---")
	encoded := url.PathEscape("../../etc/passwd")
	status, body := get(baseURL, "/exists/"+encoded)
	fmt.Printf("Response status code: %d\n", status)
	fmt.Println("Response JSON:", string(body))
	if status != http.StatusForbidden {
		log.Fatalf("path traversal: expected 403, got %d", status)
	}
	var result map[string]string
	decodeJSON(body, &result)
	if result["message"] != "Access denied" {
		log.Fatalf("path traversal: expected message=Access denied, got %q", result["message"])
	}
	fmt.Println("Path traversal blocked successfully!")
}

func testAbsolutePathTraversal(baseURL string) {
	fmt.Println("\n--- Testing Absolute Path Traversal ---")
	encoded := url.PathEscape("/../etc/passwd")
	status, body := get(baseURL, "/exists/"+encoded)
	fmt.Printf("Response status code: %d\n", status)
	fmt.Println("Response JSON:", string(body))
	if status != http.StatusForbidden {
		log.Fatalf("absolute path traversal: expected 403, got %d", status)
	}
	var result map[string]string
	decodeJSON(body, &result)
	if result["message"] != "Access denied" {
		log.Fatalf("absolute path traversal: expected message=Access denied, got %q", result["message"])
	}
	fmt.Println("Absolute path traversal blocked successfully!")
}

func main() {
	if len(os.Args) != 3 {
		fmt.Fprintf(os.Stderr, "Usage: %s <server_ip> <server_port>\n", os.Args[0])
		os.Exit(1)
	}
	baseURL := fmt.Sprintf("http://%s:%s", os.Args[1], os.Args[2])

	testHealthCheck(baseURL)
	testExecute(baseURL)
	testListFiles(baseURL)
	testExists(baseURL)
	testPathTraversal(baseURL)
	testAbsolutePathTraversal(baseURL)
}
