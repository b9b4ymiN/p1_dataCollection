"""
Optimized WebSocket Streamer
High-performance real-time data streaming with reduced latency
"""

import websocket
import json
import threading
from datetime import datetime
from typing import List, Dict
import redis
import logging
from collections import deque
import time
import msgpack  # For binary serialization

logger = logging.getLogger(__name__)


class OptimizedWebSocketStreamer:
    """
    High-performance WebSocket streamer with:
    - Binary message packing for reduced bandwidth
    - Message batching for reduced Redis operations
    - Circular buffer for rate smoothing
    - Connection health monitoring
    """

    def __init__(self, symbols: List[str], redis_client: redis.Redis, batch_size: int = 10):
        self.symbols = [s.lower().replace('/', '') for s in symbols]
        self.redis = redis_client
        self.batch_size = batch_size
        self.ws = None
        self.running = False
        self.reconnect_attempts = 0

        # Performance optimizations
        self.message_buffer = deque(maxlen=1000)
        self.batch_buffer = []
        self.last_batch_time = time.time()
        self.batch_interval = 0.1  # 100ms batching

        # Metrics
        self.messages_received = 0
        self.messages_processed = 0
        self.last_message_time = time.time()

        # Start batch processor thread
        self.batch_thread = threading.Thread(target=self._batch_processor, daemon=True)
        self.batch_thread.start()

    def start(self):
        """Start WebSocket connection with optimizations"""
        self.running = True

        # Construct stream URL with combined streams
        streams = []
        for symbol in self.symbols:
            streams.append(f"{symbol}@aggTrade")      # Aggregate trades (lower latency than kline)
            streams.append(f"{symbol}@markPrice@1s")  # Mark price every 1 second
            streams.append(f"{symbol}@bookTicker")    # Best bid/ask

        stream_url = f"wss://fstream.binance.com/stream?streams={'/'.join(streams)}"

        logger.info(f"Connecting to optimized WebSocket with {len(streams)} streams")

        self.ws = websocket.WebSocketApp(
            stream_url,
            on_message=self.on_message,
            on_error=self.on_error,
            on_close=self.on_close,
            on_open=self.on_open,
            on_ping=self.on_ping
        )

        # Run with optimized settings
        ws_thread = threading.Thread(
            target=lambda: self.ws.run_forever(
                ping_interval=20,  # Send ping every 20s
                ping_timeout=10,   # Timeout after 10s
                skip_utf8_validation=True  # Skip validation for speed
            ),
            daemon=True
        )
        ws_thread.start()

    def on_message(self, ws, message):
        """Handle incoming WebSocket message with batching"""
        try:
            self.messages_received += 1
            self.last_message_time = time.time()

            # Parse message
            data = json.loads(message)
            stream = data.get('stream', '')
            payload = data.get('data', {})

            # Add to batch buffer
            self.batch_buffer.append((stream, payload))

            # Process batch if size reached or time elapsed
            current_time = time.time()
            if len(self.batch_buffer) >= self.batch_size or \
               (current_time - self.last_batch_time) >= self.batch_interval:
                self._process_batch()

        except Exception as e:
            logger.error(f"Error processing message: {e}")

    def _batch_processor(self):
        """Background thread for batch processing"""
        while self.running:
            time.sleep(self.batch_interval)
            if self.batch_buffer:
                self._process_batch()

    def _process_batch(self):
        """Process batch of messages efficiently"""
        if not self.batch_buffer:
            return

        try:
            # Process all messages in batch
            pipeline = self.redis.pipeline()

            for stream, payload in self.batch_buffer:
                if '@aggTrade' in stream:
                    self._cache_trade_batch(payload, pipeline)
                elif '@markPrice' in stream:
                    self._cache_mark_price_batch(payload, pipeline)
                elif '@bookTicker' in stream:
                    self._cache_book_ticker_batch(payload, pipeline)

            # Execute all Redis operations at once
            pipeline.execute()

            self.messages_processed += len(self.batch_buffer)
            self.batch_buffer.clear()
            self.last_batch_time = time.time()

        except Exception as e:
            logger.error(f"Batch processing error: {e}")
            self.batch_buffer.clear()

    def _cache_trade_batch(self, data: dict, pipeline):
        """Cache aggregate trade data using pipeline"""
        try:
            symbol = data['s']
            key = f"latest_trade:{symbol}"

            # Use msgpack for smaller payload
            value = msgpack.packb({
                'time': data['T'],  # Trade time
                'price': float(data['p']),
                'quantity': float(data['q']),
                'is_buyer_maker': data['m']
            })

            pipeline.setex(key, 60, value)  # TTL 1 minute

        except Exception as e:
            logger.error(f"Error caching trade: {e}")

    def _cache_mark_price_batch(self, data: dict, pipeline):
        """Cache mark price using pipeline"""
        try:
            symbol = data['s']
            key = f"latest_mark:{symbol}"

            # Use msgpack for binary serialization
            value = msgpack.packb({
                'time': data['E'],
                'mark_price': float(data['p']),
                'index_price': float(data['i']),
                'funding_rate': float(data['r']),
                'next_funding': data['T']
            })

            pipeline.setex(key, 60, value)

        except Exception as e:
            logger.error(f"Error caching mark price: {e}")

    def _cache_book_ticker_batch(self, data: dict, pipeline):
        """Cache best bid/ask using pipeline"""
        try:
            symbol = data['s']
            key = f"latest_book:{symbol}"

            value = msgpack.packb({
                'time': data['E'],
                'best_bid': float(data['b']),
                'best_bid_qty': float(data['B']),
                'best_ask': float(data['a']),
                'best_ask_qty': float(data['A'])
            })

            pipeline.setex(key, 60, value)

        except Exception as e:
            logger.error(f"Error caching book ticker: {e}")

    def on_ping(self, ws, message):
        """Handle ping with immediate pong"""
        ws.pong(message)

    def on_error(self, ws, error):
        logger.error(f"WebSocket Error: {error}")

    def on_close(self, ws, close_status_code, close_msg):
        logger.warning(f"WebSocket closed: {close_status_code} - {close_msg}")
        if self.running:
            # Exponential backoff for reconnection
            backoff = min(60, 2 ** self.reconnect_attempts)
            logger.info(f"Reconnecting in {backoff}s...")
            time.sleep(backoff)
            self.reconnect_attempts += 1
            self.start()

    def on_open(self, ws):
        logger.info("✅ Optimized WebSocket connection opened")
        self.reconnect_attempts = 0

    def get_metrics(self) -> Dict:
        """Get performance metrics"""
        latency = (time.time() - self.last_message_time) * 1000  # ms
        return {
            'messages_received': self.messages_received,
            'messages_processed': self.messages_processed,
            'batch_buffer_size': len(self.batch_buffer),
            'latency_ms': latency,
            'messages_per_second': self.messages_received / max(1, time.time() - self.last_message_time)
        }

    def stop(self):
        """Stop WebSocket connection"""
        self.running = False
        if self.ws:
            self.ws.close()
        logger.info("WebSocket streamer stopped")
