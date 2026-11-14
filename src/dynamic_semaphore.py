from __future__ import annotations

import asyncio
import logging

logger = logging.getLogger("uvicorn.error")


class DynamicSemaphore:
    """
    An asynchronous semaphore that supports dynamic runtime resizing of its capacity.
    Utilizes an asyncio.Condition to coordinate tasks without busy-waiting.
    """

    def __init__(self, capacity: int) -> None:
        self._capacity: int = max(1, capacity)
        self._active_count: int = 0
        self._cond: asyncio.Condition | None = None

    @property
    def capacity(self) -> int:
        return self._capacity

    @property
    def active_count(self) -> int:
        return self._active_count

    def _get_cond(self) -> asyncio.Condition:
        if self._cond is None:
            self._cond = asyncio.Condition()
        return self._cond

    def set_capacity(self, new_capacity: int) -> int:
        """
        Dynamically adjusts the maximum concurrent capacity.
        Notifies waiting tasks if the capacity is expanded.
        """
        clamped = max(1, min(64, new_capacity))
        if clamped == self._capacity:
            return self._capacity

        old_capacity = self._capacity
        self._capacity = clamped
        logger.info(
            "DynamicSemaphore capacity adjusted from %d to %d (active tasks: %d).",
            old_capacity,
            clamped,
            self._active_count,
        )

        # Notify waiting tasks if more slots became available
        if clamped > old_capacity and self._cond is not None:
            async def _wake_waiters() -> None:
                assert self._cond is not None
                async with self._cond:
                    self._cond.notify_all()

            try:
                loop = asyncio.get_running_loop()
                loop.create_task(_wake_waiters())
            except RuntimeError:
                pass

        return self._capacity

    async def acquire(self) -> None:
        """Acquires a concurrency permit, suspending if active permits reached capacity."""
        cond = self._get_cond()
        async with cond:
            while self._active_count >= self._capacity:
                await cond.wait()
            self._active_count += 1

    async def release(self) -> None:
        """Releases an acquired concurrency permit and wakes a waiting task."""
        cond = self._get_cond()
        async with cond:
            self._active_count = max(0, self._active_count - 1)
            cond.notify()

    async def __aenter__(self) -> DynamicSemaphore:
        await self.acquire()
        return self

    async def __aexit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        await self.release()
