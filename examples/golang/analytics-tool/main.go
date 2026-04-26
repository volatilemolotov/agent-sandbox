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

// analytics-tool is an HTTP API server for executing analytics commands and
// managing files in a secure sandbox, mirroring the Python analytics-tool
// FastAPI example. Commands are restricted to an allow-list.
//
// Endpoints:
//
//	GET  /                   health check
//	POST /execute            run an allow-listed command, returns stdout/stderr/exit_code
//	POST /upload             upload a file (multipart/form-data)
//	GET  /download/{path...} download a file
package main

import (
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
)

const baseDir = "/tmp"

var allowedCommands = map[string]bool{
	"ls":     true,
	"echo":   true,
	"cat":    true,
	"grep":   true,
	"pwd":    true,
	"zip":    true,
	"unzip":  true,
	"mv":     true,
	"curl":   true,
	"python": true,
}

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

type executeRequest struct {
	Command string `json:"command"`
}

type executeResponse struct {
	Stdout   string `json:"stdout"`
	Stderr   string `json:"stderr"`
	ExitCode int    `json:"exit_code"`
}

func handleExecute(w http.ResponseWriter, r *http.Request) {
	var req executeRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeJSON(w, http.StatusBadRequest, executeResponse{Stderr: "invalid request body", ExitCode: 1})
		return
	}
	if req.Command == "" {
		writeJSON(w, http.StatusOK, executeResponse{Stderr: "no command provided", ExitCode: 1})
		return
	}

	// Split on the first space to extract the executable name for allow-list
	// checking. The full command is then executed via sh -c.
	parts := strings.Fields(req.Command)
	executable := parts[0]
	if !allowedCommands[executable] {
		allowed := make([]string, 0, len(allowedCommands))
		for k := range allowedCommands {
			allowed = append(allowed, k)
		}
		writeJSON(w, http.StatusOK, executeResponse{
			Stderr:   fmt.Sprintf("Forbidden command: %q. Only %v are allowed.", executable, allowed),
			ExitCode: 1,
		})
		return
	}

	cmd := exec.Command("sh", "-c", req.Command)
	cmd.Dir = baseDir

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
			writeJSON(w, http.StatusOK, executeResponse{
				Stderr:   fmt.Sprintf("failed to execute command: %v", err),
				ExitCode: 1,
			})
			return
		}
	}
	writeJSON(w, http.StatusOK, executeResponse{
		Stdout:   stdout.String(),
		Stderr:   stderr.String(),
		ExitCode: exitCode,
	})
}

func handleUpload(w http.ResponseWriter, r *http.Request) {
	if err := r.ParseMultipartForm(32 << 20); err != nil {
		writeJSON(w, http.StatusBadRequest, map[string]string{"message": "failed to parse multipart form: " + err.Error()})
		return
	}
	file, header, err := r.FormFile("file")
	if err != nil {
		writeJSON(w, http.StatusBadRequest, map[string]string{"message": "missing file field: " + err.Error()})
		return
	}
	defer file.Close()

	log.Printf("UPLOAD_FILE CALLED: Attempting to save %q", header.Filename)
	dst, err := os.Create(filepath.Join(baseDir, header.Filename))
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, map[string]string{"message": "file upload failed: " + err.Error()})
		return
	}
	defer dst.Close()
	if _, err := io.Copy(dst, file); err != nil {
		writeJSON(w, http.StatusInternalServerError, map[string]string{"message": "file upload failed: " + err.Error()})
		return
	}
	writeJSON(w, http.StatusOK, map[string]string{
		"message": fmt.Sprintf("File %q uploaded successfully.", header.Filename),
	})
}

func handleDownload(w http.ResponseWriter, r *http.Request) {
	filePath := r.PathValue("path")
	full := filepath.Join(baseDir, filePath)
	info, err := os.Stat(full)
	if err != nil || !info.Mode().IsRegular() {
		writeJSON(w, http.StatusNotFound, map[string]string{"message": "File not found"})
		return
	}
	w.Header().Set("Content-Disposition", fmt.Sprintf("attachment; filename=%q", filepath.Base(full)))
	w.Header().Set("Content-Type", "application/octet-stream")
	http.ServeFile(w, r, full)
}

func main() {
	mux := http.NewServeMux()
	mux.HandleFunc("GET /", handleHealth)
	mux.HandleFunc("POST /execute", handleExecute)
	mux.HandleFunc("POST /upload", handleUpload)
	mux.HandleFunc("GET /download/{path...}", handleDownload)

	addr := ":8080"
	log.Printf("Analytics Tool listening on %s", addr)
	if err := http.ListenAndServe(addr, mux); err != nil {
		log.Fatal(err)
	}
}
