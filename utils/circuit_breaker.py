"""
Circuit Breaker Pattern Implementation
Prevents cascading failures by breaking the circuit when errors exceed threshold
"""

import time
import logging
from enum import Enum
from typing import Callable, Any, Optional
from functools import wraps
import threading

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """Circuit breaker states"""
    CLOSED = "closed"  # Normal operation
    OPEN = "open"      # Circuit is broken, fail fast
    HALF_OPEN = "half_open"  # Testing if service recovered


class CircuitBreaker:
    """
    Circuit breaker to prevent cascading failures

    States:
    - CLOSED: Normal operation, requests pass through
    - OPEN: Too many failures, requests fail immediately
    - HALF_OPEN: Testing if service recovered, limited requests pass through
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        expected_exception: type = Exception,
        success_threshold: int = 2
    ):
        """
        Initialize circuit breaker

        Args:
            name: Name of the circuit breaker
            failure_threshold: Number of failures before opening circuit
            recovery_timeout: Seconds to wait before trying half-open
            expected_exception: Exception type to catch
            success_threshold: Successful calls needed in half-open to close circuit
        """
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        self.success_threshold = success_threshold

        # State tracking
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = None
        self.last_state_change = time.time()

        # Statistics
        self.total_calls = 0
        self.successful_calls = 0
        self.failed_calls = 0
        self.rejected_calls = 0

        # Thread safety
        self.lock = threading.Lock()

    def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute function through circuit breaker

        Args:
            func: Function to execute
            *args, **kwargs: Function arguments

        Returns:
            Function result

        Raises:
            CircuitBreakerError: If circuit is open
            Original exception: If call fails
        """
        with self.lock:
            self.total_calls += 1

            # Check if circuit should transition from OPEN to HALF_OPEN
            if self.state == CircuitState.OPEN:
                if self._should_attempt_reset():
                    self._transition_to_half_open()
                else:
                    self.rejected_calls += 1
                    raise CircuitBreakerError(
                        f"Circuit breaker '{self.name}' is OPEN. "
                        f"Retry after {self.recovery_timeout}s"
                    )

        # Execute the function
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result

        except self.expected_exception as e:
            self._on_failure()
            raise

    def _on_success(self):
        """Handle successful call"""
        with self.lock:
            self.successful_calls += 1
            self.failure_count = 0

            if self.state == CircuitState.HALF_OPEN:
                self.success_count += 1
                if self.success_count >= self.success_threshold:
                    self._transition_to_closed()

    def _on_failure(self):
        """Handle failed call"""
        with self.lock:
            self.failed_calls += 1
            self.failure_count += 1
            self.last_failure_time = time.time()

            if self.state == CircuitState.HALF_OPEN:
                # Failed during testing, reopen circuit
                self._transition_to_open()

            elif self.state == CircuitState.CLOSED:
                if self.failure_count >= self.failure_threshold:
                    self._transition_to_open()

    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset"""
        return (time.time() - self.last_failure_time) >= self.recovery_timeout

    def _transition_to_open(self):
        """Transition to OPEN state"""
        previous_state = self.state
        self.state = CircuitState.OPEN
        self.last_state_change = time.time()
        logger.warning(
            f"Circuit breaker '{self.name}' transitioned from {previous_state.value} "
            f"to OPEN after {self.failure_count} failures"
        )

    def _transition_to_half_open(self):
        """Transition to HALF_OPEN state"""
        self.state = CircuitState.HALF_OPEN
        self.success_count = 0
        self.last_state_change = time.time()
        logger.info(f"Circuit breaker '{self.name}' transitioned to HALF_OPEN (testing)")

    def _transition_to_closed(self):
        """Transition to CLOSED state"""
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_state_change = time.time()
        logger.info(f"Circuit breaker '{self.name}' transitioned to CLOSED (recovered)")

    def get_stats(self) -> dict:
        """Get circuit breaker statistics"""
        with self.lock:
            success_rate = (
                (self.successful_calls / self.total_calls * 100)
                if self.total_calls > 0 else 0
            )

            return {
                'name': self.name,
                'state': self.state.value,
                'total_calls': self.total_calls,
                'successful_calls': self.successful_calls,
                'failed_calls': self.failed_calls,
                'rejected_calls': self.rejected_calls,
                'success_rate': f"{success_rate:.2f}%",
                'failure_count': self.failure_count,
                'time_in_current_state': time.time() - self.last_state_change
            }

    def reset(self):
        """Manually reset circuit breaker"""
        with self.lock:
            self.state = CircuitState.CLOSED
            self.failure_count = 0
            self.success_count = 0
            self.last_failure_time = None
            logger.info(f"Circuit breaker '{self.name}' manually reset")


class CircuitBreakerError(Exception):
    """Exception raised when circuit breaker is open"""
    pass


class CircuitBreakerManager:
    """Manage multiple circuit breakers"""

    def __init__(self):
        self.breakers = {}
        self.lock = threading.Lock()

    def get_breaker(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: int = 60
    ) -> CircuitBreaker:
        """
        Get or create circuit breaker

        Args:
            name: Circuit breaker name
            failure_threshold: Failures before opening
            recovery_timeout: Seconds before retry

        Returns:
            CircuitBreaker instance
        """
        with self.lock:
            if name not in self.breakers:
                self.breakers[name] = CircuitBreaker(
                    name=name,
                    failure_threshold=failure_threshold,
                    recovery_timeout=recovery_timeout
                )
            return self.breakers[name]

    def get_all_stats(self) -> dict:
        """Get stats for all circuit breakers"""
        with self.lock:
            return {
                name: breaker.get_stats()
                for name, breaker in self.breakers.items()
            }

    def print_summary(self):
        """Print summary of all circuit breakers"""
        stats = self.get_all_stats()

        print("\n" + "=" * 80)
        print("CIRCUIT BREAKER STATUS")
        print("=" * 80)

        for name, stat in stats.items():
            state_icon = {
                'closed': '✅',
                'open': '❌',
                'half_open': '⚠️'
            }.get(stat['state'], '❓')

            print(f"\n{state_icon} {name}:")
            print(f"  State: {stat['state'].upper()}")
            print(f"  Total Calls: {stat['total_calls']}")
            print(f"  Success Rate: {stat['success_rate']}")
            print(f"  Failed: {stat['failed_calls']} | Rejected: {stat['rejected_calls']}")

        print("=" * 80 + "\n")


# Global circuit breaker manager
_global_manager = None


def get_circuit_breaker_manager() -> CircuitBreakerManager:
    """Get global circuit breaker manager"""
    global _global_manager
    if _global_manager is None:
        _global_manager = CircuitBreakerManager()
    return _global_manager


def circuit_breaker(
    name: str,
    failure_threshold: int = 5,
    recovery_timeout: int = 60
):
    """
    Decorator for circuit breaker pattern

    Usage:
        @circuit_breaker(name='binance_api', failure_threshold=5, recovery_timeout=60)
        def fetch_data():
            ...
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            manager = get_circuit_breaker_manager()
            breaker = manager.get_breaker(name, failure_threshold, recovery_timeout)
            return breaker.call(func, *args, **kwargs)
        return wrapper
    return decorator
