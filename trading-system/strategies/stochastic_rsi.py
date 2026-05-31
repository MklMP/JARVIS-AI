import pandas as pd
from typing import Dict
from strategies.base import BaseStrategy


class StochasticRSIStrategy(BaseStrategy):
    def __init__(self, params: dict = None):
        super().__init__('stochastic_rsi', params)
        self.oversold = self.params.get('oversold', 20)
        self.overbought = self.params.get('overbought', 80)

    def generate_signal(self, df: pd.DataFrame) -> Dict:
        df = self.prepare_data(df)
        if len(df) < 30:
            return {'action': 'hold', 'confidence': 0.0, 'price': float(df['close'].iloc[-1])}

        k = df['stoch_k'].iloc[-1]
        d = df['stoch_d'].iloc[-1]
        prev_k = df['stoch_k'].iloc[-2]
        prev_d = df['stoch_d'].iloc[-2]
        rsi = df['rsi'].iloc[-1]
        price = float(df['close'].iloc[-1])

        if prev_k <= prev_d and k > d:
            if k < self.oversold:
                conf = min(0.5 + (self.oversold - k) / self.oversold * 0.4, 0.9)
                if rsi < 30:
                    conf = min(conf + 0.1, 0.95)
                return {'action': 'buy', 'confidence': conf, 'price': price}
            elif k < 40 and rsi < 40:
                return {'action': 'buy', 'confidence': 0.4, 'price': price}

        if prev_k >= prev_d and k < d:
            if k > self.overbought:
                conf = min(0.5 + (k - self.overbought) / (100 - self.overbought) * 0.4, 0.9)
                if rsi > 70:
                    conf = min(conf + 0.1, 0.95)
                return {'action': 'sell', 'confidence': conf, 'price': price}
            elif k > 60 and rsi > 60:
                return {'action': 'sell', 'confidence': 0.4, 'price': price}

        if k < self.oversold and d < self.oversold:
            return {'action': 'buy', 'confidence': 0.3, 'price': price}
        if k > self.overbought and d > self.overbought:
            return {'action': 'sell', 'confidence': 0.3, 'price': price}

        return {'action': 'hold', 'confidence': 0.0, 'price': price}
