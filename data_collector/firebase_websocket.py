"""
Firebase WebSocket Streamer
Real-time cryptocurrency data streaming to Firebase Realtime Database
"""

import websocket
import json
import logging
from datetime import datetime
from typing import List
from database.firebase_manager import FirebaseManager

logger = logging.getLogger(__name__)


class FirebaseWebSocketStreamer:
    """
    WebSocket streamer that pushes real-time data to Firebase

    Streams:
    - Real-time candlestick data (klines)
    - Mark price updates
    - Liquidation orders
    """

    def __init__(self, symbols: List[str], firebase_manager: FirebaseManager):
        """
        Initialize WebSocket streamer

        Args:
            symbols: List of trading symbols (e.g., ['SOL/USDT', 'BTC/USDT'])
            firebase_manager: Initialized FirebaseManager instance
        """
        self.symbols = symbols
        self.firebase = firebase_manager
        self.ws = None
        self.running = False

    def start(self):
        """Start WebSocket streaming"""
        # Convert symbols to Binance format (e.g., 'SOL/USDT' -> 'solusdt')
        binance_symbols = [s.replace('/', '').lower() for s in self.symbols]

        # Build stream URL
        streams = []
        for symbol in binance_symbols:
            streams.append(f"{symbol}@kline_5m")  # 5-minute candlesticks
            streams.append(f"{symbol}@markPrice")  # Mark price updates
            streams.append(f"{symbol}@forceOrder")  # Liquidations

        stream_url = f"wss://fstream.binance.com/stream?streams={'/'.join(streams)}"

        logger.info(f"🔌 Connecting to Binance WebSocket: {len(streams)} streams")

        self.ws = websocket.WebSocketApp(
            stream_url,
            on_message=self.on_message,
            on_error=self.on_error,
            on_close=self.on_close,
            on_open=self.on_open
        )

        self.running = True
        self.ws.run_forever()

    def on_message(self, ws, message):
        """Handle incoming WebSocket message"""
        try:
            data = json.loads(message)

            if 'stream' not in data or 'data' not in data:
                return

            stream = data['stream']
            payload = data['data']

            # Route to appropriate handler based on stream type
            if '@kline_' in stream:
                self._handle_kline(payload)
            elif '@markPrice' in stream:
                self._handle_mark_price(payload)
            elif '@forceOrder' in stream:
                self._handle_liquidation(payload)

        except Exception as e:
            logger.error(f"Error processing message: {e}")

    def _handle_kline(self, data: dict):
        """Handle candlestick data"""
        try:
            kline = data['k']

            # Only process closed candles
            if not kline['x']:  # x = is candle closed
                return

            symbol = data['s']  # e.g., 'SOLUSDT'
            # Convert to standard format (e.g., 'SOL/USDT')
            if symbol.endswith('USDT'):
                formatted_symbol = f"{symbol[:-4]}/USDT"
            else:
                formatted_symbol = symbol

            # Extract timeframe (e.g., '5m')
            timeframe = kline['i']

            # Prepare data
            import pandas as pd
            df = pd.DataFrame([{
                'timestamp': pd.to_datetime(kline['T'], unit='ms'),  # Close time
                'open': float(kline['o']),
                'high': float(kline['h']),
                'low': float(kline['l']),
                'close': float(kline['c']),
                'volume': float(kline['v']),
                'quote_volume': float(kline['q']),
                'num_trades': int(kline['n']),
                'taker_buy_base': float(kline['V']),
                'taker_buy_quote': float(kline['Q']),
            }])

            # Save to Firebase (synchronous call - runs in WebSocket thread)
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(
                self.firebase.save_ohlcv_batch(df, formatted_symbol, timeframe)
            )
            loop.close()

            logger.debug(f"📊 {formatted_symbol} {timeframe} candle closed: {kline['c']}")

        except Exception as e:
            logger.error(f"Error handling kline: {e}")

    def _handle_mark_price(self, data: dict):
        """Handle mark price update"""
        try:
            symbol = data['s']
            if symbol.endswith('USDT'):
                formatted_symbol = f"{symbol[:-4]}/USDT"
            else:
                formatted_symbol = symbol

            mark_price = float(data['p'])
            timestamp = pd.to_datetime(data['E'], unit='ms')

            logger.debug(f"💰 {formatted_symbol} mark price: {mark_price}")

            # Note: Mark price updates are very frequent
            # Consider storing only snapshots or using Redis for caching

        except Exception as e:
            logger.error(f"Error handling mark price: {e}")

    def _handle_liquidation(self, data: dict):
        """Handle liquidation order"""
        try:
            order = data['o']
            symbol = order['s']

            if symbol.endswith('USDT'):
                formatted_symbol = f"{symbol[:-4]}/USDT"
            else:
                formatted_symbol = symbol

            # Prepare data
            import pandas as pd
            df = pd.DataFrame([{
                'time': pd.to_datetime(order['T'], unit='ms'),
                'side': order['S'],  # BUY or SELL
                'price': float(order['p']),
                'quantity': float(order['q']),
                'order_id': int(data['E']),  # Use event time as ID
            }])

            # Save to Firebase
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(
                self.firebase.save_liquidations_batch(df, formatted_symbol)
            )
            loop.close()

            logger.info(f"⚠️ {formatted_symbol} liquidation: {order['S']} {order['q']} @ {order['p']}")

        except Exception as e:
            logger.error(f"Error handling liquidation: {e}")

    def on_error(self, ws, error):
        """Handle WebSocket error"""
        logger.error(f"WebSocket error: {error}")

    def on_close(self, ws, close_status_code, close_msg):
        """Handle WebSocket close"""
        logger.warning(f"WebSocket closed: {close_status_code} - {close_msg}")
        self.running = False

    def on_open(self, ws):
        """Handle WebSocket open"""
        logger.info("✅ WebSocket connection established")

    def stop(self):
        """Stop WebSocket streaming"""
        if self.ws:
            self.running = False
            self.ws.close()
            logger.info("WebSocket streaming stopped")
