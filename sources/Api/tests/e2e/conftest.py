"""Pytest configuration for e2e tests."""
import pytest


def pytest_addoption(parser):
    """Add --snapshot-update option."""
    parser.addoption(
        "--snapshot-update",
        action="store_true",
        default=False,
        help="Update snapshot files instead of comparing",
    )


@pytest.fixture(scope="session")
def snapshot_update(request):
    """Return True if --snapshot-update was passed."""
    return request.config.getoption("--snapshot-update")
