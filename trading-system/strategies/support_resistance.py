import pandas as pd
import numpy as np
from typing import Dict, List
from strategies.base import BaseStrategy


class SupportResistanceStrategy(BaseStrategy):
    def __init__(self, params: dict = None):
        super().__init__('support_resistance', params)
        self.lookback = self.params.get('lookback', 100)
        self.proximity_pct = self.params.get('proximity_pct', 0.005)

    def _find_support_resistance(self, df: pd.DataFrame) -> tuple:
        high = df['high'].values
        low = df['low'].values
        close = df['close'].values

        resistance_levels = []
        support_levels = []

        for i in range(2, len(high) - 2):
            if high[i] > high[i - 1] and high[i] > high[i - 2] and high[i] > high[i + 1] and high[i] > high[i + 2]:
                resistance_levels.append(high[i])
            if low[i] < low[i - 1] and low[i] < low[i - 2] and low[i] < low[i + 1] and low[i] < low[i + 2]:
                support_levels.append(low[i])

        if not support_levels:
            support_levels.append(df['low'].min())
        if not resistance_levels:
            resistance_levels.append(df['high'].max())

        resistance = np.median(resistance_levels) if resistance_levels else df['high'].max()
        support = np.median(support_levels) if support_levels else df['low'].min()

        return support, resistance

    def generate_signal(self, df: pd.DataFrame) -> Dict:
        df = self.prepare_data(df)
        if len(df) < self.lookback:
            return {'action': 'hold', 'confidence': 0.0, 'price': float(df['close'].iloc[-1])}

        segment = df.tail(self.lookback)
        price = float(df['close'].iloc[-1])
        support, resistance = self._find_support_resistance(segment)

        proximity = self.proximity_pct * price
        rsi = df['rsi'].iloc[-1]
        volume_ratio = df['volume_ratio'].iloc[-1]
        bb_position = df['bb_position'].iloc[-1]

        at_support = abs(price - support) < proximity
        at_resistance = abs(price - resistance) < proximity

        if at_support:
            if rsi < 40 or bb_position < 0.3:
                conf = 0.65
                if volume_ratio > 1.2:
                    conf = min(conf + 0.1, 0.9)
                return {'action': 'buy', 'confidence': conf, 'price': price}
            return {'action': 'buy', 'confidence': 0.4, 'price': price}

        if at_resistance:
            if rsi > 60 or bb_position > 0.7:
                conf = 0.65
                if volume_ratio > 1.2:
                    conf = min(conf + 0.1, 0.9)
                return {'action': 'sell', 'confidence': conf, 'price': price}
            return {'action': 'sell', 'confidence': 0.4, 'price': price}

        if price < support and rsi < 30:
            return {'action': 'buy', 'confidence': 0.35, 'price': price}
        if price > resistance and rsi > 70:
            return {'action': 'sell', 'confidence': 0.35, 'price': price}

        return {'action': 'hold', 'confidence': 0.0, 'price': price}
