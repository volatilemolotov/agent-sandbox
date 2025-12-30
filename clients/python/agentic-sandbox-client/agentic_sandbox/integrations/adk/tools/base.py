from typing import (
    Callable,
    Any,
    Optional,
)

from google.adk.tools import FunctionTool

from agentic_sandbox.integrations.sandbox_settings import SandboxSettings
from agentic_sandbox.integrations.base import with_sandbox


class SandboxFunctionTool(FunctionTool):
    """
    A subclass of ADK's FunctionTool that can interact with Agent Sandbox.
    The 'func' function has to  

    """
    def __init__(
        self,
        sandbox_settings: SandboxSettings,
        func: Callable[..., Any],
        description: Optional[str] = None,

    ):

        func_with_sandbox = with_sandbox(sandbox_settings)(func)
        if description:
            func_with_sandbox.__doc__ = description

        super().__init__(func_with_sandbox)


class SandboxTool(SandboxFunctionTool):
    """
    A variation of the ADK sandbox class that accepts tool function as a class attribute.
    """
    func: Callable[..., Any]
    description: Optional[str] = None

    def __init__(
        self,
        sandbox_settings: SandboxSettings,
    ):
       super().__init__(
            sandbox_settings,
            self.__class__.func,
            description=self.__class__.description,
        )
