from abc import ABC, abstractmethod
from typing import Dict, List, Optional
from dataclasses import dataclass


@dataclass
class OrderResult:
    order_id: str
    symbol: str
    side: str
    quantity: float
    price: float
    status: str
    filled_quantity: float = 0.0
    avg_fill_price: float = 0.0


class BaseBroker(ABC):
    @abstractmethod
    def place_order(self, symbol: str, side: str, quantity: float,
                    order_type: str = 'market', price: float = None,
                    stop_loss: float = None, take_profit: float = None) -> OrderResult:
        pass

    @abstractmethod
    def cancel_order(self, order_id: str) -> bool:
        pass

    @abstractmethod
    def get_positions(self) -> List[Dict]:
        pass

    @abstractmethod
    def get_account_info(self) -> Dict:
        pass

    @abstractmethod
    def get_bars(self, symbol: str, timeframe: str = '15m', limit: int = 100) -> List[Dict]:
        pass
