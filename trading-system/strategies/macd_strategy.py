import pandas as pd
from typing import Dict
from strategies.base import BaseStrategy


class MACDStrategy(BaseStrategy):
    def __init__(self, params: dict = None):
        super().__init__('macd_strategy', params)
        self.fast = self.params.get('fast', 12)
        self.slow = self.params.get('slow', 26)
        self.signal = self.params.get('signal', 9)

    def generate_signal(self, df: pd.DataFrame) -> Dict:
        df = self.prepare_data(df)
        if len(df) < 35:
            return {'action': 'hold', 'confidence': 0.0, 'price': float(df['close'].iloc[-1])}

        macd = df['macd'].iloc[-1]
        signal = df['macd_signal'].iloc[-1]
        hist = df['macd_diff'].iloc[-1]
        prev_macd = df['macd'].iloc[-2]
        prev_signal = df['macd_signal'].iloc[-2]
        prev_hist = df['macd_diff'].iloc[-2]
        price = float(df['close'].iloc[-1])

        if prev_macd <= prev_signal and macd > signal:
            conf = min(abs(macd - signal) * 5, 0.9)
            if hist > 0 and prev_hist <= 0:
                conf = min(conf + 0.1, 0.95)
            return {'action': 'buy', 'confidence': conf, 'price': price}

        if prev_macd >= prev_signal and macd < signal:
            conf = min(abs(macd - signal) * 5, 0.9)
            if hist < 0 and prev_hist >= 0:
                conf = min(conf + 0.1, 0.95)
            return {'action': 'sell', 'confidence': conf, 'price': price}

        if macd > signal and hist > 0 and hist > prev_hist:
            return {'action': 'buy', 'confidence': 0.35, 'price': price}
        if macd < signal and hist < 0 and hist < prev_hist:
            return {'action': 'sell', 'confidence': 0.35, 'price': price}

        return {'action': 'hold', 'confidence': 0.0, 'price': price}
