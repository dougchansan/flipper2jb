"""Share HBLauncher's durable one-shot REMOVE latch across command-line runs."""
import json
import os
from pathlib import Path


def latch_path():
    return Path(os.environ.get('HB_SESSION_LATCH', Path.home() / '.local/state/hblauncher/console-session.json'))


def claim():
    path = latch_path()
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as stream:
        json.dump({'pid': os.getpid(), 'restartRequired': True}, stream)
        stream.flush()
        os.fsync(stream.fileno())


def reset():
    path = latch_path()
    state = json.loads(path.read_text())
    try:
        os.kill(state['pid'], 0)
    except ProcessLookupError:
        path.unlink()
    else:
        raise ValueError('recorded host still running')
