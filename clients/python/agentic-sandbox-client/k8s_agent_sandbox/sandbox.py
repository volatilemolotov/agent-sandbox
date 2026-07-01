import importlib.metadata

if importlib.metadata.version("k8s_agent_sandbox") >= "6.0.0":
    raise ImportError("The module k8s_agent_sandbox.sandbox has been moved to k8s_agent_sandbox.sandbox.sync.")
else:
    import warnings

    warnings.warn(
        "The module 'k8s_agent_sandbox.sandbox' is deprecated and will be removed in version 6.0.0. "
        "Use k8s_agent_sandbox.sandbox.sync instead.",
        DeprecationWarning,
        stacklevel=2
    )

