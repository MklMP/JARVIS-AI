import pandas as pd
from typing import Dict
from strategies.base import BaseStrategy


class BreakoutStrategy(BaseStrategy):
    def __init__(self, params: dict = None):
        super().__init__('breakout_strategy', params)
        self.lookback = self.params.get('lookback', 20)
        self.breakout_pct = self.params.get('breakout_pct', 0.02)
        self.volume_multiplier = self.params.get('volume_multiplier', 1.5)

    def generate_signal(self, df: pd.DataFrame) -> Dict:
        df = self.prepare_data(df)
        if len(df) < self.lookback + 5:
            return {'action': 'hold', 'confidence': 0.0, 'price': float(df['close'].iloc[-1])}

        segment = df.tail(self.lookback + 1).iloc[:-1]
        current = df.iloc[-1]
        prev = df.iloc[-2]
        price = float(current['close'])

        range_high = segment['high'].max()
        range_low = segment['low'].min()
        range_size = (range_high - range_low) / range_low

        breakout_up = current['close'] > range_high and prev['close'] <= range_high
        breakout_down = current['close'] < range_low and prev['close'] >= range_low

        vol_ratio = df['volume_ratio'].iloc[-1]
        rsi = df['rsi'].iloc[-1]
        adx = df['adx'].iloc[-1]

        if breakout_up and vol_ratio > self.volume_multiplier:
            conf = 0.5 + (vol_ratio - 1) * 0.2
            if rsi < 75:
                conf = min(conf + 0.1, 0.9)
            if adx > 25:
                conf = min(conf + 0.1, 0.95)
            return {'action': 'buy', 'confidence': conf, 'price': price}

        if breakout_down and vol_ratio > self.volume_multiplier:
            conf = 0.5 + (vol_ratio - 1) * 0.2
            if rsi > 25:
                conf = min(conf + 0.1, 0.9)
            if adx > 25:
                conf = min(conf + 0.1, 0.95)
            return {'action': 'sell', 'confidence': conf, 'price': price}

        if breakout_up:
            return {'action': 'buy', 'confidence': 0.35, 'price': price}
        if breakout_down:
            return {'action': 'sell', 'confidence': 0.35, 'price': price}

        near_resistance = abs(current['close'] - range_high) / range_high < 0.01
        near_support = abs(current['close'] - range_low) / range_low < 0.01

        if near_resistance and vol_ratio > 1.2:
            return {'action': 'buy', 'confidence': 0.2, 'price': price}
        if near_support and vol_ratio > 1.2:
            return {'action': 'sell', 'confidence': 0.2, 'price': price}

        return {'action': 'hold', 'confidence': 0.0, 'price': price}
