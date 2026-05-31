import pandas as pd
import numpy as np
from typing import Dict
from strategies.base import BaseStrategy


class FibonacciRetracementStrategy(BaseStrategy):
    def __init__(self, params: dict = None):
        super().__init__('fibonacci_retracement', params)
        self.lookback = self.params.get('lookback', 50)
        self.levels = self.params.get('levels', [0.236, 0.382, 0.5, 0.618, 0.786])

    def generate_signal(self, df: pd.DataFrame) -> Dict:
        df = self.prepare_data(df)
        if len(df) < self.lookback:
            return {'action': 'hold', 'confidence': 0.0, 'price': float(df['close'].iloc[-1])}

        segment = df.tail(self.lookback)
        high = segment['high'].max()
        low = segment['low'].min()
        high_idx = segment['high'].idxmax()
        low_idx = segment['low'].idxmin()
        price = float(df['close'].iloc[-1])

        if high_idx < low_idx:
            trend = 'downtrend'
            range_val = high - low
            fib_levels = {lvl: high - lvl * range_val for lvl in self.levels}
        else:
            trend = 'uptrend'
            range_val = high - low
            fib_levels = {lvl: low + lvl * range_val for lvl in self.levels}

        rsi = df['rsi'].iloc[-1]
        signals = []

        if trend == 'uptrend':
            for level_val in [0.382, 0.5, 0.618]:
                fib_price = fib_levels[level_val]
                proximity = abs(price - fib_price) / fib_price
                if proximity < 0.003 and price >= fib_price:
                    conf = 0.4 + (0.618 / level_val) * 0.3 if level_val >= 0.5 else 0.5
                    if level_val >= 0.618 and rsi < 50:
                        conf = min(conf + 0.2, 0.9)
                    signals.append(('buy', conf))

        elif trend == 'downtrend':
            for level_val in [0.382, 0.5, 0.618]:
                fib_price = fib_levels[level_val]
                proximity = abs(price - fib_price) / fib_price
                if proximity < 0.003 and price <= fib_price:
                    conf = 0.4 + (0.618 / level_val) * 0.3 if level_val >= 0.5 else 0.5
                    if level_val >= 0.618 and rsi > 50:
                        conf = min(conf + 0.2, 0.9)
                    signals.append(('sell', conf))

        if signals:
            best = max(signals, key=lambda x: x[1])
            return {'action': best[0], 'confidence': best[1], 'price': price}

        fib_618 = fib_levels.get(0.618, 0)
        fib_382 = fib_levels.get(0.382, 0)
        if trend == 'uptrend' and price < fib_618 and price > low:
            return {'action': 'buy', 'confidence': 0.3, 'price': price}
        if trend == 'downtrend' and price > fib_618 and price < high:
            return {'action': 'sell', 'confidence': 0.3, 'price': price}

        return {'action': 'hold', 'confidence': 0.0, 'price': price}
