"""
Firebase Real-time WebSocket Streaming Script
Streams live cryptocurrency futures data to Firebase Realtime Database
"""

import yaml
import logging
import sys
import os
import signal

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.firebase_manager import FirebaseManager
from data_collector.firebase_websocket import FirebaseWebSocketStreamer
from pythonjsonlogger import jsonlogger

# Setup logging
log_handler = logging.StreamHandler()
formatter = jsonlogger.JsonFormatter()
log_handler.setFormatter(formatter)

logger = logging.getLogger()
logger.addHandler(log_handler)
logger.setLevel(logging.INFO)

# Global streamer for graceful shutdown
streamer = None


def signal_handler(sig, frame):
    """Handle CTRL+C gracefully"""
    logger.info("\n⚠️ Shutdown signal received...")
    if streamer:
        streamer.stop()
    sys.exit(0)


def main():
    """Main streaming function"""
    global streamer

    # Register signal handler
    signal.signal(signal.SIGINT, signal_handler)

    # Load configuration
    config_path = 'config.yaml'
    if not os.path.exists(config_path):
        logger.error("❌ config.yaml not found. Please create one from config.yaml.example")
        return

    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)

    # Load Firebase configuration
    firebase_config = config.get('firebase', {})
    if not firebase_config:
        logger.error("❌ Firebase configuration not found in config.yaml")
        logger.info("Please add Firebase configuration:")
        logger.info("firebase:")
        logger.info("  service_account_path: 'path/to/service-account.json'")
        logger.info("  database_url: 'https://your-project.firebaseio.com'")
        return

    service_account_path = firebase_config.get('service_account_path')
    database_url = firebase_config.get('database_url')

    if not service_account_path or not database_url:
        logger.error("❌ Firebase credentials missing")
        return

    # Initialize Firebase
    firebase = FirebaseManager(service_account_path, database_url)
    firebase.initialize()

    # Get symbols to stream
    collection_config = config['collection']
    symbols = collection_config['symbols']

    logger.info(f"🔥 Firebase Real-time Streaming")
    logger.info(f"📊 Symbols: {', '.join(symbols)}")
    logger.info(f"🔌 Connecting to Binance WebSocket...")

    # Create and start streamer
    streamer = FirebaseWebSocketStreamer(symbols, firebase)

    logger.info("✅ Streaming started. Press CTRL+C to stop.")
    logger.info("=" * 60)

    # Start streaming (blocking call)
    streamer.start()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        sys.exit(1)
