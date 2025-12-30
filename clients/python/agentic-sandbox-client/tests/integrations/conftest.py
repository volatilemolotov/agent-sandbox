import pytest

from agentic_sandbox.integrations.sandbox_settings import SandboxSettings


@pytest.fixture(scope="session")
def python_sandbox_settings() -> SandboxSettings:
    return SandboxSettings(
        template_name="python-sandbox-template",
        namespace="default",
    )

