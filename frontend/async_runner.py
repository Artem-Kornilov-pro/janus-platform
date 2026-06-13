"""Background asyncio loop for running MCP calls without blocking the Qt UI."""

from __future__ import annotations

import asyncio
import threading
import uuid
from typing import Any, Awaitable, Callable

from PyQt6.QtCore import QObject, QThread, pyqtSignal


class AsyncRunner(QObject):
    """Runs coroutines on a dedicated background asyncio event loop.

    Results/errors are delivered back on the Qt main thread via the
    `finished` signal, keyed by the call_id returned from `submit`.
    """

    finished = pyqtSignal(str, object, object)  # call_id, result, error

    def __init__(self) -> None:
        super().__init__()
        self._loop = asyncio.new_event_loop()
        self._thread = QThread()
        self._thread.run = self._run_loop  # type: ignore[method-assign]
        self._thread.start()

    def _run_loop(self) -> None:
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    def submit(self, coro_factory: Callable[[], Awaitable[Any]]) -> str:
        """Schedule a coroutine, returning a call_id used to match the `finished` signal."""
        call_id = uuid.uuid4().hex

        def _runner() -> None:
            try:
                result = asyncio.run_coroutine_threadsafe(coro_factory(), self._loop).result()
                self.finished.emit(call_id, result, None)
            except Exception as exc:  # noqa: BLE001 - surface any error to the UI
                self.finished.emit(call_id, None, exc)

        threading.Thread(target=_runner, daemon=True).start()
        return call_id

    def shutdown(self) -> None:
        self._loop.call_soon_threadsafe(self._loop.stop)
        self._thread.quit()
        self._thread.wait(2000)
