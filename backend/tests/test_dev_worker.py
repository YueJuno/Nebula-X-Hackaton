import inspect

from app.workers import dev


def test_dev_worker_uses_supported_watchfiles_arguments(monkeypatch):
    signature = inspect.signature(dev.run_process)
    calls = []

    def watch(*args, **kwargs):
        signature.bind(*args, **kwargs)
        calls.append((args, kwargs))
        return 0

    monkeypatch.delenv("WATCHFILES_FORCE_POLLING", raising=False)
    monkeypatch.setattr(dev, "run_process", watch)
    assert dev.start_dev_worker() == 0
    assert len(calls) == 1
    assert calls[0][1]["target"] is dev.main
    import os

    assert os.environ["WATCHFILES_FORCE_POLLING"] == "true"
