import pandas as pd
import numpy as np
from typing import Dict, Optional
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report
from xgboost import XGBClassifier
import joblib
from pathlib import Path
from ml.feature_engineering import FeatureEngineer
from utils.logger import setup_logger


class ModelTrainer:
    def __init__(self, config: dict):
        self.config = config
        self.logger = setup_logger("model_trainer")
        self.feature_engineer = FeatureEngineer(
            config.get('ml', {}).get('features', None)
        )
        self.model_type = config.get('ml', {}).get('model_type', 'xgboost')
        self.model = None
        self.model_path = Path('./models')
        self.model_path.mkdir(exist_ok=True)

    def train(self, df: pd.DataFrame) -> Dict:
        self.logger.info("Starting model training...")
        features = self.feature_engineer.create_features(df)
        labels = self.feature_engineer.create_labels(df)

        common_idx = features.index.intersection(labels.index)
        features = features.loc[common_idx]
        labels = labels.loc[common_idx]

        if len(features) < self.config.get('ml', {}).get('min_training_samples', 500):
            self.logger.error(f"Insufficient training samples: {len(features)}")
            return {'error': 'Insufficient data'}

        X = features.values
        y = labels.values

        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y
        )

        if self.model_type == 'xgboost':
            self.model = XGBClassifier(
                n_estimators=200,
                max_depth=6,
                learning_rate=0.05,
                subsample=0.8,
                colsample_bytree=0.8,
                random_state=42,
                eval_metric='mlogloss'
            )
        else:
            self.model = RandomForestClassifier(
                n_estimators=200,
                max_depth=10,
                min_samples_split=20,
                min_samples_leaf=10,
                random_state=42,
                class_weight='balanced'
            )

        self.model.fit(X_train, y_train)
        train_acc = accuracy_score(y_train, self.model.predict(X_train))
        test_acc = accuracy_score(y_test, self.model.predict(X_test))

        y_pred = self.model.predict(X_test)
        report = classification_report(y_test, y_pred, output_dict=True)

        self.logger.info(f"Training Accuracy: {train_acc:.4f}")
        self.logger.info(f"Test Accuracy: {test_acc:.4f}")
        self.logger.info(f"Model: {self.model_type}")

        return {
            'train_accuracy': round(train_acc, 4),
            'test_accuracy': round(test_acc, 4),
            'model_type': self.model_type,
            'samples': len(features),
            'feature_importance': self._get_feature_importance(features.columns)
        }

    def save_model(self, name: str = 'trading_model'):
        if self.model is not None:
            path = self.model_path / f"{name}.joblib"
            joblib.dump(self.model, path)
            self.logger.info(f"Model saved to {path}")
            return str(path)
        return None

    def load_model(self, name: str = 'trading_model'):
        path = self.model_path / f"{name}.joblib"
        if path.exists():
            self.model = joblib.load(path)
            self.logger.info(f"Model loaded from {path}")
            return True
        return False

    def _get_feature_importance(self, feature_names) -> Dict:
        if hasattr(self.model, 'feature_importances_'):
            importances = self.model.feature_importances_
            return dict(sorted(
                zip(feature_names, importances),
                key=lambda x: x[1],
                reverse=True
            )[:10])
        return {}
