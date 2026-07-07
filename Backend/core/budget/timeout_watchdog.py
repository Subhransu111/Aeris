import threading
import functools

class TimeoutException(Exception):
    pass

def run_with_timeout(func, args=(), kwargs=None, timeout_seconds=900):
    """
    Runs func in a separate thread. If it exceeds timeout_seconds,
    raises TimeoutException. Caller is responsible for cleaning up
    any partial resources (container, temp dir) on timeout.
    """
    kwargs = kwargs or {}
    result = {}
    exception = {}

    def target():
        try:
            result["value"] = func(*args, **kwargs)
        except Exception as e:
            exception["error"] = e

    thread = threading.Thread(target=target, daemon=True)
    thread.start()
    thread.join(timeout=timeout_seconds)

    if thread.is_alive():
        raise TimeoutException(f"Operation exceeded {timeout_seconds}s timeout")

    if "error" in exception:
        raise exception["error"]

    return result.get("value")