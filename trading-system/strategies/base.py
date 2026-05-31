from abc import ABC, abstractmethod
from typing import Dict, Optional
import pandas as pd
from utils.indicators import add_all_indicators


class BaseStrategy(ABC):
    def __init__(self, name: str, params: dict = None):
        self.name = name
        self.params = params or {}
        self.signal_history = []

    @abstractmethod
    def generate_signal(self, df: pd.DataFrame) -> Dict:
        pass

    def prepare_data(self, df: pd.DataFrame) -> pd.DataFrame:
        if not all(c in df.columns for c in ['rsi', 'macd']):
            df = add_all_indicators(df)
        return df

    def get_confidence(self, signal: str, df: pd.DataFrame) -> float:
        return 0.5

    def __repr__(self) -> str:
        return f"{self.name}(params={self.params})"
