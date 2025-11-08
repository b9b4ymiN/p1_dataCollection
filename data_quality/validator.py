"""
Data Quality Monitor
Monitors data quality and detects anomalies
"""

import pandas as pd
from typing import Dict
import logging

logger = logging.getLogger(__name__)


class DataQualityMonitor:
    """
    Monitors data quality and detects anomalies
    """

    def validate_ohlcv(self, df: pd.DataFrame, timeframe: str = '5m') -> Dict[str, bool]:
        """
        Validate OHLCV data integrity

        Args:
            df: DataFrame with OHLCV data
            timeframe: Candlestick interval

        Returns:
            Dictionary with validation results
        """
        checks = {}

        if df.empty:
            logger.warning("DataFrame is empty")
            return {'empty': True}

        # Check for nulls
        checks['no_nulls'] = not df.isnull().any().any()
        if not checks['no_nulls']:
            null_cols = df.columns[df.isnull().any()].tolist()
            logger.warning(f"Null values found in columns: {null_cols}")

        # Check OHLC relationship
        checks['valid_ohlc'] = (
            (df['high'] >= df['low']).all() and
            (df['high'] >= df['open']).all() and
            (df['high'] >= df['close']).all() and
            (df['low'] <= df['open']).all() and
            (df['low'] <= df['close']).all()
        )
        if not checks['valid_ohlc']:
            logger.warning("Invalid OHLC relationships detected")

        # Check for duplicates
        checks['no_duplicates'] = not df.duplicated(subset=['timestamp']).any()
        if not checks['no_duplicates']:
            duplicates = df.duplicated(subset=['timestamp']).sum()
            logger.warning(f"Found {duplicates} duplicate timestamps")

        # Check time continuity (no large gaps)
        if 'timestamp' in df.columns:
            time_diffs = df['timestamp'].diff().dt.total_seconds()
            expected_diff = self._get_expected_diff(timeframe)
            checks['continuous_time'] = (time_diffs[1:] <= expected_diff * 1.5).all()
            if not checks['continuous_time']:
                gaps = time_diffs[time_diffs > expected_diff * 1.5].count()
                logger.warning(f"Found {gaps} time gaps in data")

        # Check for outliers (price spikes > 10%)
        returns = df['close'].pct_change()
        checks['no_extreme_spikes'] = (returns.abs() < 0.10).all()
        if not checks['no_extreme_spikes']:
            spikes = (returns.abs() >= 0.10).sum()
            logger.warning(f"Found {spikes} extreme price spikes (>10%)")

        # Check for negative prices
        checks['positive_prices'] = (
            (df['open'] > 0).all() and
            (df['high'] > 0).all() and
            (df['low'] > 0).all() and
            (df['close'] > 0).all()
        )

        return checks

    def validate_oi(self, df: pd.DataFrame) -> Dict[str, bool]:
        """
        Validate OI data

        Args:
            df: DataFrame with OI data

        Returns:
            Dictionary with validation results
        """
        checks = {}

        if df.empty:
            logger.warning("DataFrame is empty")
            return {'empty': True}

        # Check for nulls
        checks['no_nulls'] = not df.isnull().any().any()
        if not checks['no_nulls']:
            null_cols = df.columns[df.isnull().any()].tolist()
            logger.warning(f"Null values found in columns: {null_cols}")

        # Check positive OI
        if 'sumOpenInterest' in df.columns:
            checks['positive_oi'] = (df['sumOpenInterest'] >= 0).all()
        elif 'open_interest' in df.columns:
            checks['positive_oi'] = (df['open_interest'] >= 0).all()
        else:
            checks['positive_oi'] = False
            logger.error("No open_interest column found")

        # Check for duplicates
        checks['no_duplicates'] = not df.duplicated(subset=['timestamp']).any()
        if not checks['no_duplicates']:
            duplicates = df.duplicated(subset=['timestamp']).sum()
            logger.warning(f"Found {duplicates} duplicate timestamps")

        # OI shouldn't change more than 50% in one period (unless exceptional event)
        oi_col = 'sumOpenInterest' if 'sumOpenInterest' in df.columns else 'open_interest'
        if oi_col in df.columns:
            oi_pct_change = df[oi_col].pct_change().abs()
            checks['reasonable_changes'] = (oi_pct_change < 0.50).all()
            if not checks['reasonable_changes']:
                large_changes = (oi_pct_change >= 0.50).sum()
                logger.warning(f"Found {large_changes} large OI changes (>50%)")

        return checks

    def validate_funding_rate(self, df: pd.DataFrame) -> Dict[str, bool]:
        """
        Validate funding rate data

        Args:
            df: DataFrame with funding rate data

        Returns:
            Dictionary with validation results
        """
        checks = {}

        if df.empty:
            return {'empty': True}

        checks['no_nulls'] = not df.isnull().any().any()
        checks['no_duplicates'] = not df.duplicated(subset=['fundingTime']).any()

        # Funding rates are typically between -0.5% and 0.5%
        if 'fundingRate' in df.columns:
            checks['reasonable_rates'] = (
                (df['fundingRate'] >= -0.005).all() and
                (df['fundingRate'] <= 0.005).all()
            )

        return checks

    @staticmethod
    def _get_expected_diff(timeframe: str) -> float:
        """
        Get expected time difference in seconds

        Args:
            timeframe: Candlestick interval

        Returns:
            Expected difference in seconds
        """
        mapping = {'1m': 60, '5m': 300, '15m': 900, '1h': 3600, '4h': 14400, '1d': 86400}
        return mapping.get(timeframe, 300)

    def generate_quality_report(self, checks: Dict[str, bool]) -> str:
        """
        Generate a human-readable quality report

        Args:
            checks: Dictionary of validation checks

        Returns:
            Formatted report string
        """
        passed = sum(1 for v in checks.values() if v)
        total = len(checks)
        percentage = (passed / total * 100) if total > 0 else 0

        report = f"\nData Quality Report:\n"
        report += f"=" * 50 + "\n"
        report += f"Passed: {passed}/{total} ({percentage:.1f}%)\n"
        report += f"-" * 50 + "\n"

        for check, result in checks.items():
            status = "✅ PASS" if result else "❌ FAIL"
            report += f"{check}: {status}\n"

        report += f"=" * 50 + "\n"

        return report
