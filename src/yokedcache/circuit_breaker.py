"""
Circuit breaker implementation for YokedCache.

This module provides a circuit breaker pattern to handle Redis connection failures
gracefully and prevent cascading failures in high-load scenarios.
"""

import asyncio
import functools
import logging
import time
from enum import Enum
from typing import Any, Callable, Optional, Tuple, Type, TypeVar, Union

logger = logging.getLogger(__name__)

T = TypeVar("T")


class CircuitBreakerState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, not allowing requests
    HALF_OPEN = "half_open"  # Testing if service is back


class CircuitBreakerError(Exception):
    """Raised when circuit breaker is open."""

    def __init__(self, message: str, state: CircuitBreakerState):
        super().__init__(message)
        self.state = state


class CircuitBreaker:
    """
    Circuit breaker for Redis operations.

    Prevents cascading failures by temporarily disabling Redis operations
    when failure rate exceeds threshold.
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        timeout: float = 60.0,
        expected_exception: Union[
            Type[Exception], Tuple[Type[Exception], ...]
        ] = Exception,
    ):
        """
        Initialize circuit breaker.

        Args:
            failure_threshold: Number of failures before opening circuit
            timeout: Time to wait before attempting reset (seconds)
            expected_exception: Exception type to count as failure
        """
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.expected_exception = expected_exception

        # State tracking
        self.failure_count = 0
        self.last_failure_time: Optional[float] = None
        self.state = CircuitBreakerState.CLOSED

        # Stats
        self.total_requests = 0
        self.total_failures = 0
        self.total_successes = 0

    def _should_attempt_reset(self) -> bool:
        """Check if we should attempt to reset the circuit."""
        if self.state != CircuitBreakerState.OPEN:
            return False

        if self.last_failure_time is None:
            return True

        return time.time() - self.last_failure_time >= self.timeout

    def _on_success(self) -> None:
        """Handle successful operation."""
        self.failure_count = 0
        self.total_successes += 1
        self.state = CircuitBreakerState.CLOSED

    def _on_failure(self, exception: Exception) -> None:
        """Handle failed operation."""
        self.failure_count += 1
        self.total_failures += 1
        self.last_failure_time = time.time()

        if self.failure_count >= self.failure_threshold:
            self.state = CircuitBreakerState.OPEN
            logger.warning(
                f"Circuit breaker opened after {self.failure_count} failures. "
                f"Last error: {exception}"
            )

    def __call__(self, func: Callable) -> Callable:
        """Decorator for protecting functions with circuit breaker."""

        if asyncio.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                return await self.call_async(func, *args, **kwargs)

            return async_wrapper
        else:

            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs):
                return self.call_sync(func, *args, **kwargs)

            return sync_wrapper

    async def call_async(self, func: Callable, *args, **kwargs) -> Any:
        """Execute async function with circuit breaker protection."""
        self.total_requests += 1

        if self.state == CircuitBreakerState.OPEN:
            if self._should_attempt_reset():
                self.state = CircuitBreakerState.HALF_OPEN
                logger.info("Circuit breaker moving to half-open state")
            else:
                raise CircuitBreakerError(
                    f"Circuit breaker is open. Failure count: {self.failure_count}",
                    self.state,
                )

        try:
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)

            self._on_success()
            return result

        except Exception as e:
            # Check if exception matches expected types
            if not isinstance(e, self.expected_exception):
                raise
            self._on_failure(e)

            if self.state == CircuitBreakerState.HALF_OPEN:
                self.state = CircuitBreakerState.OPEN
                logger.warning("Circuit breaker reopened during half-open test")

            raise

    def call_sync(self, func: Callable, *args, **kwargs) -> Any:
        """Execute sync function with circuit breaker protection."""
        self.total_requests += 1

        if self.state == CircuitBreakerState.OPEN:
            if self._should_attempt_reset():
                self.state = CircuitBreakerState.HALF_OPEN
                logger.info("Circuit breaker moving to half-open state")
            else:
                raise CircuitBreakerError(
                    f"Circuit breaker is open. Failure count: {self.failure_count}",
                    self.state,
                )

        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result

        except Exception as e:
            # Check if exception matches expected types
            if not isinstance(e, self.expected_exception):
                raise
            self._on_failure(e)

            if self.state == CircuitBreakerState.HALF_OPEN:
                self.state = CircuitBreakerState.OPEN
                logger.warning("Circuit breaker reopened during half-open test")

            raise

    def get_stats(self) -> dict:
        """Get circuit breaker statistics."""
        return {
            "state": self.state.value,
            "failure_count": self.failure_count,
            "total_requests": self.total_requests,
            "total_failures": self.total_failures,
            "total_successes": self.total_successes,
            "failure_rate": (
                self.total_failures / self.total_requests
                if self.total_requests > 0
                else 0.0
            ),
            "last_failure_time": self.last_failure_time,
        }

    def reset(self) -> None:
        """Manually reset the circuit breaker."""
        self.state = CircuitBreakerState.CLOSED
        self.failure_count = 0
        self.last_failure_time = None
        logger.info("Circuit breaker manually reset")

    async def __aenter__(self):
        """Async context manager entry."""
        # Check if circuit is open and should attempt reset
        if self.state == CircuitBreakerState.OPEN:
            if self._should_attempt_reset():
                self.state = CircuitBreakerState.HALF_OPEN
                logger.info("Circuit breaker moving to half-open state")
            else:
                raise CircuitBreakerError(
                    f"Circuit breaker is open. Failure count: {self.failure_count}",
                    self.state,
                )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if exc_type is None:
            # Success
            self._on_success()
        elif exc_type is not None and isinstance(exc_val, self.expected_exception):
            # Expected failure
            self._on_failure(exc_val)
            if self.state == CircuitBreakerState.HALF_OPEN:
                self.state = CircuitBreakerState.OPEN
                logger.warning("Circuit breaker reopened during half-open test")
        # Don't suppress exceptions
        return False


class RetryWithBackoff:
    """
    Retry mechanism with exponential backoff.

    Useful for transient Redis failures.
    """

    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 0.1,
        max_delay: float = 2.0,
        exponential_base: float = 2.0,
        jitter: bool = True,
    ):
        """
        Initialize retry mechanism.

        Args:
            max_retries: Maximum number of retry attempts
            base_delay: Initial delay between retries (seconds)
            max_delay: Maximum delay between retries (seconds)
            exponential_base: Base for exponential backoff
            jitter: Whether to add random jitter to delays
        """
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter

    def _calculate_delay(self, attempt: int) -> float:
        """Calculate delay for given attempt number."""
        import random

        delay = min(self.base_delay * (self.exponential_base**attempt), self.max_delay)

        if self.jitter:
            # Add up to 10% jitter
            jitter_amount = delay * 0.1 * random.random()
            delay += jitter_amount

        return delay

    async def execute_async(self, func: Callable, *args, **kwargs) -> Any:
        """Execute async function with retry logic."""
        last_exception = None

        for attempt in range(self.max_retries + 1):
            try:
                if asyncio.iscoroutinefunction(func):
                    return await func(*args, **kwargs)
                else:
                    return func(*args, **kwargs)

            except Exception as e:
                last_exception = e

                if attempt == self.max_retries:
                    # Last attempt failed
                    logger.error(
                        f"All {self.max_retries + 1} attempts failed. "
                        f"Last error: {e}"
                    )
                    raise

                delay = self._calculate_delay(attempt)
                logger.warning(
                    f"Attempt {attempt + 1} failed: {e}. "
                    f"Retrying in {delay:.2f}s..."
                )
                await asyncio.sleep(delay)

        # Should never reach here, but just in case
        if last_exception:
            raise last_exception

    def execute_sync(self, func: Callable, *args, **kwargs) -> Any:
        """Execute sync function with retry logic."""
        import time

        last_exception = None

        for attempt in range(self.max_retries + 1):
            try:
                return func(*args, **kwargs)

            except Exception as e:
                last_exception = e

                if attempt == self.max_retries:
                    # Last attempt failed
                    logger.error(
                        f"All {self.max_retries + 1} attempts failed. "
                        f"Last error: {e}"
                    )
                    raise

                delay = self._calculate_delay(attempt)
                logger.warning(
                    f"Attempt {attempt + 1} failed: {e}. "
                    f"Retrying in {delay:.2f}s..."
                )
                time.sleep(delay)

        # Should never reach here, but just in case
        if last_exception:
            raise last_exception
