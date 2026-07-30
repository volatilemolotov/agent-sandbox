from .termination_fn import TermiinationFn


class SparseTaskTermination(TermiinationFn):
    """
    Returns True if obs["reward"] == 1 and False otherwise

    Example:
        termination_fn = SparseTaskTermination()
    """
    def __init__(self, success_fn):
        self.success_fn = success_fn

    def __call__(self, action, obs, info, task):
        return obs["reward"] == 1
