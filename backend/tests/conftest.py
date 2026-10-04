"""Test configuration and shared fixtures.

The point of this file is that the checks in `tests/` must be runnable by
someone who was not in the room when the bugs were found. Several shipped
features turned out to have no database migration at all, which is exactly what
a test suite prevents.
"""
import os
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

# Tests that touch money must not be able to mint a real delivery code. A fixed
# value keeps hashing deterministic; it is a test fixture, never a deployment
# value, and app/core/config.py refuses to hash without the real pepper set in
# the environment.
os.environ.setdefault("DELIVERY_OTP_PEPPER", "test-pepper-not-used-in-production")
os.environ.setdefault("DISTANCE_PROVIDER", "osrm")

import pytest  # noqa: E402


@pytest.fixture
def money():
    from decimal import Decimal

    return Decimal