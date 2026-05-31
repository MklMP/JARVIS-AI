import numpy as np
import pandas as pd
from typing import Dict, Optional
from ml.feature_engineering import FeatureEngineer
from utils.logger import setup_logger


class MLSignalFilter:
    def __init__(self, config: dict):
        self.config = config
        self.logger = setup_logger("ml_filter")
        self.feature_engineer = FeatureEngineer(
            config.get('ml', {}).get('features', None)
        )
        self.model = None
        self.is_trained = False
        self.confidence_threshold = config.get('ml', {}).get('confidence_threshold', 0.55)

    def set_model(self, model):
        self.model = model
        self.is_trained = True
        self.logger.info("ML model loaded")

    def predict(self, df: pd.DataFrame) -> Dict:
        if not self.is_trained or self.model is None:
            return {'ml_signal': 'neutral', 'ml_confidence': 0.0, 'ml_active': False}

        try:
            features = self.feature_engineer.create_features(df)
            if features.empty:
                return {'ml_signal': 'neutral', 'ml_confidence': 0.0, 'ml_active': True}

            latest = features.iloc[-1:]

            if hasattr(self.model, 'predict_proba'):
                probs = self.model.predict_proba(latest.fillna(0))
                classes = self.model.classes_

                sell_idx = np.where(classes == -1)[0]
                neutral_idx = np.where(classes == 0)[0]
                buy_idx = np.where(classes == 1)[0]

                sell_prob = float(probs[0, sell_idx[0]]) if len(sell_idx) > 0 else 0
                buy_prob = float(probs[0, buy_idx[0]]) if len(buy_idx) > 0 else 0

                if buy_prob > self.confidence_threshold and buy_prob > sell_prob:
                    return {'ml_signal': 'buy', 'ml_confidence': round(buy_prob, 3), 'ml_active': True}
                elif sell_prob > self.confidence_threshold and sell_prob > buy_prob:
                    return {'ml_signal': 'sell', 'ml_confidence': round(sell_prob, 3), 'ml_active': True}
                else:
                    return {'ml_signal': 'neutral', 'ml_confidence': 0.0, 'ml_active': True}

            prediction = self.model.predict(latest.fillna(0))[0]
            conf = 0.5
            if prediction == 1:
                return {'ml_signal': 'buy', 'ml_confidence': conf, 'ml_active': True}
            elif prediction == -1:
                return {'ml_signal': 'sell', 'ml_confidence': conf, 'ml_active': True}
            return {'ml_signal': 'neutral', 'ml_confidence': 0.0, 'ml_active': True}

        except Exception as e:
            self.logger.error(f"ML prediction error: {e}")
            return {'ml_signal': 'neutral', 'ml_confidence': 0.0, 'ml_active': True}

    def filter_signal(self, strategy_signal: Dict, ml_prediction: Dict) -> Dict:
        if not ml_prediction.get('ml_active', False):
            return strategy_signal

        strategy_action = strategy_signal.get('action', 'hold')
        strategy_conf = strategy_signal.get('confidence', 0.0)
        ml_action = ml_prediction.get('ml_signal', 'neutral')
        ml_conf = ml_prediction.get('ml_confidence', 0.0)

        if strategy_action == 'hold':
            return strategy_signal

        if strategy_action == ml_action:
            strategy_signal['confidence'] = min(strategy_conf + ml_conf * 0.2, 1.0)
            strategy_signal['ml_boosted'] = True
            return strategy_signal

        if ml_action == 'neutral':
            return strategy_signal

        if ml_action != strategy_action and ml_conf > 0.7:
            strategy_signal['action'] = 'hold'
            strategy_signal['confidence'] = 0.0
            strategy_signal['ml_overridden'] = True
            return strategy_signal

        if ml_action != strategy_action and ml_conf > 0.55:
            strategy_signal['confidence'] = max(strategy_conf - ml_conf * 0.3, 0.0)
            strategy_signal['ml_reduced'] = True
            return strategy_signal

        return strategy_signal
