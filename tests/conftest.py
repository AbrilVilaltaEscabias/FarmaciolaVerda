"""Test configuration.

The environment is forced BEFORE any model is imported, so the tests can
never touch the real database: they use an in-memory SQLite one.
"""
import os
from unittest.mock import MagicMock

import pytest

os.environ["ENVIRONMENT"] = "test"
os.environ["DB_URL_TEST"] = "sqlite://"


@pytest.fixture
def uow():
    """A fake unit of work with mocked repositories."""
    fake = MagicMock()
    fake.__enter__.return_value = fake
    fake.__exit__.return_value = False  # never swallow exceptions
    return fake


@pytest.fixture
def uow_factory(uow):
    return lambda: uow
