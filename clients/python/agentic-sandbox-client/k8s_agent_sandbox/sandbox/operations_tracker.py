import threading
import asyncio
import inspect
from functools import wraps


class OperationsTracker:
    def __init__(self) -> None:
        self._cv = threading.Condition(threading.Lock())
        self._count = 0

        self._draining = False

    def add_one(self):
        with self._cv:
            if self._draining:
                raise RuntimeError("Cannot perform an operation on sandbox shutdown.")

            self._count += 1

    def remove_one(self):
        with self._cv:
            if self._count == 0:
                raise RuntimeError("The tracked operations counter cannot be negative.")
            self._count -= 1
            if self._count == 0:
                self._cv.notify_all()

    def wait_for_drain(self):
        with self._cv:
            self._draining = True
            self._cv.wait()


class AsyncOperationsTracker:
    def __init__(self) -> None:
        self._cv = asyncio.Condition(asyncio.Lock())
        self._count = 0

        self._draining = False

    async def add_one(self):
        async with self._cv:
            if self._draining:
                raise RuntimeError("Cannot perform an operation on sandbox shutdown.")

            self._count += 1

    async def remove_one(self):
        async with self._cv:
            if self._count == 0:
                raise RuntimeError("The tracked operations counter cannot be negative.")
            self._count -= 1
            if self._count == 0:
                self._cv.notify_all()

    async def wait_for_drain(self):
        async with self._cv:
            self._draining = True
            await self._cv.wait()


def track_op(func):
    if inspect.iscoroutinefunction(func):
        async def async_wrapper(self, *args, **kwargs):
            tracker: AsyncOperationsTracker = self.op_tracker
            await tracker.add_one()
            try:
                return await func(*args, **kwargs)
            finally:
                await tracker.remove_one()
        wrapper = async_wrapper
    else:
        def sync_wrapper(self, *args, **kwargs):
            tracker: OperationsTracker = self.op_tracker
            tracker.add_one()
            try:
                return func(*args, **kwargs)
            finally:
                tracker.remove_one()

        wrapper = sync_wrapper

    return wraps(func)(wrapper)

