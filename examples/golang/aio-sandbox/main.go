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

// aio-sandbox demonstrates basic usage of the k8s agent-sandbox Go SDK,
// mirroring the Python aio-sandbox example: run a shell command, read a file,
// and capture a browser screenshot via a headless Chromium subprocess.
package main

import (
	"context"
	"fmt"
	"log"
	"os"

	"sigs.k8s.io/agent-sandbox/clients/go/sandbox"
)

func envOrDefault(key, def string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return def
}

func main() {
	ctx := context.Background()

	opts := sandbox.Options{
		TemplateName: envOrDefault("SANDBOX_TEMPLATE", "aio-sandbox"),
		Namespace:    envOrDefault("SANDBOX_NAMESPACE", "default"),
	}
	// If GATEWAY_URL is set, use DirectStrategy (HTTP gateway) instead of
	// the default port-forward tunnel.
	if apiURL := os.Getenv("GATEWAY_URL"); apiURL != "" {
		opts.APIURL = apiURL
	}

	sb, err := sandbox.New(ctx, opts)
	if err != nil {
		log.Fatal(err)
	}
	defer sb.Close(context.Background())

	if err := sb.Open(ctx); err != nil {
		log.Fatal(err)
	}
	fmt.Printf("Sandbox ready: claim=%s sandbox=%s pod=%s\n",
		sb.ClaimName(), sb.SandboxName(), sb.PodName())

	// Run a shell command to list files (equivalent to client.shell.exec_command).
	result, err := sb.Run(ctx, "ls -la")
	if err != nil {
		log.Fatal(err)
	}
	fmt.Print(result.Stdout)

	// Read the .bashrc file (equivalent to client.file.read_file).
	data, err := sb.Read(ctx, ".bashrc")
	if err != nil {
		log.Printf("read .bashrc: %v", err)
	} else {
		fmt.Print(string(data))
	}

	// Take a screenshot via headless Chromium and retrieve the PNG bytes.
	// The Go SDK has no native browser API; we invoke Chromium as a subprocess
	// inside the sandbox and then download the resulting file.
	_, err = sb.Run(ctx,
		"chromium --headless --screenshot=/tmp/screenshot.png --window-size=1280,720 about:blank 2>/dev/null || true")
	if err != nil {
		log.Printf("screenshot command: %v", err)
	} else {
		png, err := sb.Read(ctx, "/tmp/screenshot.png")
		if err != nil {
			log.Printf("read screenshot: %v", err)
		} else {
			const screenshotPath = "sandbox_screenshot.png"
			if err := os.WriteFile(screenshotPath, png, 0o644); err != nil {
				log.Printf("write screenshot: %v", err)
			} else {
				fmt.Printf("Screenshot saved to %s\n", screenshotPath)
			}
		}
	}
}
