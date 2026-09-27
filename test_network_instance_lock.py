from multiprocessing import Process, Queue

import pytest

from backend.services.network.instance_lock import instance_lock


def _attempt(path, queue):
    try:
        with instance_lock(path):
            queue.put("acquired")
    except RuntimeError:
        queue.put("busy")


def test_two_supervisors_cannot_share_a_lock_and_crash_releases_it(tmp_path):
    lock = tmp_path / "single.lock"
    queue = Queue()
    with instance_lock(lock):
        child = Process(target=_attempt, args=(lock, queue))
        child.start()
        child.join(timeout=5)
        if child.is_alive():
            child.terminate()
            child.join(timeout=5)
            pytest.fail("Lock contention process hung")
        assert queue.get(timeout=2) == "busy"
    with instance_lock(lock):
        pass
