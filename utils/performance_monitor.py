"""
Performance Monitoring Utilities
Track latency, throughput, and system performance
"""

import time
import logging
from typing import Dict, List
from collections import deque
from datetime import datetime
import psutil
import threading

logger = logging.getLogger(__name__)


class PerformanceMonitor:
    """
    Monitor and track system performance metrics
    """

    def __init__(self):
        self.metrics = {
            'api_calls': deque(maxlen=1000),
            'db_operations': deque(maxlen=1000),
            'cache_operations': deque(maxlen=1000),
            'websocket_messages': deque(maxlen=1000)
        }

        self.counters = {
            'total_api_calls': 0,
            'total_db_operations': 0,
            'total_cache_operations': 0,
            'total_ws_messages': 0
        }

        self.start_time = time.time()
        self.lock = threading.Lock()

    def record_api_call(self, duration_ms: float, success: bool = True):
        """Record API call metrics"""
        with self.lock:
            self.metrics['api_calls'].append({
                'timestamp': time.time(),
                'duration_ms': duration_ms,
                'success': success
            })
            self.counters['total_api_calls'] += 1

    def record_db_operation(self, operation: str, duration_ms: float, rows: int = 0):
        """Record database operation metrics"""
        with self.lock:
            self.metrics['db_operations'].append({
                'timestamp': time.time(),
                'operation': operation,
                'duration_ms': duration_ms,
                'rows': rows
            })
            self.counters['total_db_operations'] += 1

    def record_cache_operation(self, operation: str, duration_ms: float, hit: bool = False):
        """Record cache operation metrics"""
        with self.lock:
            self.metrics['cache_operations'].append({
                'timestamp': time.time(),
                'operation': operation,
                'duration_ms': duration_ms,
                'hit': hit
            })
            self.counters['total_cache_operations'] += 1

    def record_websocket_message(self, latency_ms: float):
        """Record WebSocket message metrics"""
        with self.lock:
            self.metrics['websocket_messages'].append({
                'timestamp': time.time(),
                'latency_ms': latency_ms
            })
            self.counters['total_ws_messages'] += 1

    def get_summary(self) -> Dict:
        """Get performance summary"""
        with self.lock:
            uptime = time.time() - self.start_time

            summary = {
                'uptime_seconds': uptime,
                'uptime_hours': uptime / 3600,
                'counters': self.counters.copy(),
                'rates': {
                    'api_calls_per_second': self.counters['total_api_calls'] / uptime if uptime > 0 else 0,
                    'db_ops_per_second': self.counters['total_db_operations'] / uptime if uptime > 0 else 0,
                    'ws_messages_per_second': self.counters['total_ws_messages'] / uptime if uptime > 0 else 0
                }
            }

            # Calculate latency statistics
            for metric_name, metric_data in self.metrics.items():
                if metric_data:
                    if 'duration_ms' in metric_data[0]:
                        durations = [m['duration_ms'] for m in metric_data]
                        summary[f'{metric_name}_latency'] = {
                            'avg_ms': sum(durations) / len(durations),
                            'min_ms': min(durations),
                            'max_ms': max(durations),
                            'p50_ms': self._percentile(durations, 50),
                            'p95_ms': self._percentile(durations, 95),
                            'p99_ms': self._percentile(durations, 99)
                        }

            # System metrics
            summary['system'] = {
                'cpu_percent': psutil.cpu_percent(interval=0.1),
                'memory_percent': psutil.virtual_memory().percent,
                'disk_percent': psutil.disk_usage('/').percent
            }

            return summary

    def print_summary(self):
        """Print formatted performance summary"""
        summary = self.get_summary()

        print("\n" + "=" * 80)
        print("PERFORMANCE SUMMARY")
        print("=" * 80)

        print(f"\nUptime: {summary['uptime_hours']:.2f} hours")

        print("\nThroughput:")
        print(f"  API Calls:     {summary['rates']['api_calls_per_second']:.2f} req/s")
        print(f"  DB Operations: {summary['rates']['db_ops_per_second']:.2f} ops/s")
        print(f"  WS Messages:   {summary['rates']['ws_messages_per_second']:.2f} msg/s")

        print("\nLatency (API Calls):")
        if 'api_calls_latency' in summary:
            lat = summary['api_calls_latency']
            print(f"  Avg: {lat['avg_ms']:.2f}ms  P50: {lat['p50_ms']:.2f}ms  P95: {lat['p95_ms']:.2f}ms  P99: {lat['p99_ms']:.2f}ms")

        print("\nLatency (DB Operations):")
        if 'db_operations_latency' in summary:
            lat = summary['db_operations_latency']
            print(f"  Avg: {lat['avg_ms']:.2f}ms  P50: {lat['p50_ms']:.2f}ms  P95: {lat['p95_ms']:.2f}ms  P99: {lat['p99_ms']:.2f}ms")

        print("\nSystem Resources:")
        sys_metrics = summary['system']
        print(f"  CPU:    {sys_metrics['cpu_percent']:.1f}%")
        print(f"  Memory: {sys_metrics['memory_percent']:.1f}%")
        print(f"  Disk:   {sys_metrics['disk_percent']:.1f}%")

        print("=" * 80 + "\n")

    @staticmethod
    def _percentile(data: List[float], percentile: int) -> float:
        """Calculate percentile"""
        if not data:
            return 0
        sorted_data = sorted(data)
        index = int(len(sorted_data) * percentile / 100)
        return sorted_data[min(index, len(sorted_data) - 1)]


class Timer:
    """
    Context manager for timing operations

    Usage:
        with Timer() as t:
            do_something()
        print(f"Operation took {t.elapsed_ms}ms")
    """

    def __init__(self, name: str = None):
        self.name = name
        self.start_time = None
        self.end_time = None

    def __enter__(self):
        self.start_time = time.time()
        return self

    def __exit__(self, *args):
        self.end_time = time.time()
        if self.name:
            logger.debug(f"{self.name} took {self.elapsed_ms:.2f}ms")

    @property
    def elapsed_ms(self) -> float:
        """Get elapsed time in milliseconds"""
        if self.end_time is None:
            return (time.time() - self.start_time) * 1000
        return (self.end_time - self.start_time) * 1000


def benchmark(func):
    """
    Decorator to benchmark function execution time

    Usage:
        @benchmark
        def my_function():
            ...
    """
    def wrapper(*args, **kwargs):
        start = time.time()
        result = func(*args, **kwargs)
        duration = (time.time() - start) * 1000
        logger.info(f"{func.__name__} executed in {duration:.2f}ms")
        return result
    return wrapper
