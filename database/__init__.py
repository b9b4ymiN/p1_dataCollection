"""
Database Module
Supports multiple database backends with automatic switching
"""

from database.db_factory import DatabaseFactory, DatabaseType
from database.sqlite_manager import SQLiteManager
from database.firebase_manager import FirebaseManager

__all__ = [
    'DatabaseFactory',
    'DatabaseType',
    'SQLiteManager',
    'FirebaseManager',
]
