from crewai.tools import BaseTool

from agentic_sandbox.integrations.sandbox_utils import SandboxSettings


class CrewAISandboxTool(BaseTool):
    def __init__(self, sandbox_settings: SandboxSettings, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._sandbox_settings = sandbox_settings

