import time
from collections import deque
from typing import Callable, TypeVar

import httpx

T = TypeVar("T")


def _is_outage(exc: Exception) -> bool:
    """Network errors and 5xx responses mean the provider is struggling. A 4xx
    is about one request (bad reference, invalid phone), so it must not open
    the circuit for everyone else."""
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code >= 500
    return isinstance(exc, httpx.TransportError)


class CircuitBreaker:
    """Minimal circuit breaker for external HTTP calls.

    Opens after `failure_threshold` consecutive failures within `window_seconds`,
    stays open for `cooldown_seconds`, then allows one probe request through.
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        window_seconds: float = 60.0,
        cooldown_seconds: float = 30.0,
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.window_seconds = window_seconds
        self.cooldown_seconds = cooldown_seconds
        self.failures: deque[float] = deque()
        self.opened_at: float = 0.0
        self._last_exception: Exception | None = None

    @property
    def is_open(self) -> bool:
        if self.opened_at and time.monotonic() - self.opened_at < self.cooldown_seconds:
            return True
        if self.opened_at and time.monotonic() - self.opened_at >= self.cooldown_seconds:
            self._reset()
        return False

    def record_failure(self, exc: Exception) -> None:
        self._last_exception = exc
        now = time.monotonic()
        self.failures.append(now)
        self._prune(now)
        if len(self.failures) >= self.failure_threshold:
            self.opened_at = now

    def record_success(self) -> None:
        self._reset()

    def call(self, func: Callable[[], T], fallback: Callable[[], T] | None = None) -> T:
        if self.is_open:
            if fallback is not None:
                return fallback()
            raise RuntimeError(f"Circuit breaker {self.name} is open")
        try:
            result = func()
            self.record_success()
            return result
        except Exception as exc:
            if not _is_outage(exc):
                raise
            self.record_failure(exc)
            if fallback is not None:
                return fallback()
            raise

    def _reset(self) -> None:
        self.failures.clear()
        self.opened_at = 0.0
        self._last_exception = None

    def _prune(self, now: float) -> None:
        while self.failures and now - self.failures[0] > self.window_seconds:
            self.failures.popleft()


mpesa_circuit = CircuitBreaker("mpesa")
paystack_circuit = CircuitBreaker("paystack")
ors_circuit = CircuitBreaker("openrouteservice")
resend_circuit = CircuitBreaker("resend")
