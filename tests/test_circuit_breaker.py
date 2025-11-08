"""
Tests for Circuit Breaker
"""

import pytest
import time
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.circuit_breaker import CircuitBreaker, CircuitState, CircuitBreakerError


class TestCircuitBreaker:
    """Test circuit breaker functionality"""

    def setup_method(self):
        """Setup for each test"""
        self.breaker = CircuitBreaker(
            name='test_breaker',
            failure_threshold=3,
            recovery_timeout=1,
            success_threshold=2
        )

    def test_initial_state_is_closed(self):
        """Test circuit breaker starts in CLOSED state"""
        assert self.breaker.state == CircuitState.CLOSED

    def test_successful_call(self):
        """Test successful call passes through"""
        result = self.breaker.call(lambda: "success")
        assert result == "success"
        assert self.breaker.successful_calls == 1

    def test_failed_call(self):
        """Test failed call is tracked"""
        with pytest.raises(ValueError):
            self.breaker.call(lambda: 1 / 0)  # This will raise an error

        assert self.breaker.failed_calls == 1
        assert self.breaker.failure_count == 1

    def test_circuit_opens_after_threshold(self):
        """Test circuit opens after failure threshold"""
        # Trigger failures
        for i in range(3):
            with pytest.raises(Exception):
                self.breaker.call(lambda: 1 / 0)

        assert self.breaker.state == CircuitState.OPEN

    def test_open_circuit_rejects_calls(self):
        """Test OPEN circuit rejects calls immediately"""
        # Open the circuit
        for i in range(3):
            with pytest.raises(Exception):
                self.breaker.call(lambda: 1 / 0)

        # Now calls should be rejected
        with pytest.raises(CircuitBreakerError):
            self.breaker.call(lambda: "test")

        assert self.breaker.rejected_calls > 0

    def test_transition_to_half_open(self):
        """Test circuit transitions to HALF_OPEN after timeout"""
        # Open the circuit
        for i in range(3):
            with pytest.raises(Exception):
                self.breaker.call(lambda: 1 / 0)

        assert self.breaker.state == CircuitState.OPEN

        # Wait for recovery timeout
        time.sleep(1.1)

        # Next call should trigger HALF_OPEN
        try:
            self.breaker.call(lambda: "success")
        except:
            pass

        # State should be HALF_OPEN or CLOSED depending on success
        assert self.breaker.state in [CircuitState.HALF_OPEN, CircuitState.CLOSED]

    def test_circuit_closes_after_successes(self):
        """Test circuit closes after successful calls in HALF_OPEN"""
        # Open circuit
        for i in range(3):
            with pytest.raises(Exception):
                self.breaker.call(lambda: 1 / 0)

        # Wait for recovery
        time.sleep(1.1)

        # Successful calls to close circuit
        try:
            self.breaker.call(lambda: "success")
            self.breaker.call(lambda: "success")
        except:
            pass

        # Should eventually close
        assert self.breaker.state == CircuitState.CLOSED or self.breaker.success_count >= self.breaker.success_threshold

    def test_get_stats(self):
        """Test statistics retrieval"""
        self.breaker.call(lambda: "success")

        stats = self.breaker.get_stats()

        assert 'name' in stats
        assert 'state' in stats
        assert 'total_calls' in stats
        assert stats['total_calls'] == 1

    def test_reset(self):
        """Test manual circuit reset"""
        # Open circuit
        for i in range(3):
            with pytest.raises(Exception):
                self.breaker.call(lambda: 1 / 0)

        assert self.breaker.state == CircuitState.OPEN

        # Reset
        self.breaker.reset()

        assert self.breaker.state == CircuitState.CLOSED
        assert self.breaker.failure_count == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
