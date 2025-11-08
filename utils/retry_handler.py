"""
Retry Handler with Exponential Backoff
Automatic retry mechanism for transient failures
"""

import time
import random
import asyncio
import logging
from typing import Callable, Any, Optional, Tuple, Type
from functools import wraps

logger = logging.getLogger(__name__)


class RetryError(Exception):
    """Exception raised when all retry attempts fail"""
    pass


def retry_with_backoff(
    max_retries: int = 3,
    initial_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
    on_retry: Optional[Callable] = None
):
    """
    Decorator for retry with exponential backoff

    Args:
        max_retries: Maximum number of retry attempts
        initial_delay: Initial delay in seconds
        max_delay: Maximum delay in seconds
        exponential_base: Base for exponential backoff
        jitter: Add random jitter to prevent thundering herd
        exceptions: Tuple of exceptions to catch and retry
        on_retry: Callback function called on each retry

    Usage:
        @retry_with_backoff(max_retries=5, initial_delay=1.0)
        def unstable_function():
            ...
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)

                except exceptions as e:
                    last_exception = e

                    if attempt == max_retries:
                        # All retries exhausted
                        logger.error(
                            f"{func.__name__} failed after {max_retries} retries: {e}"
                        )
                        raise RetryError(
                            f"Failed after {max_retries} attempts"
                        ) from e

                    # Calculate delay
                    delay = min(
                        initial_delay * (exponential_base ** attempt),
                        max_delay
                    )

                    # Add jitter
                    if jitter:
                        delay = delay * (0.5 + random.random())

                    logger.warning(
                        f"{func.__name__} attempt {attempt + 1}/{max_retries} failed: {e}. "
                        f"Retrying in {delay:.2f}s..."
                    )

                    # Call retry callback if provided
                    if on_retry:
                        on_retry(attempt, e, delay)

                    time.sleep(delay)

            # Should not reach here, but just in case
            raise RetryError("Unexpected retry loop exit") from last_exception

        return wrapper
    return decorator


def async_retry_with_backoff(
    max_retries: int = 3,
    initial_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
    on_retry: Optional[Callable] = None
):
    """
    Async version of retry with exponential backoff decorator

    Usage:
        @async_retry_with_backoff(max_retries=5)
        async def async_unstable_function():
            ...
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None

            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)

                except exceptions as e:
                    last_exception = e

                    if attempt == max_retries:
                        logger.error(
                            f"{func.__name__} failed after {max_retries} retries: {e}"
                        )
                        raise RetryError(
                            f"Failed after {max_retries} attempts"
                        ) from e

                    # Calculate delay
                    delay = min(
                        initial_delay * (exponential_base ** attempt),
                        max_delay
                    )

                    # Add jitter
                    if jitter:
                        delay = delay * (0.5 + random.random())

                    logger.warning(
                        f"{func.__name__} attempt {attempt + 1}/{max_retries} failed: {e}. "
                        f"Retrying in {delay:.2f}s..."
                    )

                    # Call retry callback if provided
                    if on_retry:
                        if asyncio.iscoroutinefunction(on_retry):
                            await on_retry(attempt, e, delay)
                        else:
                            on_retry(attempt, e, delay)

                    await asyncio.sleep(delay)

            raise RetryError("Unexpected retry loop exit") from last_exception

        return wrapper
    return decorator


class RetryStrategy:
    """
    Configurable retry strategy for manual retry logic
    """

    def __init__(
        self,
        max_retries: int = 3,
        initial_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        jitter: bool = True
    ):
        self.max_retries = max_retries
        self.initial_delay = initial_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter

        self.attempt = 0

    def get_delay(self) -> float:
        """Calculate delay for current attempt"""
        delay = min(
            self.initial_delay * (self.exponential_base ** self.attempt),
            self.max_delay
        )

        if self.jitter:
            delay = delay * (0.5 + random.random())

        return delay

    def should_retry(self) -> bool:
        """Check if should retry"""
        return self.attempt < self.max_retries

    def next_attempt(self) -> int:
        """Increment attempt counter and return new attempt number"""
        self.attempt += 1
        return self.attempt

    def reset(self):
        """Reset attempt counter"""
        self.attempt = 0


# Specific retry decorators for common scenarios

def retry_api_call(max_retries: int = 5, initial_delay: float = 2.0):
    """
    Retry decorator specifically for API calls

    - Retries on connection errors, timeouts, rate limits
    - Longer delays for rate limits
    """
    return retry_with_backoff(
        max_retries=max_retries,
        initial_delay=initial_delay,
        max_delay=120.0,  # Up to 2 minutes for API calls
        exceptions=(ConnectionError, TimeoutError, Exception)
    )


def retry_db_operation(max_retries: int = 3, initial_delay: float = 0.5):
    """
    Retry decorator for database operations

    - Shorter delays
    - Fewer retries
    """
    return retry_with_backoff(
        max_retries=max_retries,
        initial_delay=initial_delay,
        max_delay=10.0,
        exceptions=(Exception,)
    )


def async_retry_api_call(max_retries: int = 5, initial_delay: float = 2.0):
    """Async version of retry_api_call"""
    return async_retry_with_backoff(
        max_retries=max_retries,
        initial_delay=initial_delay,
        max_delay=120.0,
        exceptions=(ConnectionError, TimeoutError, Exception)
    )


def async_retry_db_operation(max_retries: int = 3, initial_delay: float = 0.5):
    """Async version of retry_db_operation"""
    return async_retry_with_backoff(
        max_retries=max_retries,
        initial_delay=initial_delay,
        max_delay=10.0,
        exceptions=(Exception,)
    )
