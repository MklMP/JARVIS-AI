import pandas as pd
from typing import Dict
from strategies.base import BaseStrategy


class EMATrendStrategy(BaseStrategy):
    def __init__(self, params: dict = None):
        super().__init__('ema_trend', params)
        self.fast = self.params.get('fast_ema', 9)
        self.medium = self.params.get('medium_ema', 21)
        self.slow = self.params.get('slow_ema', 50)

    def generate_signal(self, df: pd.DataFrame) -> Dict:
        df = self.prepare_data(df)
        if len(df) < self.slow + 5:
            return {'action': 'hold', 'confidence': 0.0, 'price': float(df['close'].iloc[-1])}

        ema_9 = df['ema_9'].iloc[-1]
        ema_21 = df['ema_21'].iloc[-1]
        ema_50 = df['ema_50'].iloc[-1]
        prev_ema_9 = df['ema_9'].iloc[-2]
        prev_ema_21 = df['ema_21'].iloc[-2]
        price = float(df['close'].iloc[-1])
        rsi = df['rsi'].iloc[-1]

        bullish_alignment = ema_9 > ema_21 > ema_50
        bearish_alignment = ema_9 < ema_21 < ema_50

        ema_distance = abs(ema_9 - ema_21) / ema_21

        if prev_ema_9 <= prev_ema_21 and ema_9 > ema_21:
            if bullish_alignment:
                conf = min(0.5 + ema_distance * 5, 0.9)
                return {'action': 'buy', 'confidence': conf, 'price': price}
            else:
                return {'action': 'buy', 'confidence': 0.4, 'price': price}

        if prev_ema_9 >= prev_ema_21 and ema_9 < ema_21:
            if bearish_alignment:
                conf = min(0.5 + ema_distance * 5, 0.9)
                return {'action': 'sell', 'confidence': conf, 'price': price}
            else:
                return {'action': 'sell', 'confidence': 0.4, 'price': price}

        if bullish_alignment and price > ema_9:
            conf = 0.45 + (price / ema_9 - 1) * 2
            if rsi < 70:
                return {'action': 'buy', 'confidence': min(conf, 0.75), 'price': price}

        if bearish_alignment and price < ema_9:
            conf = 0.45 + (1 - price / ema_9) * 2
            if rsi > 30:
                return {'action': 'sell', 'confidence': min(conf, 0.75), 'price': price}

        if ema_9 > ema_21:
            return {'action': 'buy', 'confidence': 0.15, 'price': price}
        if ema_9 < ema_21:
            return {'action': 'sell', 'confidence': 0.15, 'price': price}

        return {'action': 'hold', 'confidence': 0.0, 'price': price}
