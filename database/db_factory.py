"""
Database Factory
Factory pattern for creating database managers based on configuration
"""

import logging
from typing import Union
from enum import Enum

logger = logging.getLogger(__name__)


class DatabaseType(Enum):
    """Supported database types"""
    POSTGRESQL = "postgresql"
    SQLITE = "sqlite"
    FIREBASE = "firebase"


class DatabaseFactory:
    """
    Factory for creating database manager instances

    Supports:
    - PostgreSQL + TimescaleDB (production, high-performance)
    - SQLite (local development, lightweight)
    - Firebase Realtime Database (cloud-hosted, zero infrastructure)
    """

    @staticmethod
    def create_database(config: dict) -> Union['SQLiteManager', 'FirebaseManager']:
        """
        Create database manager based on configuration

        Args:
            config: Configuration dictionary with 'database_type' key

        Returns:
            Database manager instance

        Raises:
            ValueError: If database_type is invalid or configuration is missing
        """
        db_type = config.get('database_type', 'sqlite').lower()

        logger.info(f"🔧 Creating database manager: {db_type}")

        if db_type == DatabaseType.POSTGRESQL.value:
            return DatabaseFactory._create_postgresql(config)
        elif db_type == DatabaseType.SQLITE.value:
            return DatabaseFactory._create_sqlite(config)
        elif db_type == DatabaseType.FIREBASE.value:
            return DatabaseFactory._create_firebase(config)
        else:
            raise ValueError(f"Unsupported database type: {db_type}. "
                           f"Supported types: postgresql, sqlite, firebase")

    @staticmethod
    def _create_postgresql(config: dict):
        """Create PostgreSQL manager (not implemented in this version)"""
        # Note: PostgreSQL support would require additional implementation
        # For now, we'll raise an error directing users to use optimized_collector.py
        raise NotImplementedError(
            "PostgreSQL support is available through the original collectors. "
            "Use scripts/main_historical_collection.py for PostgreSQL. "
            "This unified collector supports SQLite and Firebase only."
        )

    @staticmethod
    def _create_sqlite(config: dict):
        """Create SQLite manager"""
        from database.sqlite_manager import SQLiteManager

        sqlite_config = config.get('sqlite', {})
        database_path = sqlite_config.get('database_path', 'data/futures_data.db')

        manager = SQLiteManager(database_path=database_path)
        manager.initialize()

        logger.info(f"✅ SQLite manager created: {database_path}")
        return manager

    @staticmethod
    def _create_firebase(config: dict):
        """Create Firebase manager"""
        from database.firebase_manager import FirebaseManager

        firebase_config = config.get('firebase', {})

        service_account_path = firebase_config.get('service_account_path')
        database_url = firebase_config.get('database_url')

        if not service_account_path or not database_url:
            raise ValueError(
                "Firebase configuration incomplete. Required: "
                "service_account_path and database_url in config.yaml"
            )

        manager = FirebaseManager(
            service_account_path=service_account_path,
            database_url=database_url
        )
        manager.initialize()

        logger.info(f"✅ Firebase manager created: {database_url}")
        return manager

    @staticmethod
    def get_supported_types() -> list:
        """Get list of supported database types"""
        return [db_type.value for db_type in DatabaseType]

    @staticmethod
    def validate_config(config: dict) -> tuple[bool, str]:
        """
        Validate database configuration

        Args:
            config: Configuration dictionary

        Returns:
            Tuple of (is_valid, error_message)
        """
        db_type = config.get('database_type', 'sqlite').lower()

        if db_type not in DatabaseFactory.get_supported_types():
            return False, f"Invalid database_type: {db_type}. Supported: {DatabaseFactory.get_supported_types()}"

        if db_type == DatabaseType.FIREBASE.value:
            firebase_config = config.get('firebase', {})
            if not firebase_config.get('service_account_path'):
                return False, "Firebase service_account_path is required"
            if not firebase_config.get('database_url'):
                return False, "Firebase database_url is required"

        if db_type == DatabaseType.SQLITE.value:
            sqlite_config = config.get('sqlite', {})
            database_path = sqlite_config.get('database_path', 'data/futures_data.db')
            # Check if directory is writable
            import os
            directory = os.path.dirname(database_path) or '.'
            if not os.path.exists(directory):
                try:
                    os.makedirs(directory, exist_ok=True)
                except Exception as e:
                    return False, f"Cannot create directory for SQLite database: {e}"

        return True, ""
