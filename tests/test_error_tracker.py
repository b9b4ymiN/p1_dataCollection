"""
Tests for Error Tracker
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.error_tracker import ErrorTracker, get_error_tracker


class TestErrorTracker:
    """Test error tracking functionality"""

    def setup_method(self):
        """Setup for each test"""
        self.tracker = ErrorTracker(alert_threshold=5, time_window=60)

    def test_record_error(self):
        """Test recording an error"""
        error = ValueError("Test error")
        self.tracker.record_error(
            error_type='test_error',
            error=error,
            context={'test': True},
            severity='ERROR'
        )

        assert self.tracker.error_counts['test_error'] == 1
        assert len(self.tracker.error_details) == 1

    def test_error_counting(self):
        """Test error counter increments"""
        for i in range(5):
            error = ValueError(f"Error {i}")
            self.tracker.record_error('test_error', error)

        assert self.tracker.error_counts['test_error'] == 5

    def test_error_rate_calculation(self):
        """Test error rate calculation"""
        for i in range(10):
            error = ValueError(f"Error {i}")
            self.tracker.record_error('test_error', error)

        rate = self.tracker.get_error_rate('test_error')
        assert rate > 0  # Should have some rate

    def test_get_error_summary(self):
        """Test error summary generation"""
        error = ValueError("Test error")
        self.tracker.record_error('test_error', error)

        summary = self.tracker.get_error_summary()

        assert summary['total_errors'] == 1
        assert 'test_error' in summary['error_types']
        assert len(summary['recent_errors']) > 0

    def test_clear_errors(self):
        """Test clearing errors"""
        error = ValueError("Test error")
        self.tracker.record_error('test_error', error)

        assert self.tracker.error_counts['test_error'] == 1

        self.tracker.clear_errors('test_error')

        assert self.tracker.error_counts['test_error'] == 0

    def test_multiple_error_types(self):
        """Test tracking multiple error types"""
        self.tracker.record_error('error_type_1', ValueError("Error 1"))
        self.tracker.record_error('error_type_2', TypeError("Error 2"))
        self.tracker.record_error('error_type_1', ValueError("Error 3"))

        assert self.tracker.error_counts['error_type_1'] == 2
        assert self.tracker.error_counts['error_type_2'] == 1

    def test_global_tracker(self):
        """Test global error tracker instance"""
        tracker1 = get_error_tracker()
        tracker2 = get_error_tracker()

        assert tracker1 is tracker2  # Should be same instance


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
