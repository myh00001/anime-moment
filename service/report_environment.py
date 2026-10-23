"""Keep a successful TROS environment in memory for subsequent photo helpers."""
import os
import subprocess
import threading
import time

_overlay = None
_lock = threading.Lock()


def helper_environment(deadline):
    global _overlay
    with _lock:
        if _overlay is None:
            left = deadline - time.monotonic()
            if left <= 0:
                return None
            base = os.environ.copy()
            try:
                raw = subprocess.check_output(
                    ['bash', '-c', 'source /opt/tros/humble/setup.bash >/dev/null && env -0'],
                    env=base, stderr=subprocess.DEVNULL, timeout=min(3, left))
                loaded = dict(os.fsdecode(item).split('=', 1)
                              for item in raw.split(b'\0') if b'=' in item)
                if not loaded.get('AMENT_PREFIX_PATH') or not loaded.get('PYTHONPATH'):
                    return None
                # Preserve current process variables; cache only the ROS overlay.
                _overlay = {key: value for key, value in loaded.items()
                            if base.get(key) != value and key not in ('_', 'SHLVL', 'PWD')}
            except (OSError, ValueError, subprocess.SubprocessError):
                return None
        return dict(os.environ, **_overlay)
