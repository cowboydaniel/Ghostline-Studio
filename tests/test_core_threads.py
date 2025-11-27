from __future__ import annotations

import concurrent.futures

import pytest

from ghostline.core.threads import BackgroundWorkers


class ImmediateExecutor:
    def __init__(self, *args, **kwargs) -> None:  # noqa: ANN002, ANN003
        self.submissions: list[tuple[callable, tuple, dict]] = []

    def submit(self, func, *args, **kwargs):  # noqa: ANN001, ANN002, ANN003
        self.submissions.append((func, args, kwargs))
        future: concurrent.futures.Future = concurrent.futures.Future()
        try:
            result = func(*args, **kwargs)
            future.set_result(result)
        except Exception as exc:  # noqa: BLE001
            future.set_exception(exc)
        return future

    def shutdown(self, wait: bool = False) -> None:  # noqa: ARG002
        return None


def test_submit_replaces_existing(monkeypatch) -> None:
    calls: list[str] = []
    monkeypatch.setattr(concurrent.futures, "ThreadPoolExecutor", ImmediateExecutor)

    workers = BackgroundWorkers()
    first = workers.submit("job", calls.append, "first")
    second = workers.submit("job", calls.append, "second")

    assert calls == ["first", "second"]
    assert first.done() and second.done()

    workers.shutdown()


def test_shutdown_cancels_pending(monkeypatch) -> None:
    monkeypatch.setattr(concurrent.futures, "ThreadPoolExecutor", ImmediateExecutor)

    workers = BackgroundWorkers()
    future = workers.submit("job", lambda: "done")
    assert future.done()

    # shutdown should clear the task registry without raising
    workers.shutdown()
    assert workers._tasks == {}


@pytest.mark.parametrize("key", ["alpha", "beta"])
def test_cancel_handles_missing_tasks(monkeypatch, key: str) -> None:
    monkeypatch.setattr(concurrent.futures, "ThreadPoolExecutor", ImmediateExecutor)
    workers = BackgroundWorkers()
    workers.cancel(key)
    workers.shutdown()
