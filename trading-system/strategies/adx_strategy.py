import pandas as pd
from typing import Dict
from strategies.base import BaseStrategy


class ADXStrategy(BaseStrategy):
    def __init__(self, params: dict = None):
        super().__init__('adx_strategy', params)
        self.period = self.params.get('period', 14)
        self.threshold = self.params.get('threshold', 25)

    def generate_signal(self, df: pd.DataFrame) -> Dict:
        df = self.prepare_data(df)
        if len(df) < 30:
            return {'action': 'hold', 'confidence': 0.0, 'price': float(df['close'].iloc[-1])}

        adx = df['adx'].iloc[-1]
        prev_adx = df['adx'].iloc[-2]
        close = df['close'].iloc[-1]
        prev_close = df['close'].iloc[-2]
        price = float(close)
        rsi = df['rsi'].iloc[-1]

        if adx < self.threshold:
            return {'action': 'hold', 'confidence': 0.0, 'price': price}

        trend_strength = min((adx - self.threshold) / 25, 1.0)

        if close > prev_close and adx > prev_adx:
            if rsi < 70:
                conf = 0.5 + trend_strength * 0.4
                if adx > 40:
                    conf = min(conf + 0.1, 0.9)
                return {'action': 'buy', 'confidence': conf, 'price': price}

        if close < prev_close and adx > prev_adx:
            if rsi > 30:
                conf = 0.5 + trend_strength * 0.4
                if adx > 40:
                    conf = min(conf + 0.1, 0.9)
                return {'action': 'sell', 'confidence': conf, 'price': price}

        if adx > 40:
            if close > prev_close:
                return {'action': 'buy', 'confidence': 0.45, 'price': price}
            else:
                return {'action': 'sell', 'confidence': 0.45, 'price': price}

        return {'action': 'hold', 'confidence': 0.0, 'price': price}
