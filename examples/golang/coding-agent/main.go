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

// coding-agent is an interactive code-generation loop that mirrors the Python
// LangGraph coding agent example. It uses the Anthropic Claude API in place of
// a local HuggingFace model and LangGraph, implementing the same
// generate → execute → fix state machine.
//
// Requirements:
//
//	ANTHROPIC_API_KEY  Anthropic API key (required)
//
// Usage:
//
//	go run . [-- task description]
//
// If no task is provided on the command line, the agent runs in interactive
// REPL mode.
package main

import (
	"bufio"
	"bytes"
	"context"
	"errors"
	"fmt"
	"os"
	"os/exec"
	"strings"
	"time"

	"github.com/anthropics/anthropic-sdk-go"
	"github.com/anthropics/anthropic-sdk-go/option"
)

const (
	model         = "claude-haiku-4-5-20251001"
	maxIterations = 3
	execTimeout   = 60 * time.Second
)

// agentState mirrors the TypedDict in the Python version.
type agentState struct {
	userRequest     string
	generatedCode   string
	executionResult string
	errorMessage    string
	iterationCount  int
	status          string // planning | coding | executing | fixing | completed | failed
}

// --- LLM ---

type codingLLM struct {
	client *anthropic.Client
}

func newCodingLLM() (*codingLLM, error) {
	key := os.Getenv("ANTHROPIC_API_KEY")
	if key == "" {
		return nil, errors.New("ANTHROPIC_API_KEY environment variable not set")
	}
	return &codingLLM{
		client: anthropic.NewClient(option.WithAPIKey(key)),
	}, nil
}

func (l *codingLLM) generateCode(ctx context.Context, task string) (string, error) {
	prompt := fmt.Sprintf(`You are an expert programmer. Generate clean, executable Python code for the following task.
Your code must be completely self-contained with no external dependencies.
Include proper error handling and print informative output.
Output ONLY executable Python code, no markdown, no explanations, no backticks.

Task: %s

Python code:`, task)

	return l.complete(ctx, prompt)
}

func (l *codingLLM) fixCode(ctx context.Context, task, code, errMsg string) (string, error) {
	prompt := fmt.Sprintf(`You are debugging code. The code failed with an error. Fix the code to resolve the error.
Output ONLY the corrected Python code, no markdown, no explanations, no backticks.

Original Task: %s

Failed code:
%s

Error:
%s

Fixed Python code:`, task, code, errMsg)

	return l.complete(ctx, prompt)
}

func (l *codingLLM) complete(ctx context.Context, prompt string) (string, error) {
	msg, err := l.client.Messages.New(ctx, anthropic.MessageNewParams{
		Model:     anthropic.F(anthropic.Model(model)),
		MaxTokens: anthropic.F(int64(1024)),
		Messages: anthropic.F([]anthropic.MessageParam{
			anthropic.NewUserMessage(anthropic.NewTextBlock(prompt)),
		}),
	})
	if err != nil {
		return "", fmt.Errorf("LLM call: %w", err)
	}
	if len(msg.Content) == 0 {
		return "", errors.New("LLM returned empty response")
	}
	raw := msg.Content[0].Text
	return cleanCode(raw), nil
}

// cleanCode strips markdown fences, matching the Python _clean_code helper.
func cleanCode(code string) string {
	code = strings.TrimSpace(code)
	if strings.HasPrefix(code, "```python") {
		code = strings.TrimPrefix(code, "```python")
	} else if strings.HasPrefix(code, "```") {
		code = strings.TrimPrefix(code, "```")
	}
	code = strings.TrimSuffix(strings.TrimSpace(code), "```")
	return strings.TrimSpace(code)
}

// --- Code executor ---

func executeCode(code string) (output string, success bool) {
	const tmpFile = "/tmp/agent_code.py"
	if err := os.WriteFile(tmpFile, []byte(code), 0o600); err != nil {
		return fmt.Sprintf("write temp file: %v", err), false
	}

	ctx, cancel := context.WithTimeout(context.Background(), execTimeout)
	defer cancel()

	cmd := exec.CommandContext(ctx, "python3", tmpFile)
	var stdout, stderr bytes.Buffer
	cmd.Stdout = &stdout
	cmd.Stderr = &stderr

	err := cmd.Run()
	if err == nil {
		return stdout.String(), true
	}
	if errors.Is(ctx.Err(), context.DeadlineExceeded) {
		return fmt.Sprintf("Execution timeout (%s)", execTimeout), false
	}
	combined := stderr.String()
	if combined == "" {
		combined = err.Error()
	}
	return combined, false
}

// --- Agent loop ---

func runAgent(ctx context.Context, llm *codingLLM, task string) agentState {
	state := agentState{
		userRequest:    task,
		iterationCount: 0,
		status:         "planning",
	}

	// Generate initial code.
	fmt.Println("\nGenerating code...")
	code, err := llm.generateCode(ctx, task)
	if err != nil {
		state.status = "failed"
		state.executionResult = fmt.Sprintf("code generation failed: %v", err)
		return state
	}
	state.generatedCode = code
	fmt.Printf("Code generated (%d chars)\n", len(code))

	for {
		// Execute.
		fmt.Println("Executing code...")
		output, ok := executeCode(state.generatedCode)
		if ok {
			fmt.Println("Execution successful")
			state.executionResult = output
			state.errorMessage = ""
			state.status = "completed"
			return state
		}

		fmt.Println("Execution failed")
		state.executionResult = output
		state.errorMessage = output
		state.iterationCount++

		if state.iterationCount >= maxIterations {
			state.status = "failed"
			state.executionResult = fmt.Sprintf("Max iterations reached (%d)", maxIterations)
			return state
		}

		// Fix.
		fmt.Printf("Fixing code (attempt %d/%d)...\n", state.iterationCount, maxIterations)
		fixed, err := llm.fixCode(ctx, task, state.generatedCode, state.errorMessage)
		if err != nil {
			state.status = "failed"
			state.executionResult = fmt.Sprintf("code fix failed: %v", err)
			return state
		}
		state.generatedCode = fixed
		fmt.Printf("Code fixed (%d chars)\n", len(fixed))
	}
}

// --- REPL ---

func interactiveChat(ctx context.Context, llm *codingLLM) {
	sep := strings.Repeat("=", 80)
	fmt.Println(sep)
	fmt.Println("LangGraph-style Coding Agent (Anthropic Claude)")
	fmt.Println(sep)
	fmt.Println("I can help you write and execute Python code.")
	fmt.Println("Commands: 'exit', 'quit', or Ctrl+C to quit")
	fmt.Println(sep)

	scanner := bufio.NewScanner(os.Stdin)
	for {
		fmt.Printf("\n%s\nYou: ", sep)
		if !scanner.Scan() {
			break
		}
		input := strings.TrimSpace(scanner.Text())
		if input == "" {
			continue
		}
		if input == "exit" || input == "quit" {
			fmt.Println("\nGoodbye!")
			return
		}

		fmt.Println()
		result := runAgent(ctx, llm, input)

		fmt.Printf("\n%s\nGenerated Code:\n%s\n%s\n",
			sep, strings.Repeat("-", 80), result.generatedCode)
		fmt.Printf("\n%s\nExecution Result:\n%s\n%s\n%s\n",
			sep, strings.Repeat("-", 80), result.executionResult, sep)

		if result.status == "failed" {
			fmt.Printf("\nStatus: FAILED (tried %d times)\n", result.iterationCount)
		} else {
			fmt.Printf("\nStatus: %s\n", strings.ToUpper(result.status))
			if result.iterationCount > 0 {
				fmt.Printf("   (Fixed after %d attempts)\n", result.iterationCount)
			}
		}
	}
}

func main() {
	llm, err := newCodingLLM()
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error: %v\n", err)
		os.Exit(1)
	}

	ctx := context.Background()

	// If a task is provided as a command-line argument, run once and exit.
	if len(os.Args) > 1 {
		task := strings.Join(os.Args[1:], " ")
		result := runAgent(ctx, llm, task)
		fmt.Println("\nGenerated Code:")
		fmt.Println(strings.Repeat("-", 80))
		fmt.Println(result.generatedCode)
		fmt.Println("\nExecution Result:")
		fmt.Println(strings.Repeat("-", 80))
		fmt.Println(result.executionResult)
		if result.status == "failed" {
			fmt.Fprintf(os.Stderr, "Status: FAILED (tried %d times)\n", result.iterationCount)
			os.Exit(1)
		}
		fmt.Printf("Status: %s\n", strings.ToUpper(result.status))
		return
	}

	interactiveChat(ctx, llm)
}
