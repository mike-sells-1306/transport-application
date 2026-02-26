"""
conftest.py — shared pytest configuration for the backend test suite.

Sets DATABASE_URL to an in-memory SQLite URI before any test module imports
app.py, preventing the module-level db.create_all() from touching the
file-based database (which may be on a networked drive where SQLite file
locking is unreliable).
"""

import os

# Must be set before `from app import ...` is executed by any test module.
os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("SECRET_KEY", "test-secret-key")
