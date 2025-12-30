import dataclasses
from functools import wraps

from .sandbox_settings import SandboxSettings


@dataclasses.dataclass
class SandboxExtraParam:
    settings: SandboxSettings


def with_sandbox(sandbox_settings):
    """
    Decorator that injects additional keyword argument named ``sandbox`` to the original function.

    The 'sandbox' argument is an instance of the ``SandboxExtraParam``.

    The original function can use the 'sandbox' argument to interact with Agent Sandbox.

    Args:
        sandbox_settings: Sandbox settings to be passed to the original function inside the 'sandbox' keyword argument
    """

    extra_param = SandboxExtraParam(
        sandbox_settings,
    )

    def _create_wrapper(func):

        @wraps(func)
        def _wrapper(*args, **kwargs):

            updated_kwargs = kwargs.copy()
            updated_kwargs["sandbox"] = extra_param
            return func(*args, **updated_kwargs) 

        return _wrapper

    return _create_wrapper
