import pandas as pd
import numpy as np
from typing import List


class FeatureEngineer:
    def __init__(self, feature_list: List[str] = None):
        self.feature_list = feature_list or [
            'rsi', 'macd', 'macd_signal', 'macd_diff',
            'bb_position', 'bb_width', 'adx',
            'volume_ratio', 'price_position',
            'volatility', 'momentum_1', 'momentum_5',
            'stoch_k', 'stoch_d', 'williams_r',
        ]

    def create_features(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()

        features = pd.DataFrame(index=df.index)
        features['rsi'] = df['rsi']
        features['macd'] = df['macd']
        features['macd_signal'] = df['macd_signal']
        features['macd_diff'] = df['macd_diff']
        features['bb_position'] = df['bb_position']
        features['bb_width'] = df['bb_width']
        features['adx'] = df['adx']
        features['volume_ratio'] = df['volume_ratio']
        features['price_position'] = df['price_position']
        features['volatility'] = df['volatility']
        features['momentum_1'] = df['momentum_1']
        features['momentum_5'] = df['momentum_5']
        features['stoch_k'] = df['stoch_k']
        features['stoch_d'] = df['stoch_d']
        features['williams_r'] = df['williams_r']

        features['rsi_ma3'] = df['rsi'].rolling(3).mean()
        features['vol_ma5'] = df['volume_ratio'].rolling(5).mean()

        features['close_sma20_ratio'] = df['close'] / df['sma_21'] - 1
        features['close_sma50_ratio'] = df['close'] / df['sma_50'] - 1

        features['ema_cross'] = (df['ema_9'] / df['ema_21'] - 1)
        features['macd_hist_accel'] = df['macd_diff'].diff()

        return features.dropna()

    def create_labels(self, df: pd.DataFrame, forward_periods: int = 5, threshold_pct: float = 0.02) -> pd.Series:
        future_returns = df['close'].shift(-forward_periods) / df['close'] - 1
        labels = pd.Series(0, index=df.index)
        labels[future_returns > threshold_pct] = 1
        labels[future_returns < -threshold_pct] = -1
        return labels.shift(-forward_periods).dropna().astype(int)
