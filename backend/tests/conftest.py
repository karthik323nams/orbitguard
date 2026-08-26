import os
import pytest
from pathlib import Path

# Set test database path before importing any db elements
test_db_path = Path(__file__).resolve().parent / "orbitguard_test.db"
os.environ["ORBITGUARD_DB_PATH"] = str(test_db_path)

@pytest.fixture(scope="session", autouse=True)
def cleanup_test_db():
    yield
    # Delete the test database after the test session
    for suffix in ["", "-shm", "-wal"]:
        p = test_db_path.parent / (test_db_path.name + suffix)
        if p.exists():
            try:
                p.unlink()
            except OSError:
                pass

