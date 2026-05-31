import os
import json
import threading
import time
from typing import Dict, Optional, Callable
from datetime import datetime
from utils.logger import setup_logger


class AlpacaStream:
    def __init__(self, api_key: str = None, api_secret: str = None, paper: bool = True):
        self.api_key = api_key or os.getenv('ALPACA_API_KEY', '')
        self.api_secret = api_secret or os.getenv('ALPACA_API_SECRET', '')
        self.paper = paper
        self.logger = setup_logger("alpaca_stream")
        self._running = False
        self._thread = None
        self._prices: Dict[str, float] = {}
        self._trades: Dict[str, dict] = {}
        self._callbacks: list = []
        self._connected = False

    def connect(self):
        if not self.api_key or not self.api_secret:
            self.logger.warning("ALPACA: No API keys. Set ALPACA_API_KEY y ALPACA_API_SECRET en .env")
            return False
        try:
            from alpaca.trading.client import TradingClient
            from alpaca.data.live import StockDataStream

            self._trade_client = TradingClient(self.api_key, self.api_secret, paper=self.paper)
            self._stream = StockDataStream(self.api_key, self.api_secret)

            account = self._trade_client.get_account()
            self.logger.info(f"ALPACA: Conectado! Equity=${float(account.equity):.2f} "
                           f"Cash=${float(account.cash):.2f} (paper={self.paper})")
            self._connected = True
            return True
        except ImportError:
            self.logger.error("ALPACA: pip install alpaca-py")
            return False
        except Exception as e:
            self.logger.error(f"ALPACA: Error conexion: {e}")
            return False

    def subscribe_symbols(self, symbols: list, callback: Callable = None):
        if not self._connected:
            self.logger.error("ALPACA: Conecta primero")
            return
        try:
            async def handler(data):
                try:
                    sym = data.symbol
                    price = float(data.price)
                    self._prices[sym] = price
                    self._trades[sym] = {
                        'price': price,
                        'timestamp': datetime.now().isoformat(),
                        'volume': getattr(data, 'volume', 0)
                    }
                    if callback:
                        callback(sym, price)
                except Exception:
                    pass

            for sym in symbols:
                self._stream.subscribe_trades(handler, sym)
                self.logger.info(f"ALPACA: Suscrito a {sym}")

            self._running = True
            self._thread = threading.Thread(target=self._run_loop, daemon=True)
            self._thread.start()
        except Exception as e:
            self.logger.error(f"ALPACA: Error subscription: {e}")

    def _run_loop(self):
        try:
            self._stream.run()
        except Exception as e:
            self.logger.error(f"ALPACA: Stream error: {e}")
            self._running = False

    def get_price(self, symbol: str) -> Optional[float]:
        return self._prices.get(symbol)

    def get_all_prices(self) -> Dict[str, float]:
        return dict(self._prices)

    def get_account(self) -> Dict:
        if not self._connected:
            return {'error': 'No conectado'}
        try:
            acc = self._trade_client.get_account()
            positions = self._trade_client.get_all_positions()
            return {
                'equity': float(acc.equity),
                'cash': float(acc.cash),
                'buying_power': float(acc.buying_power),
                'positions': len(positions),
                'status': acc.status,
                'day_change': float(acc.equity) - float(acc.last_equity) if hasattr(acc, 'last_equity') else 0
            }
        except Exception as e:
            return {'error': str(e)}

    def place_order(self, symbol: str, side: str, qty: int, order_type: str = 'market'):
        if not self._connected:
            return {'error': 'No conectado'}
        try:
            from alpaca.trading.requests import MarketOrderRequest
            from alpaca.trading.enums import OrderSide, TimeInForce
            req = MarketOrderRequest(
                symbol=symbol,
                qty=qty,
                side=OrderSide.BUY if side == 'buy' else OrderSide.SELL,
                time_in_force=TimeInForce.DAY
            )
            order = self._trade_client.submit_order(req)
            self.logger.info(f"ORDEN: {side.upper()} {qty} {symbol} (ID: {order.id})")
            return {'id': order.id, 'status': order.status, 'qty': qty, 'symbol': symbol}
        except Exception as e:
            self.logger.error(f"Orden fallo: {e}")
            return {'error': str(e)}

    def close(self):
        self._running = False
        if hasattr(self, '_stream'):
            try:
                self._stream.close()
            except Exception:
                pass
        self.logger.info("ALPACA: Desconectado")
