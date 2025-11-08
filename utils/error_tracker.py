"""
Error Tracking and Counter System
Comprehensive error tracking with metrics and alerting
"""

import logging
import time
from typing import Dict, List, Optional
from collections import defaultdict, deque
from datetime import datetime, timedelta
import threading
import json

logger = logging.getLogger(__name__)


class ErrorTracker:
    """
    Centralized error tracking with counters, metrics, and alerting
    """

    def __init__(self, alert_threshold: int = 10, time_window: int = 300):
        """
        Initialize error tracker

        Args:
            alert_threshold: Number of errors before alerting
            time_window: Time window in seconds for error rate calculation
        """
        self.alert_threshold = alert_threshold
        self.time_window = time_window

        # Error counters
        self.error_counts = defaultdict(int)  # Total count per error type
        self.error_history = defaultdict(lambda: deque(maxlen=1000))  # Recent errors
        self.error_details = []  # Detailed error information

        # Error rate tracking
        self.error_timestamps = defaultdict(lambda: deque(maxlen=100))

        # Circuit breaker states
        self.circuit_states = {}  # service_name -> state

        # Lock for thread safety
        self.lock = threading.Lock()

        # Alert tracking
        self.alerts_sent = defaultdict(int)
        self.last_alert_time = defaultdict(float)
        self.alert_cooldown = 300  # 5 minutes between alerts

    def record_error(
        self,
        error_type: str,
        error: Exception,
        context: Optional[Dict] = None,
        severity: str = "ERROR"
    ):
        """
        Record an error with full context

        Args:
            error_type: Type/category of error (e.g., 'api_error', 'db_error')
            error: The exception object
            context: Additional context (symbol, function, etc.)
            severity: ERROR, WARNING, CRITICAL
        """
        with self.lock:
            timestamp = time.time()

            # Increment counter
            self.error_counts[error_type] += 1

            # Record timestamp for rate calculation
            self.error_timestamps[error_type].append(timestamp)

            # Store error details
            error_record = {
                'timestamp': datetime.fromtimestamp(timestamp).isoformat(),
                'error_type': error_type,
                'error_class': error.__class__.__name__,
                'error_message': str(error),
                'severity': severity,
                'context': context or {},
                'count': self.error_counts[error_type]
            }

            self.error_history[error_type].append(error_record)
            self.error_details.append(error_record)

            # Keep only recent errors (last 1000)
            if len(self.error_details) > 1000:
                self.error_details = self.error_details[-1000:]

            # Log the error
            log_msg = f"{error_type}: {error.__class__.__name__} - {str(error)}"
            if context:
                log_msg += f" | Context: {json.dumps(context)}"

            if severity == "CRITICAL":
                logger.critical(log_msg)
            elif severity == "WARNING":
                logger.warning(log_msg)
            else:
                logger.error(log_msg)

            # Check if alert should be sent
            self._check_alert(error_type, error_record)

    def get_error_rate(self, error_type: str) -> float:
        """
        Calculate error rate (errors per minute) for given error type

        Returns:
            Errors per minute
        """
        with self.lock:
            timestamps = self.error_timestamps[error_type]
            if not timestamps:
                return 0.0

            # Count errors in the time window
            current_time = time.time()
            cutoff_time = current_time - self.time_window

            recent_errors = sum(1 for t in timestamps if t >= cutoff_time)

            # Calculate rate per minute
            return (recent_errors / self.time_window) * 60

    def get_error_summary(self) -> Dict:
        """Get comprehensive error summary"""
        with self.lock:
            summary = {
                'total_errors': sum(self.error_counts.values()),
                'error_types': dict(self.error_counts),
                'error_rates': {},
                'recent_errors': [],
                'top_errors': []
            }

            # Calculate error rates
            for error_type in self.error_counts.keys():
                summary['error_rates'][error_type] = self.get_error_rate(error_type)

            # Get recent errors (last 10)
            summary['recent_errors'] = self.error_details[-10:]

            # Get top error types
            top_errors = sorted(
                self.error_counts.items(),
                key=lambda x: x[1],
                reverse=True
            )[:5]
            summary['top_errors'] = [
                {'type': t, 'count': c} for t, c in top_errors
            ]

            return summary

    def get_errors_by_type(self, error_type: str, limit: int = 10) -> List[Dict]:
        """Get recent errors of specific type"""
        with self.lock:
            history = list(self.error_history[error_type])
            return history[-limit:]

    def clear_errors(self, error_type: Optional[str] = None):
        """Clear error counters"""
        with self.lock:
            if error_type:
                self.error_counts[error_type] = 0
                self.error_history[error_type].clear()
                self.error_timestamps[error_type].clear()
            else:
                self.error_counts.clear()
                self.error_history.clear()
                self.error_timestamps.clear()
                self.error_details.clear()

    def _check_alert(self, error_type: str, error_record: Dict):
        """Check if alert should be sent"""
        current_time = time.time()

        # Check cooldown
        if error_type in self.last_alert_time:
            time_since_last_alert = current_time - self.last_alert_time[error_type]
            if time_since_last_alert < self.alert_cooldown:
                return

        # Check threshold
        if self.error_counts[error_type] >= self.alert_threshold:
            self._send_alert(error_type, error_record)
            self.last_alert_time[error_type] = current_time
            self.alerts_sent[error_type] += 1

    def _send_alert(self, error_type: str, error_record: Dict):
        """Send alert (can be extended to send emails, Slack, etc.)"""
        error_rate = self.get_error_rate(error_type)

        alert_msg = f"""
        ⚠️ ERROR ALERT ⚠️

        Error Type: {error_type}
        Total Count: {self.error_counts[error_type]}
        Error Rate: {error_rate:.2f} errors/min
        Severity: {error_record['severity']}

        Latest Error:
        - Class: {error_record['error_class']}
        - Message: {error_record['error_message']}
        - Time: {error_record['timestamp']}
        - Context: {json.dumps(error_record['context'], indent=2)}
        """

        logger.critical(alert_msg)

        # TODO: Add integrations for email, Slack, PagerDuty, etc.
        # Example: send_slack_alert(alert_msg)

    def print_summary(self):
        """Print formatted error summary"""
        summary = self.get_error_summary()

        print("\n" + "=" * 80)
        print("ERROR TRACKING SUMMARY")
        print("=" * 80)

        print(f"\nTotal Errors: {summary['total_errors']}")

        if summary['top_errors']:
            print("\nTop Error Types:")
            for err in summary['top_errors']:
                rate = summary['error_rates'].get(err['type'], 0)
                print(f"  {err['type']}: {err['count']} ({rate:.2f}/min)")

        if summary['recent_errors']:
            print("\nRecent Errors:")
            for err in summary['recent_errors'][-5:]:
                print(f"  [{err['timestamp']}] {err['error_type']}: {err['error_message'][:50]}")

        print("=" * 80 + "\n")

    def export_errors(self, filepath: str):
        """Export errors to JSON file"""
        with self.lock:
            summary = self.get_error_summary()
            summary['error_history'] = {
                k: list(v) for k, v in self.error_history.items()
            }

            with open(filepath, 'w') as f:
                json.dump(summary, f, indent=2)

            logger.info(f"Errors exported to {filepath}")


# Global error tracker instance
_global_tracker = None


def get_error_tracker() -> ErrorTracker:
    """Get global error tracker instance"""
    global _global_tracker
    if _global_tracker is None:
        _global_tracker = ErrorTracker()
    return _global_tracker


def record_error(error_type: str, error: Exception, context: Optional[Dict] = None, severity: str = "ERROR"):
    """Convenience function to record error to global tracker"""
    tracker = get_error_tracker()
    tracker.record_error(error_type, error, context, severity)
