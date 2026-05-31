import pandas as pd
from typing import Dict
from strategies.base import BaseStrategy
from utils.indicators import detect_divergence


class RSIStrategy(BaseStrategy):
    def __init__(self, params: dict = None):
        super().__init__('rsi_strategy', params)
        self.period = self.params.get('period', 14)
        self.oversold = self.params.get('oversold', 30)
        self.overbought = self.params.get('overbought', 70)

    def generate_signal(self, df: pd.DataFrame) -> Dict:
        df = self.prepare_data(df)
        if len(df) < 30:
            return {'action': 'hold', 'confidence': 0.0, 'price': float(df['close'].iloc[-1])}

        rsi = df['rsi'].iloc[-1]
        prev_rsi = df['rsi'].iloc[-2]
        price = float(df['close'].iloc[-1])
        divergence = detect_divergence(df)

        if rsi < self.oversold and rsi > prev_rsi:
            conf = max(0.5, 1.0 - (rsi / self.oversold) * 0.5)
            if divergence.get('rsi_bullish_div'):
                conf = min(conf + 0.3, 0.95)
            return {'action': 'buy', 'confidence': conf, 'price': price}

        if rsi > self.overbought and rsi < prev_rsi:
            conf = max(0.5, (rsi / 100 - 0.5) * 2)
            if divergence.get('rsi_bearish_div'):
                conf = min(conf + 0.3, 0.95)
            return {'action': 'sell', 'confidence': conf, 'price': price}

        if 40 < rsi < 60:
            return {'action': 'hold', 'confidence': 0.0, 'price': price}

        if rsi < self.oversold:
            return {'action': 'buy', 'confidence': 0.3, 'price': price}
        if rsi > self.overbought:
            return {'action': 'sell', 'confidence': 0.3, 'price': price}

        return {'action': 'hold', 'confidence': 0.0, 'price': price}
