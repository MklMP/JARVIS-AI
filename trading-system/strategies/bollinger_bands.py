import pandas as pd
from typing import Dict
from strategies.base import BaseStrategy


class BollingerBandsStrategy(BaseStrategy):
    def __init__(self, params: dict = None):
        super().__init__('bollinger_bands', params)
        self.period = self.params.get('period', 20)
        self.std_dev = self.params.get('std_dev', 2.0)

    def generate_signal(self, df: pd.DataFrame) -> Dict:
        df = self.prepare_data(df)
        if len(df) < 25:
            return {'action': 'hold', 'confidence': 0.0, 'price': float(df['close'].iloc[-1])}

        close = df['close'].iloc[-1]
        prev_close = df['close'].iloc[-2]
        bb_high = df['bb_high'].iloc[-1]
        bb_low = df['bb_low'].iloc[-1]
        bb_mid = df['bb_mid'].iloc[-1]
        bb_position = df['bb_position'].iloc[-1]
        prev_bb_pos = df['bb_position'].iloc[-2]
        bb_width = df['bb_width'].iloc[-1]
        price = float(close)

        squeeze = bb_width < df['bb_width'].rolling(50).mean().iloc[-1] if len(df) > 50 else False

        if bb_position < 0.05 and bb_position > prev_bb_pos:
            conf = max(0.6, 1.0 - bb_position * 5)
            if squeeze:
                conf = min(conf + 0.2, 0.95)
            return {'action': 'buy', 'confidence': conf, 'price': price}

        if bb_position > 0.95 and bb_position < prev_bb_pos:
            conf = max(0.6, bb_position)
            if squeeze:
                conf = min(conf + 0.2, 0.95)
            return {'action': 'sell', 'confidence': conf, 'price': price}

        if close < bb_mid and prev_close >= bb_mid:
            return {'action': 'buy', 'confidence': 0.35, 'price': price}
        if close > bb_mid and prev_close <= bb_mid:
            return {'action': 'sell', 'confidence': 0.35, 'price': price}

        bb_upper = df['bb_high'].iloc[-1]
        bb_lower = df['bb_low'].iloc[-1]
        if close > bb_upper:
            return {'action': 'sell', 'confidence': 0.4, 'price': price}
        if close < bb_lower:
            return {'action': 'buy', 'confidence': 0.4, 'price': price}

        return {'action': 'hold', 'confidence': 0.0, 'price': price}
