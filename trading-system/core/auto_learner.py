import numpy as np
from typing import Dict, List
from collections import defaultdict
from datetime import datetime, timedelta
from utils.logger import setup_logger


class AutoLearner:
    def __init__(self, config: dict):
        self.config = config
        self.logger = setup_logger("auto_learner")
        self.micro_performance: Dict[str, List[dict]] = defaultdict(list)
        self.composite_performance: Dict[str, List[dict]] = defaultdict(list)
        self.dynamic_weights: Dict[str, float] = {}
        self.adaptation_rate = 0.05
        self.min_samples = 10
        self.last_adaptation = datetime.now()

    def record_outcome(self, micro_name: str, composite_name: str, action: str,
                       confidence: float, actual_return: float, was_correct: bool):
        self.micro_performance[micro_name].append({
            'action': action,
            'confidence': confidence,
            'return': actual_return,
            'correct': was_correct,
            'timestamp': datetime.now()
        })
        self.composite_performance[composite_name].append({
            'action': action,
            'confidence': confidence,
            'return': actual_return,
            'correct': was_correct,
            'timestamp': datetime.now()
        })

    def get_accuracy(self, name: str, min_samples: int = 5) -> float:
        records = self.micro_performance.get(name, [])
        if len(records) < min_samples:
            return 0.5
        recent = records[-min_samples:]
        correct = sum(1 for r in recent if r['correct'])
        return correct / len(recent) if recent else 0.5

    def adapt_weights(self, current_weights: Dict[str, float]) -> Dict[str, float]:
        now = datetime.now()
        if (now - self.last_adaptation).total_seconds() < 3600:
            return current_weights

        adapted = dict(current_weights)
        for name, records in self.micro_performance.items():
            if len(records) < self.min_samples:
                continue
            recent = records[-self.min_samples:]
            accuracy = sum(1 for r in recent if r['correct']) / len(recent)
            avg_confidence = np.mean([r['confidence'] for r in recent]) if recent else 0

            if accuracy > 0.6:
                adapted[name] = min(adapted.get(name, 1.0) + self.adaptation_rate * (accuracy - 0.5) * 2, 1.5)
                self.logger.info(f"  ↑ {name}: accuracy={accuracy:.2f} → weight={adapted[name]:.2f}")
            elif accuracy < 0.4:
                adapted[name] = max(adapted.get(name, 1.0) - self.adaptation_rate * (0.5 - accuracy) * 2, 0.2)
                self.logger.info(f"  ↓ {name}: accuracy={accuracy:.2f} → weight={adapted[name]:.2f}")

        self.dynamic_weights = adapted
        self.last_adaptation = now
        return adapted

    def get_performance_report(self) -> Dict:
        report = {}
        for name in list(self.micro_performance.keys()):
            records = self.micro_performance[name]
            if not records:
                continue
            recent = records[-20:]
            accuracy = sum(1 for r in recent if r['correct']) / len(recent) if recent else 0
            avg_return = np.mean([r['return'] for r in recent if r['return'] != 0]) if recent else 0
            report[name] = {
                'accuracy': round(accuracy, 3),
                'samples': len(recent),
                'avg_return': round(avg_return, 4),
                'weight': self.dynamic_weights.get(name, 1.0)
            }
        return report

    def evaluate_prediction(self, action: str, predicted_return: float,
                           actual_return: float, confidence: float) -> bool:
        if action == 'hold':
            return abs(actual_return) < 0.01
        if action == 'buy':
            return actual_return > 0
        if action == 'sell':
            return actual_return < 0
        return False
