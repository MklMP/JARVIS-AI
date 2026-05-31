import pandas as pd
from typing import Dict
from strategies.base import BaseStrategy


class VolumeProfileStrategy(BaseStrategy):
    def __init__(self, params: dict = None):
        super().__init__('volume_profile', params)
        self.lookback = self.params.get('lookback', 20)
        self.volume_threshold = self.params.get('volume_threshold', 1.5)

    def generate_signal(self, df: pd.DataFrame) -> Dict:
        df = self.prepare_data(df)
        if len(df) < self.lookback + 5:
            return {'action': 'hold', 'confidence': 0.0, 'price': float(df['close'].iloc[-1])}

        vol_ratio = df['volume_ratio'].iloc[-1]
        prev_vol_ratio = df['volume_ratio'].iloc[-2]
        close = df['close'].iloc[-1]
        prev_close = df['close'].iloc[-2]
        price = float(close)
        volume = df['volume'].iloc[-1]
        avg_volume = df['volume'].iloc[-self.lookback:].mean()

        vp = df['volume'].iloc[-self.lookback:] * df['close'].iloc[-self.lookback:]
        vwap = vp.sum() / df['volume'].iloc[-self.lookback:].sum() if df['volume'].iloc[-self.lookback:].sum() > 0 else price

        obv = df['obv'].iloc[-1]
        prev_obv = df['obv'].iloc[-2]

        volume_surge = vol_ratio > self.volume_threshold
        obv_rising = obv > prev_obv
        price_above_vwap = price > vwap
        climactic_volume = vol_ratio > 2.5

        if volume_surge and close > prev_close and obv_rising:
            if not climactic_volume:
                conf = min(0.5 + (vol_ratio - self.volume_threshold) * 0.3, 0.85)
                if price_above_vwap:
                    conf = min(conf + 0.1, 0.9)
                return {'action': 'buy', 'confidence': conf, 'price': price}

        if volume_surge and close < prev_close and not obv_rising:
            if not climactic_volume:
                conf = min(0.5 + (vol_ratio - self.volume_threshold) * 0.3, 0.85)
                if not price_above_vwap:
                    conf = min(conf + 0.1, 0.9)
                return {'action': 'sell', 'confidence': conf, 'price': price}

        if climactic_volume and close > prev_close:
            return {'action': 'sell', 'confidence': 0.5, 'price': price}
        if climactic_volume and close < prev_close:
            return {'action': 'buy', 'confidence': 0.5, 'price': price}

        if vol_ratio > 1.0 and close > prev_close:
            return {'action': 'buy', 'confidence': 0.2, 'price': price}

        return {'action': 'hold', 'confidence': 0.0, 'price': price}
