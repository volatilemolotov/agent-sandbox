from k8s_agent_sandbox import SandboxClient

with SandboxClient(template_name="playwright-template", namespace="default") as sandbox:
    result = sandbox.run("https://kubernetes.io")

    print("--- STDOUT ---")
    print(result.stdout)
    print("--- STDERR ---")
    print(result.stderr)
    print("--- EXIT CODE ---")
    print(result.exit_code)
