"""
This module provides a cross-database lock mechanism for Galaxy processes.
It supports PostgreSQL advisory locks and filesystem locks for non-PostgreSQL
databases (e.g., SQLite for testing). The module maintains file handles for
file locks to ensure proper locking behavior.
"""

import fcntl
import time

import sqlalchemy as sa

# Dictionary to store open file handles for file-based locks
_LOCK_HANDLES = {}

# How long to sleep between attempts when waiting for a lock
RETRY_INTERVAL = 0.1


def try_lock(session, lock_id, timeout=0):
    """
    Attempt to acquire a lock identified by `lock_id` using the given SQLAlchemy
    session.

    - For PostgreSQL, uses pg_try_advisory_lock (non-blocking).
    - For other databases, uses an exclusive non-blocking filesystem lock in /tmp.

    If `timeout` is greater than zero, keep retrying for up to that many seconds
    before giving up, rather than returning as soon as the lock is unavailable.

    Returns True if the lock was successfully acquired, False otherwise.
    """
    deadline = time.monotonic() + timeout
    while True:
        if _try_acquire(session, lock_id):
            return True
        if time.monotonic() + RETRY_INTERVAL > deadline:
            return False
        time.sleep(RETRY_INTERVAL)


def _try_acquire(session, lock_id):
    if session.bind.dialect.name == "postgresql":
        return session.execute(
            sa.text("SELECT pg_try_advisory_xact_lock(:id)"),
            {"id": lock_id},
        ).scalar()

    lock_path = f"/tmp/galaxy_lock_{lock_id}.lock"
    f = open(lock_path, "w")
    try:
        fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except (BlockingIOError, IOError):
        f.close()
        return False
    _LOCK_HANDLES[lock_id] = f
    return True


def unlock(session, lock_id):
    """
    Release a previously acquired lock identified by `lock_id`.

    - For PostgreSQL, calls pg_advisory_unlock.
    - For file-based locks, releases the flock and closes the file handle.
    """
    if session.bind.dialect.name == "postgresql":
        session.commit()  # commit to make sure the lock is released
        return

    f = _LOCK_HANDLES.pop(lock_id, None)
    if f:
        try:
            fcntl.flock(f, fcntl.LOCK_UN)
        finally:
            f.close()
