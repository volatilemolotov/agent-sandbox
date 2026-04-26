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

// runtime-sandbox is an HTTP API server for executing commands and managing
// files inside a secure sandbox, mirroring the Python python-runtime-sandbox
// FastAPI example.
//
// Endpoints:
//
//	GET  /                        health check
//	POST /execute                 run a shell command, returns stdout/stderr/exit_code
//	POST /upload                  upload a file (multipart/form-data)
//	GET  /download/{path...}      download a file
//	GET  /list/{path...}          list directory contents
//	GET  /exists/{path...}        check whether a path exists
//
// All file paths are sandboxed to /app to prevent traversal attacks.
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
	"time"
)

const baseDir = "/"

// getSafePath resolves filePath relative to baseDir and returns an error if
// the result escapes baseDir (path traversal protection).
func getSafePath(filePath string) (string, error) {
	// Strip leading slashes so the path is treated as relative to baseDir.
	cleaned := strings.TrimLeft(filePath, "/")
	full := filepath.Clean(filepath.Join(baseDir, cleaned))
	if full != baseDir && !strings.HasPrefix(full, baseDir+string(filepath.Separator)) {
		return "", errors.New("access denied: path must be within /app")
	}
	return full, nil
}

func writeJSON(w http.ResponseWriter, status int, v any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(v)
}

// --- handlers ---

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

	// Use "sh -c" to support shell syntax while avoiding manual argument
	// splitting, which matches the safety profile of the Python shlex.split
	// approach when the command is treated as a single shell expression.
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
	rawPath := r.PathValue("path")
	full, err := getSafePath(rawPath)
	if err != nil {
		writeJSON(w, http.StatusForbidden, map[string]string{"message": "Access denied"})
		return
	}
	info, err := os.Stat(full)
	if err != nil || !info.Mode().IsRegular() {
		writeJSON(w, http.StatusNotFound, map[string]string{"message": "File not found"})
		return
	}
	w.Header().Set("Content-Disposition", fmt.Sprintf("attachment; filename=%q", filepath.Base(full)))
	w.Header().Set("Content-Type", "application/octet-stream")
	http.ServeFile(w, r, full)
}

type fileEntry struct {
	Name    string  `json:"name"`
	Size    int64   `json:"size"`
	Type    string  `json:"type"`
	ModTime float64 `json:"mod_time"`
}

func handleList(w http.ResponseWriter, r *http.Request) {
	rawPath := r.PathValue("path")
	full, err := getSafePath(rawPath)
	if err != nil {
		writeJSON(w, http.StatusForbidden, map[string]string{"message": "Access denied"})
		return
	}
	entries, err := os.ReadDir(full)
	if err != nil {
		if errors.Is(err, os.ErrNotExist) {
			writeJSON(w, http.StatusNotFound, map[string]string{"message": "Path is not a directory"})
		} else {
			writeJSON(w, http.StatusInternalServerError, map[string]string{"message": "list files failed: " + err.Error()})
		}
		return
	}

	var result []fileEntry
	for _, e := range entries {
		info, err := e.Info()
		if err != nil {
			continue
		}
		kind := "file"
		if e.IsDir() {
			kind = "directory"
		}
		result = append(result, fileEntry{
			Name:    e.Name(),
			Size:    info.Size(),
			Type:    kind,
			ModTime: float64(info.ModTime().UnixNano()) / float64(time.Second),
		})
	}
	if result == nil {
		result = []fileEntry{}
	}
	writeJSON(w, http.StatusOK, result)
}

func handleExists(w http.ResponseWriter, r *http.Request) {
	rawPath := r.PathValue("path")
	full, err := getSafePath(rawPath)
	if err != nil {
		writeJSON(w, http.StatusForbidden, map[string]string{"message": "Access denied"})
		return
	}
	_, statErr := os.Stat(full)
	writeJSON(w, http.StatusOK, map[string]any{
		"path":   strings.TrimLeft(rawPath, "/"),
		"exists": statErr == nil,
	})
}

func main() {
	mux := http.NewServeMux()
	mux.HandleFunc("GET /", handleHealth)
	mux.HandleFunc("POST /execute", handleExecute)
	mux.HandleFunc("POST /upload", handleUpload)
	mux.HandleFunc("GET /download/{path...}", handleDownload)
	mux.HandleFunc("GET /list/{path...}", handleList)
	mux.HandleFunc("GET /exists/{path...}", handleExists)

	addr := ":8080"
	log.Printf("Sandbox Runtime listening on %s", addr)
	if err := http.ListenAndServe(addr, mux); err != nil {
		log.Fatal(err)
	}
}
