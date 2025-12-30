from agentic_sandbox import SandboxClient


class SandboxSettings:
    def __init__(
        self,
        template_name: str,
        namespace: str,
    ):
        self.template_name = template_name
        self.namespace = namespace

    def create_client(self) -> SandboxClient:
        return SandboxClient(
            template_name=self.template_name,
            namespace=self.namespace,
        )
    

