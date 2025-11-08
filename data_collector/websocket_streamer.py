"""
WebSocket Streamer
Real-time data streaming via WebSocket
"""

import websocket
import json
import threading
from datetime import datetime
from typing import List
import redis
import logging

logger = logging.getLogger(__name__)


class BinanceWebSocketStreamer:
    """
    Real-time data streaming via WebSocket
    """

    def __init__(self, symbols: List[str], redis_client: redis.Redis):
        self.symbols = [s.lower().replace('/', '') for s in symbols]
        self.redis = redis_client
        self.ws = None
        self.running = False
        self.reconnect_attempts = 0

    def start(self):
        """Start WebSocket connection"""
        self.running = True

        # Construct stream URL
        streams = []
        for symbol in self.symbols:
            streams.append(f"{symbol}@kline_5m")      # Price
            streams.append(f"{symbol}@markPrice")     # Mark price

        stream_url = f"wss://fstream.binance.com/stream?streams={'/'.join(streams)}"

        self.ws = websocket.WebSocketApp(
            stream_url,
            on_message=self.on_message,
            on_error=self.on_error,
            on_close=self.on_close,
            on_open=self.on_open,
            on_ping=self.on_ping
        )

        # Run in separate thread
        ws_thread = threading.Thread(target=self.ws.run_forever)
        ws_thread.daemon = True
        ws_thread.start()

    def on_message(self, ws, message):
        """Handle incoming WebSocket message"""
        try:
            data = json.loads(message)
            stream = data.get('stream', '')
            payload = data.get('data', {})

            # Cache latest data in Redis
            if '@kline' in stream:
                self._cache_kline(payload)
            elif '@markPrice' in stream:
                self._cache_mark_price(payload)
        except Exception as e:
            logger.error(f"Error processing message: {e}")

    def _cache_kline(self, data):
        """Cache latest kline data"""
        try:
            kline = data['k']
            symbol = kline['s']

            key = f"latest_kline:{symbol}"
            value = {
                'time': datetime.fromtimestamp(kline['t'] / 1000).isoformat(),
                'close': float(kline['c']),
                'volume': float(kline['v']),
                'is_closed': kline['x']
            }

            self.redis.setex(key, 300, json.dumps(value))  # TTL 5 minutes
            logger.debug(f"Cached kline for {symbol}")
        except Exception as e:
            logger.error(f"Error caching kline: {e}")

    def _cache_mark_price(self, data):
        """Cache mark price and funding rate"""
        try:
            symbol = data['s']

            key = f"latest_mark:{symbol}"
            value = {
                'time': datetime.fromtimestamp(data['E'] / 1000).isoformat(),
                'mark_price': float(data['p']),
                'funding_rate': float(data['r']),
                'next_funding': datetime.fromtimestamp(data['T'] / 1000).isoformat()
            }

            self.redis.setex(key, 300, json.dumps(value))
            logger.debug(f"Cached mark price for {symbol}")
        except Exception as e:
            logger.error(f"Error caching mark price: {e}")

    def on_ping(self, ws, message):
        """Handle ping message"""
        ws.pong(message)

    def on_error(self, ws, error):
        logger.error(f"WebSocket Error: {error}")

    def on_close(self, ws, close_status_code, close_msg):
        logger.warning(f"WebSocket connection closed: {close_status_code} - {close_msg}")
        if self.running:
            # Auto-reconnect with exponential backoff
            backoff = min(60, 2 ** self.reconnect_attempts)
            logger.info(f"Reconnecting in {backoff}s...")
            import time
            time.sleep(backoff)
            self.reconnect_attempts += 1
            self.start()

    def on_open(self, ws):
        logger.info("WebSocket connection opened")
        self.reconnect_attempts = 0  # Reset counter on successful connection

    def stop(self):
        """Stop WebSocket connection"""
        self.running = False
        if self.ws:
            self.ws.close()
        logger.info("WebSocket streamer stopped")
