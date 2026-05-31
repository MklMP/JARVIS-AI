import pandas as pd
from typing import Dict, List, Optional
from strategies import STRATEGY_REGISTRY
from strategies.base import BaseStrategy
from core.signal_combiner import Signal, SignalCombiner
from utils.logger import setup_logger


class StrategyManager:
    def __init__(self, config: dict):
        self.config = config
        self.logger = setup_logger("strategy_manager")
        self.strategies: Dict[str, BaseStrategy] = {}
        self.weights: Dict[str, float] = {}
        self.combiner = SignalCombiner(
            min_confidence=config.get('general', {}).get('min_confidence', 0.6)
        )
        self._load_strategies()

    def _load_strategies(self):
        strat_config = self.config.get('strategies', {})
        for name, strat_cls in STRATEGY_REGISTRY.items():
            sc = strat_config.get(name, {})
            if sc.get('enabled', True):
                params = sc.get('params', {})
                weight = sc.get('weight', 1.0)
                try:
                    strategy = strat_cls(params)
                    self.strategies[name] = strategy
                    self.weights[name] = weight
                    self.logger.info(f"Loaded strategy: {name} (weight: {weight})")
                except Exception as e:
                    self.logger.error(f"Failed to load strategy {name}: {e}")

        self.logger.info(f"Loaded {len(self.strategies)} strategies")

    def analyze(self, symbol: str, df: pd.DataFrame) -> Dict:
        signals = []
        for name, strategy in self.strategies.items():
            try:
                result = strategy.generate_signal(df.copy())
                signal = Signal(
                    symbol=symbol,
                    action=result.get('action', 'hold'),
                    confidence=result.get('confidence', 0.0),
                    strategy_name=name,
                    price=result.get('price', float(df['close'].iloc[-1])),
                    metadata=result.get('metadata', {})
                )
                signals.append(signal)
            except Exception as e:
                self.logger.error(f"Error in strategy {name}: {e}")

        combined = self.combiner.combine(signals, self.weights)
        combined = self.combiner.filter_by_confidence(combined)

        return {
            'symbol': symbol,
            'action': combined.action,
            'confidence': combined.confidence,
            'weighted_score': combined.weighted_score,
            'agreement_ratio': combined.agreement_ratio,
            'signals': [
                {
                    'strategy': s.strategy_name,
                    'action': s.action,
                    'confidence': s.confidence
                }
                for s in combined.signals
            ]
        }

    def get_strategy_count(self) -> int:
        return len(self.strategies)

    def get_active_strategies(self) -> List[str]:
        return list(self.strategies.keys())
