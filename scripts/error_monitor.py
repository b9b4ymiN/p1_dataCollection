"""
Error Monitoring Dashboard
Real-time monitoring of errors, circuit breakers, and system health
"""

import sys
import os
import time
import argparse
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.error_tracker import get_error_tracker
from utils.circuit_breaker import get_circuit_breaker_manager


def clear_screen():
    """Clear terminal screen"""
    os.system('cls' if os.name == 'nt' else 'clear')


def print_dashboard():
    """Print error monitoring dashboard"""
    clear_screen()

    # Get error tracker and circuit breaker manager
    error_tracker = get_error_tracker()
    cb_manager = get_circuit_breaker_manager()

    # Header
    print("=" * 100)
    print(f"ERROR MONITORING DASHBOARD - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 100)

    # Error Summary
    error_summary = error_tracker.get_error_summary()

    print(f"\n📊 OVERALL STATISTICS")
    print("-" * 100)
    print(f"Total Errors: {error_summary['total_errors']}")

    # Error counts by type
    if error_summary['error_types']:
        print(f"\n🔴 ERROR TYPES:")
        for error_type, count in sorted(
            error_summary['error_types'].items(),
            key=lambda x: x[1],
            reverse=True
        ):
            rate = error_summary['error_rates'].get(error_type, 0)
            print(f"  • {error_type:30s}: {count:5d} errors  ({rate:6.2f}/min)")

    # Recent errors
    if error_summary['recent_errors']:
        print(f"\n🕒 RECENT ERRORS (Last 5):")
        for err in error_summary['recent_errors'][-5:]:
            timestamp = err['timestamp']
            error_type = err['error_type']
            message = err['error_message'][:60]
            severity = err['severity']

            severity_icon = {
                'CRITICAL': '🔴',
                'ERROR': '🟠',
                'WARNING': '🟡'
            }.get(severity, '⚪')

            print(f"  {severity_icon} [{timestamp}] {error_type}")
            print(f"     {message}")

    # Circuit Breakers
    print(f"\n⚡ CIRCUIT BREAKERS:")
    print("-" * 100)

    cb_stats = cb_manager.get_all_stats()

    if cb_stats:
        for name, stats in cb_stats.items():
            state = stats['state']
            state_icon = {
                'closed': '✅',
                'open': '❌',
                'half_open': '⚠️'
            }.get(state, '❓')

            print(f"{state_icon} {name:30s} State: {state.upper():10s} | "
                  f"Calls: {stats['total_calls']:5d} | "
                  f"Success: {stats['success_rate']:6s} | "
                  f"Failed: {stats['failed_calls']:4d} | "
                  f"Rejected: {stats['rejected_calls']:4d}")
    else:
        print("  No circuit breakers active")

    # Error rate trends
    print(f"\n📈 ERROR RATES (errors/min):")
    print("-" * 100)

    if error_summary['error_rates']:
        for error_type, rate in sorted(
            error_summary['error_rates'].items(),
            key=lambda x: x[1],
            reverse=True
        )[:10]:  # Top 10
            bar_length = int(min(rate * 2, 50))  # Visual bar
            bar = '█' * bar_length
            print(f"  {error_type:30s}: {rate:6.2f}/min {bar}")

    # Health indicators
    print(f"\n💚 HEALTH INDICATORS:")
    print("-" * 100)

    total_errors = error_summary['total_errors']
    if total_errors == 0:
        health_status = "✅ EXCELLENT - No errors"
    elif total_errors < 10:
        health_status = "✅ GOOD - Minor issues"
    elif total_errors < 50:
        health_status = "⚠️  WARNING - Moderate errors"
    else:
        health_status = "🔴 CRITICAL - Many errors"

    print(f"  System Health: {health_status}")

    # Check circuit breaker health
    open_circuits = sum(1 for s in cb_stats.values() if s['state'] == 'open')
    if open_circuits > 0:
        print(f"  ⚠️  {open_circuits} circuit breaker(s) OPEN")

    print("\n" + "=" * 100)
    print("Press Ctrl+C to exit | Refreshing every 5 seconds...")
    print("=" * 100)


def export_error_report(filepath: str):
    """Export detailed error report"""
    error_tracker = get_error_tracker()
    error_tracker.export_errors(filepath)
    print(f"✅ Error report exported to: {filepath}")


def main():
    """Main error monitoring loop"""
    parser = argparse.ArgumentParser(description='Error Monitoring Dashboard')
    parser.add_argument(
        '--interval',
        type=int,
        default=5,
        help='Refresh interval in seconds (default: 5)'
    )
    parser.add_argument(
        '--export',
        type=str,
        help='Export error report to file and exit'
    )
    parser.add_argument(
        '--once',
        action='store_true',
        help='Print dashboard once and exit'
    )

    args = parser.parse_args()

    # Export mode
    if args.export:
        export_error_report(args.export)
        return

    # Print once mode
    if args.once:
        print_dashboard()
        return

    # Continuous monitoring
    try:
        while True:
            print_dashboard()
            time.sleep(args.interval)

    except KeyboardInterrupt:
        print("\n\n👋 Monitoring stopped by user")

        # Print final summary
        error_tracker = get_error_tracker()
        cb_manager = get_circuit_breaker_manager()

        print("\n" + "=" * 100)
        print("FINAL SUMMARY")
        print("=" * 100)

        error_tracker.print_summary()
        cb_manager.print_summary()


if __name__ == "__main__":
    main()
