from typing import Dict, List, Optional
from datetime import datetime
import random
from broker.base import BaseBroker, OrderResult
from utils.logger import setup_logger


class PaperBroker(BaseBroker):
    def __init__(self, initial_capital: float = 100000.0):
        self.logger = setup_logger("paper_broker")
        self.initial_capital = initial_capital
        self.cash = initial_capital
        self.positions: Dict[str, Dict] = {}
        self.orders: List[Dict] = []
        self.trades: List[Dict] = []

    def place_order(self, symbol: str, side: str, quantity: float,
                    order_type: str = 'market', price: float = None,
                    stop_loss: float = None, take_profit: float = None) -> OrderResult:
        order_id = f"paper_{int(datetime.now().timestamp())}_{random.randint(1000, 9999)}"

        if price is None:
            price = 100.0

        cost = quantity * price
        if side == 'buy' and cost > self.cash:
            self.logger.warning(f"Insufficient funds: ${cost:.2f} > ${self.cash:.2f}")
            return OrderResult(
                order_id=order_id, symbol=symbol, side=side,
                quantity=quantity, price=price, status='rejected'
            )

        if side == 'buy':
            self.cash -= cost
            self.positions[symbol] = {
                'symbol': symbol,
                'quantity': quantity,
                'entry_price': price,
                'current_price': price,
                'side': side,
                'stop_loss': stop_loss,
                'take_profit': take_profit
            }
        else:
            self.cash += cost
            if symbol in self.positions:
                pos = self.positions.pop(symbol)
                pnl = quantity * (price - pos['entry_price'])
                self.trades.append({
                    'symbol': symbol, 'side': 'sell', 'quantity': quantity,
                    'entry_price': pos['entry_price'], 'exit_price': price,
                    'pnl': pnl, 'timestamp': datetime.now()
                })

        order = OrderResult(
            order_id=order_id, symbol=symbol, side=side,
            quantity=quantity, price=price, status='filled',
            filled_quantity=quantity, avg_fill_price=price
        )
        self.orders.append(order)
        self.logger.info(f"Paper {side} {quantity} {symbol} @ ${price:.2f}")
        return order

    def cancel_order(self, order_id: str) -> bool:
        return True

    def get_positions(self) -> List[Dict]:
        return list(self.positions.values())

    def get_account_info(self) -> Dict:
        position_value = sum(
            p['quantity'] * p['current_price'] for p in self.positions.values()
        )
        return {
            'total_equity': round(self.cash + position_value, 2),
            'cash': round(self.cash, 2),
            'positions': len(self.positions),
            'buying_power': round(self.cash, 2),
            'total_pnl': round(self.cash + position_value - self.initial_capital, 2)
        }

    def get_bars(self, symbol: str, timeframe: str = '15m', limit: int = 100) -> List[Dict]:
        return []
