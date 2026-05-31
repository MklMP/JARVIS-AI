from typing import Dict, List, Optional
from datetime import datetime
import os
from broker.base import BaseBroker, OrderResult
from utils.logger import setup_logger


class AlpacaBroker(BaseBroker):
    def __init__(self, config: dict):
        self.logger = setup_logger("alpaca_broker")
        self.config = config
        self.api_key = config.get('alpaca', {}).get('api_key') or os.getenv('ALPACA_API_KEY', '')
        self.api_secret = config.get('alpaca', {}).get('api_secret') or os.getenv('ALPACA_API_SECRET', '')
        self.base_url = config.get('alpaca', {}).get('base_url', 'https://paper-api.alpaca.markets')
        self.data_url = config.get('alpaca', {}).get('data_url', 'https://data.alpaca.markets')
        self.paper_trading = config.get('alpaca', {}).get('paper_trading', True)
        self._api = None

    def _ensure_api(self):
        if self._api is None:
            try:
                from alpaca.trading.client import TradingClient
                self._api = TradingClient(self.api_key, self.api_secret, paper=self.paper_trading)
                self.logger.info("Alpaca API connected")
            except Exception as e:
                self.logger.error(f"Failed to connect to Alpaca: {e}")
                raise

    def place_order(self, symbol: str, side: str, quantity: float,
                    order_type: str = 'market', price: float = None,
                    stop_loss: float = None, take_profit: float = None) -> OrderResult:
        self._ensure_api()
        try:
            from alpaca.trading.requests import MarketOrderRequest, LimitOrderRequest, StopLossRequest, TakeProfitRequest
            from alpaca.trading.enums import OrderSide, OrderType, TimeInForce

            if order_type == 'market':
                order_request = MarketOrderRequest(
                    symbol=symbol,
                    qty=abs(int(quantity)),
                    side=OrderSide.BUY if side == 'buy' else OrderSide.SELL,
                    time_in_force=TimeInForce.DAY
                )
            else:
                order_request = LimitOrderRequest(
                    symbol=symbol,
                    qty=abs(int(quantity)),
                    side=OrderSide.BUY if side == 'buy' else OrderSide.SELL,
                    limit_price=price,
                    time_in_force=TimeInForce.DAY
                )

            order = self._api.submit_order(order_request)

            return OrderResult(
                order_id=order.id,
                symbol=symbol,
                side=side,
                quantity=quantity,
                price=float(order.filled_avg_price) if order.filled_avg_price else (price or 0),
                status=order.status,
                filled_quantity=float(order.filled_qty) if order.filled_qty else 0,
                avg_fill_price=float(order.filled_avg_price) if order.filled_avg_price else 0
            )
        except Exception as e:
            self.logger.error(f"Order failed for {symbol}: {e}")
            return OrderResult(
                order_id='', symbol=symbol, side=side,
                quantity=quantity, price=price or 0, status='rejected'
            )

    def cancel_order(self, order_id: str) -> bool:
        self._ensure_api()
        try:
            self._api.cancel_order_by_id(order_id)
            return True
        except Exception as e:
            self.logger.error(f"Cancel failed: {e}")
            return False

    def get_positions(self) -> List[Dict]:
        self._ensure_api()
        try:
            positions = self._api.get_all_positions()
            return [
                {
                    'symbol': p.symbol,
                    'quantity': float(p.qty),
                    'entry_price': float(p.avg_entry_price),
                    'current_price': float(p.current_price),
                    'pnl': float(p.unrealized_pl),
                    'pnl_pct': float(p.unrealized_plpc) * 100
                }
                for p in positions
            ]
        except Exception as e:
            self.logger.error(f"Failed to get positions: {e}")
            return []

    def get_account_info(self) -> Dict:
        self._ensure_api()
        try:
            account = self._api.get_account()
            return {
                'total_equity': float(account.equity),
                'cash': float(account.cash),
                'buying_power': float(account.buying_power),
                'positions': int(account.position_market_value) > 0,
                'status': account.status,
                'pattern_day_trader': account.pattern_day_trader,
            }
        except Exception as e:
            self.logger.error(f"Failed to get account: {e}")
            return {}

    def get_bars(self, symbol: str, timeframe: str = '15m', limit: int = 100) -> List[Dict]:
        self._ensure_api()
        try:
            from alpaca.data.requests import StockBarsRequest
            from alpaca.data.timeframe import TimeFrame, TimeFrameUnit
            from alpaca.data.historical import StockHistoricalDataClient

            client = StockHistoricalDataClient(self.api_key, self.api_secret)
            tf_map = {
                '1m': TimeFrame(1, TimeFrameUnit.Minute),
                '5m': TimeFrame(5, TimeFrameUnit.Minute),
                '15m': TimeFrame(15, TimeFrameUnit.Minute),
                '1h': TimeFrame(1, TimeFrameUnit.Hour),
                '1d': TimeFrame(1, TimeFrameUnit.Day),
            }

            request = StockBarsRequest(
                symbol_or_symbols=[symbol],
                timeframe=tf_map.get(timeframe, TimeFrame(15, TimeFrameUnit.Minute)),
                limit=limit
            )
            bars = client.get_stock_bars(request)
            if symbol in bars:
                return [{
                    'timestamp': b.timestamp,
                    'open': b.open, 'high': b.high,
                    'low': b.low, 'close': b.close,
                    'volume': b.volume
                } for b in bars[symbol]]
            return []
        except Exception as e:
            self.logger.error(f"Failed to get bars: {e}")
            return []
