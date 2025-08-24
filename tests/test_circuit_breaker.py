"""
Comprehensive tests for the circuit breaker functionality.
"""

import asyncio
import time
from unittest.mock import patch

import pytest

from yokedcache.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerError,
    CircuitBreakerState,
    RetryWithBackoff,
)


class TestCircuitBreaker:
    """Test circuit breaker functionality comprehensively."""

    def test_circuit_breaker_initial_state(self):
        """Test circuit breaker initialization."""
        cb = CircuitBreaker(
            failure_threshold=3, timeout=30.0, expected_exception=ValueError
        )

        assert cb.failure_threshold == 3
        assert cb.timeout == 30.0
        assert cb.failure_count == 0
        assert cb.state == CircuitBreakerState.CLOSED
        assert cb.total_requests == 0
        assert cb.total_failures == 0
        assert cb.total_successes == 0
        assert cb.last_failure_time is None

    def test_circuit_breaker_success_tracking(self):
        """Test successful operation tracking."""
        cb = CircuitBreaker(failure_threshold=2)

        def success_func():
            return "success"

        result = cb.call_sync(success_func)

        assert result == "success"
        stats = cb.get_stats()
        assert stats["total_requests"] == 1
        assert stats["failure_count"] == 0
        assert cb.state == CircuitBreakerState.CLOSED

    def test_circuit_breaker_failure_tracking(self):
        """Test failure tracking and state changes."""
        cb = CircuitBreaker(failure_threshold=2, timeout=1.0)

        def failing_func():
            raise ValueError("Test error")

        # First failure
        with pytest.raises(ValueError):
            cb.call_sync(failing_func)

        stats = cb.get_stats()
        assert stats["total_requests"] == 1
        assert stats["failure_count"] == 1
        assert cb.state == CircuitBreakerState.CLOSED

        # Second failure - should open circuit
        with pytest.raises(ValueError):
            cb.call_sync(failing_func)

        stats = cb.get_stats()
        assert stats["total_requests"] == 2
        assert stats["failure_count"] == 2
        assert cb.state == CircuitBreakerState.OPEN

    def test_circuit_breaker_open_state_blocking(self):
        """Test that open circuit blocks requests."""
        cb = CircuitBreaker(failure_threshold=1, timeout=1.0)

        def failing_func():
            raise ValueError("Test error")

        def success_func():
            return "success"

        # Cause failure to open circuit
        with pytest.raises(ValueError):
            cb.call_sync(failing_func)

        # Now circuit should be open and block requests
        with pytest.raises(CircuitBreakerError) as exc_info:
            cb.call_sync(success_func)

        assert exc_info.value.state == CircuitBreakerState.OPEN
        assert "Circuit breaker is open" in str(exc_info.value)

    def test_circuit_breaker_half_open_transition(self):
        """Test transition to half-open state after timeout."""
        cb = CircuitBreaker(failure_threshold=1, timeout=0.1)

        def failing_func():
            raise ValueError("Test error")

        def success_func():
            return "success"

        # Open the circuit
        with pytest.raises(ValueError):
            cb.call_sync(failing_func)

        assert cb.state == CircuitBreakerState.OPEN

        # Wait for timeout
        time.sleep(0.2)

        # Should transition to half-open and allow test request
        result = cb.call_sync(success_func)
        assert result == "success"
        assert cb.state == CircuitBreakerState.CLOSED

    def test_circuit_breaker_half_open_failure_reopens(self):
        """Test that failure in half-open state reopens circuit."""
        cb = CircuitBreaker(failure_threshold=1, timeout=0.1)

        def failing_func():
            raise ValueError("Test error")

        # Open the circuit
        with pytest.raises(ValueError):
            cb.call_sync(failing_func)

        # Wait for timeout
        time.sleep(0.2)

        # Fail during half-open test
        with pytest.raises(ValueError):
            cb.call_sync(failing_func)

        # Should be open again
        assert cb.state == CircuitBreakerState.OPEN

    @pytest.mark.asyncio
    async def test_circuit_breaker_async_operations(self):
        """Test circuit breaker with async functions."""
        cb = CircuitBreaker(failure_threshold=2)

        async def async_success():
            return "async_success"

        async def async_failure():
            raise ValueError("Async error")

        # Test successful async operation
        result = await cb.call_async(async_success)
        assert result == "async_success"

        # Test failed async operation
        with pytest.raises(ValueError):
            await cb.call_async(async_failure)

        stats = cb.get_stats()
        assert stats["total_requests"] == 2

    def test_circuit_breaker_decorator(self):
        """Test circuit breaker as decorator."""
        cb = CircuitBreaker(failure_threshold=1)

        @cb
        def decorated_func(x):
            if x < 0:
                raise ValueError("Negative value")
            return x * 2

        # Test successful call
        result = decorated_func(5)
        assert result == 10

        # Test failure
        with pytest.raises(ValueError):
            decorated_func(-1)

        # Circuit should be open now
        with pytest.raises(CircuitBreakerError):
            decorated_func(3)

    @pytest.mark.asyncio
    async def test_circuit_breaker_async_decorator(self):
        """Test circuit breaker as async decorator."""
        cb = CircuitBreaker(failure_threshold=1)

        @cb
        async def async_decorated_func(x):
            if x < 0:
                raise ValueError("Negative value")
            await asyncio.sleep(0.01)
            return x * 2

        # Test successful call
        result = await async_decorated_func(5)
        assert result == 10

        # Test failure
        with pytest.raises(ValueError):
            await async_decorated_func(-1)

        # Circuit should be open now
        with pytest.raises(CircuitBreakerError):
            await async_decorated_func(3)

    def test_circuit_breaker_exception_filtering(self):
        """Test that only expected exceptions trigger circuit breaker."""
        cb = CircuitBreaker(failure_threshold=2, expected_exception=ValueError)

        def value_error_func():
            raise ValueError("Expected error")

        def runtime_error_func():
            raise RuntimeError("Unexpected error")

        # ValueError should trigger circuit breaker
        with pytest.raises(ValueError):
            cb.call_sync(value_error_func)

        stats = cb.get_stats()
        initial_failure_count = stats["failure_count"]
        assert initial_failure_count == 1

        # RuntimeError should not trigger circuit breaker (but will be re-raised)
        with pytest.raises(RuntimeError):
            cb.call_sync(runtime_error_func)

        # Failure count should not increase for non-expected exceptions
        stats = cb.get_stats()
        assert stats["failure_count"] == initial_failure_count

    def test_circuit_breaker_stats(self):
        """Test circuit breaker statistics."""
        cb = CircuitBreaker(failure_threshold=3)

        def sometimes_fails(should_fail):
            if should_fail:
                raise ValueError("Test error")
            return "success"

        # Mix of successes and failures
        cb.call_sync(sometimes_fails, False)  # Success
        cb.call_sync(sometimes_fails, False)  # Success

        with pytest.raises(ValueError):
            cb.call_sync(sometimes_fails, True)  # Failure

        stats = cb.get_stats()

        assert stats["total_requests"] == 3
        assert stats["state"] == "closed"

    def test_circuit_breaker_reset(self):
        """Test manual circuit breaker reset."""
        cb = CircuitBreaker(failure_threshold=1)

        def failing_func():
            raise ValueError("Test error")

        # Open the circuit
        with pytest.raises(ValueError):
            cb.call_sync(failing_func)

        assert cb.state == CircuitBreakerState.OPEN

        # Reset manually
        cb.reset()

        assert cb.state == CircuitBreakerState.CLOSED
        assert cb.failure_count == 0
        assert cb.last_failure_time is None


class TestRetryWithBackoff:
    """Test retry mechanism with exponential backoff."""

    def test_retry_initialization(self):
        """Test retry mechanism initialization."""
        retry = RetryWithBackoff(
            max_retries=3,
            base_delay=0.1,
            max_delay=2.0,
            exponential_base=2.0,
            jitter=True,
        )

        assert retry.max_retries == 3
        assert retry.base_delay == 0.1
        assert retry.max_delay == 2.0
        assert retry.exponential_base == 2.0
        assert retry.jitter is True

    def test_retry_successful_on_first_attempt(self):
        """Test retry when function succeeds on first attempt."""
        retry = RetryWithBackoff(max_retries=3)

        def success_func():
            return "success"

        result = retry.execute_sync(success_func)
        assert result == "success"

    def test_retry_after_failures(self):
        """Test retry mechanism with eventual success."""
        retry = RetryWithBackoff(max_retries=3, base_delay=0.01)
        call_count = 0

        def eventually_succeeds():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError(f"Attempt {call_count} failed")
            return f"Success on attempt {call_count}"

        result = retry.execute_sync(eventually_succeeds)
        assert result == "Success on attempt 3"
        assert call_count == 3

    def test_retry_exhausted(self):
        """Test retry mechanism when all attempts fail."""
        retry = RetryWithBackoff(max_retries=2, base_delay=0.01)

        def always_fails():
            raise ValueError("Always fails")

        with pytest.raises(ValueError, match="Always fails"):
            retry.execute_sync(always_fails)

    @pytest.mark.asyncio
    async def test_retry_async_success(self):
        """Test async retry mechanism."""
        retry = RetryWithBackoff(max_retries=3, base_delay=0.01)
        call_count = 0

        async def eventually_succeeds():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ValueError(f"Attempt {call_count} failed")
            return f"Success on attempt {call_count}"

        result = await retry.execute_async(eventually_succeeds)
        assert result == "Success on attempt 2"
        assert call_count == 2

    def test_calculate_delay(self):
        """Test delay calculation with exponential backoff."""
        retry = RetryWithBackoff(
            max_retries=5,
            base_delay=0.1,
            max_delay=2.0,
            exponential_base=2.0,
            jitter=False,
        )

        # Test delay calculation for different attempts
        delay_0 = retry._calculate_delay(0)
        delay_1 = retry._calculate_delay(1)
        delay_2 = retry._calculate_delay(2)
        delay_5 = retry._calculate_delay(5)

        assert delay_0 == 0.1  # base_delay * 2^0
        assert delay_1 == 0.2  # base_delay * 2^1
        assert delay_2 == 0.4  # base_delay * 2^2
        assert delay_5 == 2.0  # capped at max_delay

    def test_delay_with_jitter(self):
        """Test that jitter adds randomness to delays."""
        retry = RetryWithBackoff(max_retries=3, base_delay=1.0, jitter=True)

        # Calculate delay multiple times to check for variation
        delays = [retry._calculate_delay(1) for _ in range(10)]

        # Should have some variation due to jitter
        assert len(set(delays)) > 1

        # All delays should be around the expected value (2.0) but with jitter
        for delay in delays:
            assert 2.0 <= delay <= 2.2  # 2.0 + 10% jitter

    @pytest.mark.asyncio
    async def test_async_retry_with_sync_function(self):
        """Test async retry with sync function."""
        retry = RetryWithBackoff(max_retries=2, base_delay=0.01)

        def sync_func():
            return "sync_result"

        result = await retry.execute_async(sync_func)
        assert result == "sync_result"
