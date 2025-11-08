"""
Real-time WebSocket Streaming Script
Starts WebSocket connections for real-time data streaming
"""

import redis
import yaml
import sys
import logging
import signal
import time
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data_collector.websocket_streamer import BinanceWebSocketStreamer


# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class StreamManager:
    """Manager for WebSocket streams with graceful shutdown"""

    def __init__(self, config):
        self.config = config
        self.streamers = []
        self.running = True

        # Setup signal handlers
        signal.signal(signal.SIGINT, self.shutdown)
        signal.signal(signal.SIGTERM, self.shutdown)

    def start(self):
        """Start all WebSocket streams"""
        logger.info("Starting real-time data streaming...")

        # Connect to Redis
        redis_config = self.config['redis']
        try:
            redis_client = redis.Redis(
                host=redis_config['host'],
                port=redis_config['port'],
                db=redis_config['db'],
                password=redis_config.get('password', None),
                decode_responses=False
            )
            # Test connection
            redis_client.ping()
            logger.info(f"Connected to Redis at {redis_config['host']}:{redis_config['port']}")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            sys.exit(1)

        # Get symbols from config
        symbols = self.config['collection']['symbols']
        logger.info(f"Streaming symbols: {', '.join(symbols)}")

        # Create and start streamer
        streamer = BinanceWebSocketStreamer(symbols, redis_client)
        streamer.start()
        self.streamers.append(streamer)

        logger.info("✅ WebSocket streams started successfully!")
        logger.info("Press Ctrl+C to stop...")

        # Keep running
        try:
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            self.shutdown(None, None)

    def shutdown(self, signum, frame):
        """Graceful shutdown"""
        logger.info("\n🛑 Graceful shutdown initiated...")
        self.running = False

        # Stop all streamers
        for streamer in self.streamers:
            streamer.stop()

        logger.info("✅ Cleanup complete. Exiting.")
        sys.exit(0)


def load_config(config_path='config.yaml'):
    """Load configuration from YAML file"""
    try:
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        logger.error(f"Configuration file not found: {config_path}")
        sys.exit(1)


def main():
    """Main entry point"""
    config = load_config()
    manager = StreamManager(config)
    manager.start()


if __name__ == "__main__":
    main()
