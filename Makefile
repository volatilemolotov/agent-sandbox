.PHONY: all
all: fix-go-generate build

.PHONY: fix-go-generate
fix-go-generate:
	dev/tools/fix-go-generate

.PHONY: build
build:
	go build -o bin/manager cmd/agent-sandbox-controller/main.go
