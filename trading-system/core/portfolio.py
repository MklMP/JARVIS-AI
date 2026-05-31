from typing import Dict, List, Optional
from datetime import datetime
from dataclasses import dataclass, field


@dataclass
class Position:
    symbol: str
    quantity: float
    entry_price: float
    current_price: float
    stop_loss: float
    take_profit: float
    side: str
    entry_time: datetime
    pnl: float = 0.0
    pnl_pct: float = 0.0
    trailing_stop_active: bool = True


@dataclass
class Trade:
    symbol: str
    side: str
    quantity: float
    price: float
    timestamp: datetime
    pnl: float = 0.0
    strategy: str = ''


class Portfolio:
    def __init__(self, initial_capital: float = 100000.0):
        self.initial_capital = initial_capital
        self.cash = initial_capital
        self.positions: Dict[str, Position] = {}
        self.trades: List[Trade] = []
        self.equity_curve: List[tuple] = []

    @property
    def total_equity(self) -> float:
        position_value = sum(p.quantity * p.current_price for p in self.positions.values())
        return self.cash + position_value

    @property
    def open_pnl(self) -> float:
        return sum(p.pnl for p in self.positions.values())

    @property
    def position_count(self) -> int:
        return len(self.positions)

    def can_open_position(self, max_positions: int = 5) -> bool:
        return len(self.positions) < max_positions

    def open_position(self, position: Position) -> bool:
        cost = position.quantity * position.entry_price
        if cost > self.cash:
            return False
        self.positions[position.symbol] = position
        self.cash -= cost
        return True

    def close_position(self, symbol: str, price: float, strategy: str = '') -> Optional[Trade]:
        if symbol not in self.positions:
            return None
        pos = self.positions.pop(symbol)
        pnl = pos.quantity * (price - pos.entry_price) if pos.side == 'buy' else pos.quantity * (pos.entry_price - price)
        self.cash += pos.quantity * price
        trade = Trade(
            symbol=symbol,
            side='sell' if pos.side == 'buy' else 'buy',
            quantity=pos.quantity,
            price=price,
            timestamp=datetime.now(),
            pnl=pnl,
            strategy=strategy
        )
        self.trades.append(trade)
        return trade

    def update_prices(self, prices: Dict[str, float]):
        for symbol, pos in self.positions.items():
            if symbol in prices:
                pos.current_price = prices[symbol]
                if pos.side == 'buy':
                    pos.pnl = pos.quantity * (pos.current_price - pos.entry_price)
                    pos.pnl_pct = (pos.current_price - pos.entry_price) / pos.entry_price
                else:
                    pos.pnl = pos.quantity * (pos.entry_price - pos.current_price)
                    pos.pnl_pct = (pos.entry_price - pos.current_price) / pos.entry_price

    def check_stops(self, prices: Dict[str, float]) -> List[Trade]:
        closed = []
        for symbol, pos in list(self.positions.items()):
            if symbol in prices:
                price = prices[symbol]
                if pos.side == 'buy':
                    if price <= pos.stop_loss or price >= pos.take_profit:
                        closed.append(self.close_position(symbol, price, 'stop_loss/take_profit'))
                else:
                    if price >= pos.stop_loss or price <= pos.take_profit:
                        closed.append(self.close_position(symbol, price, 'stop_loss/take_profit'))
        return [t for t in closed if t is not None]

    def get_total_pnl(self) -> float:
        total = self.total_equity - self.initial_capital
        return total

    def get_total_pnl_pct(self) -> float:
        return ((self.total_equity - self.initial_capital) / self.initial_capital) * 100

    def get_win_rate(self) -> float:
        if not self.trades:
            return 0.0
        wins = sum(1 for t in self.trades if t.pnl > 0)
        return wins / len(self.trades)

    def record_equity(self, timestamp: datetime = None):
        if timestamp is None:
            timestamp = datetime.now()
        self.equity_curve.append((timestamp, self.total_equity))
