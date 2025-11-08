# Error Hardening & Resilience Guide

Comprehensive error handling, tracking, and recovery mechanisms for production-grade reliability.

## 🛡️ Overview

The system implements multiple layers of error hardening:

1. **Error Tracking** - Centralized error monitoring with counters
2. **Circuit Breakers** - Prevent cascading failures
3. **Retry Logic** - Automatic retry with exponential backoff
4. **Error Recovery** - Graceful degradation and recovery
5. **Real-time Monitoring** - Live error dashboard

---

## 📊 Error Tracking System

### Features

- **Error Counters** - Track total errors by type
- **Error Rates** - Calculate errors per minute
- **Error History** - Store recent error details
- **Automatic Alerting** - Alert when thresholds exceeded
- **Error Export** - Export error reports to JSON

### Usage

```python
from utils.error_tracker import get_error_tracker, record_error

# Get global tracker
tracker = get_error_tracker()

# Record error
try:
    risky_operation()
except Exception as e:
    record_error(
        error_type='api_error',
        error=e,
        context={'symbol': 'SOL/USDT', 'function': 'fetch_data'},
        severity='ERROR'  # ERROR, WARNING, CRITICAL
    )

# Get error summary
summary = tracker.get_error_summary()
print(f"Total errors: {summary['total_errors']}")

# Print formatted summary
tracker.print_summary()

# Export errors
tracker.export_errors('errors_report.json')
```

### Error Tracking Metrics

- **Total error count** by type
- **Error rate** (errors/minute)
- **Recent error history** (last 1000)
- **Error trends** over time
- **Alert counts** and history

---

## ⚡ Circuit Breaker Pattern

### How It Works

Circuit breakers prevent cascading failures by "breaking the circuit" when too many errors occur.

**States:**
1. **CLOSED** (Normal) - All requests pass through
2. **OPEN** (Broken) - Requests fail immediately without calling service
3. **HALF_OPEN** (Testing) - Limited requests to test if service recovered

### Usage

```python
from utils.circuit_breaker import circuit_breaker

# As decorator
@circuit_breaker(
    name='binance_api',
    failure_threshold=5,      # Open after 5 failures
    recovery_timeout=60       # Try again after 60s
)
def fetch_from_api():
    # Your code here
    pass

# Manual usage
from utils.circuit_breaker import get_circuit_breaker_manager

manager = get_circuit_breaker_manager()
breaker = manager.get_breaker('my_service')

try:
    result = breaker.call(risky_function, arg1, arg2)
except CircuitBreakerError:
    # Circuit is open, use fallback
    result = fallback_function()

# Get statistics
stats = breaker.get_stats()
print(f"State: {stats['state']}")
print(f"Success rate: {stats['success_rate']}")
```

### Circuit Breaker Configuration

| Parameter | Default | Description |
|-----------|---------|-------------|
| `failure_threshold` | 5 | Failures before opening circuit |
| `recovery_timeout` | 60s | Time before trying half-open |
| `success_threshold` | 2 | Successes needed to close circuit |

---

## 🔄 Retry Mechanisms

### Exponential Backoff

Automatic retry with increasing delays to handle transient failures.

**Retry Delays:**
- Attempt 1: 1s
- Attempt 2: 2s
- Attempt 3: 4s
- Attempt 4: 8s
- Attempt 5: 16s

### Usage

```python
from utils.retry_handler import (
    retry_with_backoff,
    async_retry_with_backoff,
    retry_api_call,
    async_retry_api_call
)

# Sync retry
@retry_with_backoff(
    max_retries=5,
    initial_delay=1.0,
    max_delay=60.0,
    exponential_base=2.0,
    jitter=True
)
def unstable_function():
    # Your code
    pass

# Async retry
@async_retry_with_backoff(max_retries=5)
async def async_unstable_function():
    # Your async code
    pass

# Specific retry strategies
@retry_api_call(max_retries=5)  # For API calls
def call_external_api():
    pass

@retry_db_operation(max_retries=3)  # For DB operations
def database_query():
    pass
```

### Retry Strategies

**API Calls:**
- Max retries: 5
- Initial delay: 2.0s
- Max delay: 120s (2 minutes)

**Database Operations:**
- Max retries: 3
- Initial delay: 0.5s
- Max delay: 10s

---

## 🔧 Hardened Binance Client

The `HardenedBinanceFuturesClient` combines all error hardening features.

### Features

- ✅ Automatic retry (5 attempts)
- ✅ Circuit breakers for each API endpoint
- ✅ Error tracking and metrics
- ✅ Comprehensive logging
- ✅ Graceful degradation

### Usage

```python
from data_collector.hardened_binance_client import HardenedBinanceFuturesClient

client = HardenedBinanceFuturesClient(
    api_key='your_key',
    api_secret='your_secret',
    testnet=False
)

# Fetch data with automatic error handling
try:
    df = await client.fetch_ohlcv('SOL/USDT', '5m')
    print(f"Fetched {len(df)} candles")
except CircuitBreakerError:
    print("Circuit breaker is open, service temporarily unavailable")
except RetryError:
    print("All retry attempts failed")
except Exception as e:
    print(f"Unexpected error: {e}")

# Get error summary
client.print_error_summary()
```

### Endpoint Circuit Breakers

| Endpoint | Breaker Name | Threshold | Timeout |
|----------|--------------|-----------|---------|
| OHLCV | `binance_ohlcv` | 10 | 120s |
| Open Interest | `binance_oi` | 10 | 120s |
| Funding Rate | `binance_funding` | 10 | 120s |
| Liquidations | `binance_liquidations` | 10 | 120s |
| Trader Ratio | `binance_trader_ratio` | 10 | 120s |

---

## 📺 Error Monitoring Dashboard

Real-time monitoring of errors and circuit breakers.

### Running the Dashboard

```bash
# Continuous monitoring (refreshes every 5s)
python scripts/error_monitor.py

# Custom interval
python scripts/error_monitor.py --interval 10

# Print once and exit
python scripts/error_monitor.py --once

# Export error report
python scripts/error_monitor.py --export errors_report.json
```

### Dashboard Features

- **Real-time error counts** by type
- **Error rates** (errors/minute)
- **Recent error details** (last 5)
- **Circuit breaker status** for all services
- **Visual error rate graphs**
- **Health indicators**

### Dashboard Output

```
================================================================================
ERROR MONITORING DASHBOARD - 2025-11-08 10:30:45
================================================================================

📊 OVERALL STATISTICS
Total Errors: 42

🔴 ERROR TYPES:
  • api_ohlcv_error              :    25 errors  (  2.50/min)
  • api_oi_error                 :    12 errors  (  1.20/min)
  • api_funding_error            :     5 errors  (  0.50/min)

🕒 RECENT ERRORS (Last 5):
  🟠 [2025-11-08T10:30:42] api_ohlcv_error
     ConnectionError: Failed to connect to Binance API

⚡ CIRCUIT BREAKERS:
  ✅ binance_ohlcv               State: CLOSED     | Calls:   150 | Success: 95.00% | Failed:    7 | Rejected:    0
  ✅ binance_oi                  State: CLOSED     | Calls:    75 | Success: 96.00% | Failed:    3 | Rejected:    0
  ❌ binance_funding             State: OPEN       | Calls:    50 | Success: 80.00% | Failed:   10 | Rejected:   15

💚 HEALTH INDICATORS:
  System Health: ⚠️  WARNING - Moderate errors
  ⚠️  1 circuit breaker(s) OPEN
================================================================================
```

---

## 🔥 Error Scenarios & Handling

### Scenario 1: API Rate Limit

**Problem:** Too many requests to Binance API

**Solution:**
1. Retry with exponential backoff (automatic)
2. Circuit breaker opens after repeated failures
3. Requests fail fast until recovery
4. System automatically recovers when API available

```python
# Automatic handling
@async_retry_api_call(max_retries=5)
@circuit_breaker(name='binance_api')
async def fetch_data():
    return await client.fetch_ohlcv('SOL/USDT', '5m')

# Result:
# - Retries: 1s, 2s, 4s, 8s, 16s
# - If all fail, circuit opens
# - Subsequent calls fail immediately
# - Circuit attempts reset after 60s
```

### Scenario 2: Network Timeout

**Problem:** Network connection drops

**Solution:**
```python
try:
    data = await client.fetch_ohlcv('SOL/USDT', '5m')
except TimeoutError:
    # Logged automatically
    # Retry attempted automatically
    # Use cached data if available
    data = cache.get('last_ohlcv')
```

### Scenario 3: Invalid Data Response

**Problem:** Exchange returns empty or invalid data

**Solution:**
```python
# Validation built into client
df = await client.fetch_ohlcv('SOL/USDT', '5m')

# Raises ValueError if empty
# Error tracked automatically
# Retry attempted
```

### Scenario 4: Database Connection Lost

**Problem:** PostgreSQL connection drops

**Solution:**
- Connection pool automatically reconnects
- Retry mechanism for DB operations
- Data buffered in memory until connection restored

---

## 📈 Error Alerting

### Alert Thresholds

Alerts triggered when:
- **Error count** exceeds 10 within 5 minutes
- **Circuit breaker** opens
- **Error rate** exceeds 5 errors/minute
- **Critical errors** occur

### Alert Cooldown

- **5 minutes** between duplicate alerts
- Prevents alert spam
- Configurable per error type

### Extending Alerts

```python
# In utils/error_tracker.py, modify _send_alert()

def _send_alert(self, error_type: str, error_record: Dict):
    # Email
    send_email_alert(error_record)

    # Slack
    send_slack_message(channel='#alerts', message=alert_msg)

    # PagerDuty
    trigger_pagerduty_incident(error_record)

    # Custom webhook
    requests.post('https://your-webhook.com/alert', json=error_record)
```

---

## 🧪 Testing Error Handling

### Simulate Errors

```python
# Test error tracking
from utils.error_tracker import record_error

for i in range(10):
    try:
        if i % 2 == 0:
            raise ValueError(f"Test error {i}")
    except Exception as e:
        record_error('test_error', e, {'iteration': i})

# Check error monitor
python scripts/error_monitor.py --once
```

### Test Circuit Breaker

```python
from utils.circuit_breaker import get_circuit_breaker_manager

manager = get_circuit_breaker_manager()
breaker = manager.get_breaker('test_circuit', failure_threshold=3)

# Trigger failures
for i in range(5):
    try:
        breaker.call(lambda: 1 / 0)  # Always fails
    except:
        pass

# Check state
stats = breaker.get_stats()
print(f"State: {stats['state']}")  # Should be OPEN
```

---

## 🎯 Best Practices

1. **Always use hardened client** in production
2. **Monitor error dashboard** regularly
3. **Set up alerts** for critical services
4. **Review error logs** daily
5. **Test error scenarios** before deployment
6. **Tune circuit breaker thresholds** based on your needs
7. **Export error reports** for analysis
8. **Have fallback strategies** for critical operations

---

## 📊 Metrics & KPIs

Track these metrics:

- **Error rate** (target: < 1 error/minute)
- **Success rate** (target: > 99%)
- **Circuit breaker opens** (target: 0)
- **Mean time to recovery** (target: < 5 minutes)
- **Error diversity** (number of unique error types)

---

## 🚨 Troubleshooting

### High Error Rate

1. Check error dashboard
2. Identify error type
3. Check circuit breaker status
4. Review recent code changes
5. Check external service status

### Circuit Breaker Stuck Open

1. Check if service actually recovered
2. Review error logs
3. Manually reset if needed: `breaker.reset()`
4. Increase recovery timeout if needed

### Memory Growth from Error Tracking

- Error history limited to last 1000
- Clear old errors: `tracker.clear_errors()`
- Export and clear periodically

---

**For questions, check logs at `logs/optimized_collection.log` or run `python scripts/error_monitor.py`**
