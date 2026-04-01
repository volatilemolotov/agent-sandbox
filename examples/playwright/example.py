import sys
from k8s_agent_sandbox import SandboxClient

with SandboxClient(template_name="playwright-template", namespace="default") as sandbox:
    target_url = sys.argv[1]

    result = sandbox.run(f"python3 /app/search.py '{target_url}'")

    print("--- STDOUT ---")
    print(result.stdout)
    print("--- STDERR ---")
    print(result.stderr)
    print("--- EXIT CODE ---")
    print(result.exit_code)
