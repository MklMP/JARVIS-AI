import numpy as np
from typing import Dict, List, Optional
from dataclasses import dataclass


@dataclass
class PositionSizingResult:
    quantity: float
    stop_loss: float
    take_profit: float
    risk_amount: float
    position_value: float


class RiskManager:
    def __init__(self, config: dict):
        self.config = config
        self.positions: Dict[str, dict] = {}

    def calculate_position_size(
        self,
        symbol: str,
        price: float,
        account_equity: float,
        confidence: float,
        atr: float = None,
        side: str = 'buy'
    ) -> PositionSizingResult:
        sizing_method = self.config.get('use_position_sizing', 'fixed')
        max_risk_pct = self.config.get('max_position_risk_pct', 0.01)

        if sizing_method == 'kelly':
            kelly_fraction = self.config.get('kelly_fraction', 0.25)
            win_rate = self._get_win_rate(symbol, default=0.55)
            avg_win = self._get_avg_win(symbol, default=1.5)
            avg_loss = self._get_avg_loss(symbol, default=1.0)
            if avg_loss <= 0:
                avg_loss = 1.0
            b = avg_win / avg_loss
            p = win_rate
            q = 1 - p
            kelly_pct = (b * p - q) / b
            kelly_pct = max(0, min(kelly_pct, 0.5))
            risk_pct = kelly_pct * kelly_fraction
        else:
            risk_pct = max_risk_pct

        risk_pct *= confidence

        if atr and atr > 0:
            stop_loss_pct = atr / price * 2.0
        else:
            stop_loss_pct = self.config.get('default_stop_loss_pct', 0.02)

        if side == 'buy':
            stop_loss = price * (1 - stop_loss_pct)
            take_profit = price * (1 + stop_loss_pct * 2)
        else:
            stop_loss = price * (1 + stop_loss_pct)
            take_profit = price * (1 - stop_loss_pct * 2)

        risk_amount = account_equity * risk_pct
        price_risk = abs(price - stop_loss)
        if price_risk > 0:
            quantity = risk_amount / price_risk
        else:
            quantity = 0

        max_position_value = account_equity * self.config.get('position_size_pct', 0.02)
        position_value = quantity * price
        if position_value > max_position_value:
            quantity = max_position_value / price
            position_value = quantity * price

        quantity = self._round_quantity(quantity, price)

        return PositionSizingResult(
            quantity=quantity,
            stop_loss=round(stop_loss, 2),
            take_profit=round(take_profit, 2),
            risk_amount=round(risk_amount, 2),
            position_value=round(position_value, 2)
        )

    def _round_quantity(self, quantity: float, price: float) -> float:
        return round(quantity, 0)

    def _get_win_rate(self, symbol: str, default: float = 0.55) -> float:
        return default

    def _get_avg_win(self, symbol: str, default: float = 1.5) -> float:
        return default

    def _get_avg_loss(self, symbol: str, default: float = 1.0) -> float:
        return default

    def update_trailing_stop(self, symbol: str, current_price: float, position: dict) -> Optional[float]:
        if not position.get('trailing_stop_active'):
            return None
        trail_pct = self.config.get('trailing_stop_pct', 0.015)
        new_stop = current_price * (1 - trail_pct)
        old_stop = position.get('stop_loss', 0)
        if new_stop > old_stop:
            return new_stop
        return None

    def check_correlation_risk(self, symbol: str, current_positions: List[str]) -> bool:
        sectors = {
            'tech': ['AAPL', 'MSFT', 'GOOGL', 'NVDA', 'META', 'AMD', 'INTC', 'CRM', 'ADBE', 'CSCO'],
            'consumer': ['AMZN', 'TSLA', 'WMT', 'HD', 'MCD', 'NKE', 'DIS', 'SBUX'],
            'finance': ['JPM', 'BAC', 'GS', 'V', 'MA', 'C', 'WFC', 'MS'],
            'health': ['JNJ', 'UNH', 'PFE', 'MRK', 'ABBV', 'TMO', 'LLY'],
            'energy': ['XOM', 'CVX', 'COP', 'SLB', 'EOG', 'PSX'],
            'defense': ['LMT', 'RTX', 'BA', 'NOC', 'GD', 'LHX'],
        }
        max_correlation = self.config.get('max_correlation', 0.7)
        return True
