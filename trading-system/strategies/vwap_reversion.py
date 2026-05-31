import pandas as pd
import numpy as np
from typing import Dict
from strategies.base import BaseStrategy


class VWAPReversionStrategy(BaseStrategy):
    def __init__(self, params: dict = None):
        super().__init__('vwap_reversion', params)
        self.std_dev_threshold = self.params.get('std_dev_threshold', 2.0)
        self.lookback = self.params.get('lookback', 20)

    def generate_signal(self, df: pd.DataFrame) -> Dict:
        df = self.prepare_data(df)
        if len(df) < self.lookback + 5:
            return {'action': 'hold', 'confidence': 0.0, 'price': float(df['close'].iloc[-1])}

        close = df['close']
        volume = df['volume']
        high = df['high']
        low = df['low']
        price = float(close.iloc[-1])

        typical_price = (high + low + close) / 3
        vwap = (typical_price * volume).cumsum() / volume.cumsum()

        vwap_diff = ((typical_price - vwap) ** 2 * volume).cumsum() / volume.cumsum()
        vwap_std = np.sqrt(vwap_diff)

        current_vwap = vwap.iloc[-1]
        current_std = vwap_std.iloc[-1]
        price_from_vwap = (price - current_vwap) / current_std if current_std > 0 else 0

        rsi = df['rsi'].iloc[-1]
        bb_position = df['bb_position'].iloc[-1]

        if price_from_vwap < -self.std_dev_threshold:
            conf = min(abs(price_from_vwap) / (self.std_dev_threshold * 2), 0.9)
            if rsi < 30 and bb_position < 0.2:
                conf = min(conf + 0.1, 0.95)
            return {'action': 'buy', 'confidence': conf, 'price': price}

        if price_from_vwap > self.std_dev_threshold:
            conf = min(price_from_vwap / (self.std_dev_threshold * 2), 0.9)
            if rsi > 70 and bb_position > 0.8:
                conf = min(conf + 0.1, 0.95)
            return {'action': 'sell', 'confidence': conf, 'price': price}

        if price < current_vwap and price_from_vwap < -1.0:
            return {'action': 'buy', 'confidence': 0.3, 'price': price}
        if price > current_vwap and price_from_vwap > 1.0:
            return {'action': 'sell', 'confidence': 0.3, 'price': price}

        return {'action': 'hold', 'confidence': 0.0, 'price': price}
