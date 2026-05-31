import pandas as pd
import numpy as np
from typing import Dict
from strategies.base import BaseStrategy


class ParabolicSARStrategy(BaseStrategy):
    def __init__(self, params: dict = None):
        super().__init__('parabolic_sar', params)
        self.step = self.params.get('step', 0.02)
        self.max_step = self.params.get('max_step', 0.2)

    def _calculate_psar(self, df: pd.DataFrame) -> pd.Series:
        high = df['high'].values
        low = df['low'].values
        close = df['close'].values
        length = len(close)
        psar = np.zeros(length)
        af = self.step
        trend = 1
        ep = high[0]
        psar[0] = low[0]
        sar = low[0]

        for i in range(1, length):
            prev_sar = sar
            if trend == 1:
                sar = prev_sar + af * (ep - prev_sar)
                sar = min(sar, low[i - 1], low[i - 2] if i >= 2 else low[i - 1])
                if low[i] < sar:
                    trend = -1
                    sar = ep
                    ep = low[i]
                    af = self.step
                else:
                    if high[i] > ep:
                        ep = high[i]
                        af = min(af + self.step, self.max_step)
            else:
                sar = prev_sar + af * (ep - prev_sar)
                sar = max(sar, high[i - 1], high[i - 2] if i >= 2 else high[i - 1])
                if high[i] > sar:
                    trend = 1
                    sar = ep
                    ep = high[i]
                    af = self.step
                else:
                    if low[i] < ep:
                        ep = low[i]
                        af = min(af + self.step, self.max_step)
            psar[i] = sar

        return pd.Series(psar, index=df.index)

    def generate_signal(self, df: pd.DataFrame) -> Dict:
        df = self.prepare_data(df)
        if len(df) < 30:
            return {'action': 'hold', 'confidence': 0.0, 'price': float(df['close'].iloc[-1])}

        psar = self._calculate_psar(df)
        close = df['close']
        price = float(close.iloc[-1])
        current_psar = psar.iloc[-1]
        prev_psar = psar.iloc[-2]

        if prev_psar >= close.iloc[-2] and current_psar < price:
            adx = df['adx'].iloc[-1]
            conf = 0.6
            if adx > 25:
                conf = min(conf + 0.2, 0.9)
            return {'action': 'buy', 'confidence': conf, 'price': price}

        if prev_psar <= close.iloc[-2] and current_psar > price:
            adx = df['adx'].iloc[-1]
            conf = 0.6
            if adx > 25:
                conf = min(conf + 0.2, 0.9)
            return {'action': 'sell', 'confidence': conf, 'price': price}

        if current_psar < price:
            return {'action': 'buy', 'confidence': 0.25, 'price': price}
        else:
            return {'action': 'sell', 'confidence': 0.25, 'price': price}
