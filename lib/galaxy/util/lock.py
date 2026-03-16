"""
This module provides a cross-database lock mechanism for Galaxy processes.
It supports PostgreSQL advisory locks and filesystem locks for non-PostgreSQL
databases (e.g., SQLite for testing). The module maintains file handles for
file locks to ensure proper locking behavior.
"""

import fcntl
import sqlalchemy as sa

# Dictionary to store open file handles for file-based locks
_LOCK_HANDLES = {}


def try_lock(session, lock_id):
    """
    Attempt to acquire a lock identified by `lock_id` using the given SQLAlchemy
    session.

    - For PostgreSQL, uses pg_try_advisory_lock (non-blocking).
    - For other databases, uses an exclusive non-blocking filesystem lock in /tmp.

    Returns True if the lock was successfully acquired, False otherwise.
    """
    if session.bind.dialect.name == "postgresql":
        return session.execute(
            sa.text("SELECT pg_try_advisory_lock(:id)"),
            {"id": lock_id},
        ).scalar()

    try:
        lock_path = f"/tmp/galaxy_lock_{lock_id}.lock"
        f = open(lock_path, "w")
        fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        _LOCK_HANDLES[lock_id] = f
        return True
    except (BlockingIOError, IOError):
        return False


def unlock(session, lock_id):
    """
    Release a previously acquired lock identified by `lock_id`.

    - For PostgreSQL, calls pg_advisory_unlock.
    - For file-based locks, releases the flock and closes the file handle.
    """
    if session.bind.dialect.name == "postgresql":
        session.execute(
            sa.text("SELECT pg_advisory_unlock(:id)"),
            {"id": lock_id},
        )
        return

    f = _LOCK_HANDLES.pop(lock_id, None)
    if f:
        try:
            fcntl.flock(f, fcntl.LOCK_UN)
        finally:
            f.close()