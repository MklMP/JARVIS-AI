import pandas as pd
from typing import Dict
from strategies.base import BaseStrategy


class SMACrossoverStrategy(BaseStrategy):
    def __init__(self, params: dict = None):
        super().__init__('sma_crossover', params)
        self.fast = self.params.get('fast_period', 9)
        self.slow = self.params.get('slow_period', 21)

    def generate_signal(self, df: pd.DataFrame) -> Dict:
        df = self.prepare_data(df)
        if len(df) < self.slow + 1:
            return {'action': 'hold', 'confidence': 0.0, 'price': float(df['close'].iloc[-1])}

        current_fast = df['sma_9'].iloc[-1]
        current_slow = df['sma_21'].iloc[-1]
        prev_fast = df['sma_9'].iloc[-2]
        prev_slow = df['sma_21'].iloc[-2]
        price = float(df['close'].iloc[-1])

        if prev_fast <= prev_slow and current_fast > current_slow:
            confidence = min(abs(current_fast / current_slow - 1) * 10, 0.95)
            return {'action': 'buy', 'confidence': confidence, 'price': price}
        elif prev_fast >= prev_slow and current_fast < current_slow:
            confidence = min(abs(current_fast / current_slow - 1) * 10, 0.95)
            return {'action': 'sell', 'confidence': confidence, 'price': price}

        ema_9 = df['ema_9'].iloc[-1]
        ema_21 = df['ema_21'].iloc[-1]
        if ema_9 > ema_21 and price > current_fast:
            return {'action': 'buy', 'confidence': 0.3, 'price': price}
        elif ema_9 < ema_21 and price < current_fast:
            return {'action': 'sell', 'confidence': 0.3, 'price': price}

        return {'action': 'hold', 'confidence': 0.0, 'price': price}
