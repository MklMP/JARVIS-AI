import pandas as pd
import numpy as np
from typing import Dict
from strategies.base import BaseStrategy


class IchimokuCloudStrategy(BaseStrategy):
    def __init__(self, params: dict = None):
        super().__init__('ichimoku_cloud', params)
        self.conversion = self.params.get('conversion', 9)
        self.base = self.params.get('base', 26)
        self.span_b = self.params.get('span_b', 52)
        self.displacement = self.params.get('displacement', 26)

    def _calculate_ichimoku(self, df: pd.DataFrame) -> pd.DataFrame:
        high = df['high']
        low = df['low']
        close = df['close']

        df['tenkan_sen'] = (high.rolling(self.conversion).max() + low.rolling(self.conversion).min()) / 2
        df['kijun_sen'] = (high.rolling(self.base).max() + low.rolling(self.base).min()) / 2
        df['senkou_span_a'] = ((df['tenkan_sen'] + df['kijun_sen']) / 2).shift(self.displacement)
        df['senkou_span_b'] = ((high.rolling(self.span_b).max() + low.rolling(self.span_b).min()) / 2).shift(self.displacement)
        df['chikou_span'] = close.shift(-self.displacement)

        return df

    def generate_signal(self, df: pd.DataFrame) -> Dict:
        df = self.prepare_data(df)
        if len(df) < self.span_b + self.displacement + 1:
            return {'action': 'hold', 'confidence': 0.0, 'price': float(df['close'].iloc[-1])}

        df = self._calculate_ichimoku(df)
        price = float(df['close'].iloc[-1])
        tenkan = df['tenkan_sen'].iloc[-1]
        kijun = df['kijun_sen'].iloc[-1]
        span_a = df['senkou_span_a'].iloc[-1]
        span_b = df['senkou_span_b'].iloc[-1]
        prev_tenkan = df['tenkan_sen'].iloc[-2]
        prev_kijun = df['kijun_sen'].iloc[-2]
        chikou = df['chikou_span'].iloc[-1]

        cloud_top = max(span_a, span_b)
        cloud_bottom = min(span_a, span_b)

        signals = []
        conf = 0.0

        if prev_tenkan <= prev_kijun and tenkan > kijun:
            signals.append('tk_cross_buy')
            conf += 0.25
        elif prev_tenkan >= prev_kijun and tenkan < kijun:
            signals.append('tk_cross_sell')
            conf += 0.25

        if price > cloud_top:
            signals.append('cloud_bullish')
            conf += 0.2
        elif price < cloud_bottom:
            signals.append('cloud_bearish')
            conf += 0.2

        if chikou > price:
            signals.append('chikou_bullish')
            conf += 0.15
        elif chikou < price:
            signals.append('chikou_bearish')
            conf += 0.15

        if tenkan > kijun:
            signals.append('bullish_aligned')
            conf += 0.1
        else:
            signals.append('bearish_aligned')
            conf += 0.1

        if price > cloud_top and tenkan > kijun and chikou > price:
            return {'action': 'buy', 'confidence': min(conf + 0.3, 0.95), 'price': price}
        elif price < cloud_bottom and tenkan < kijun and chikou < price:
            return {'action': 'sell', 'confidence': min(conf + 0.3, 0.95), 'price': price}

        if 'tk_cross_buy' in signals and price > cloud_top:
            return {'action': 'buy', 'confidence': 0.65, 'price': price}
        if 'tk_cross_sell' in signals and price < cloud_bottom:
            return {'action': 'sell', 'confidence': 0.65, 'price': price}

        return {'action': 'hold', 'confidence': 0.0, 'price': price}
