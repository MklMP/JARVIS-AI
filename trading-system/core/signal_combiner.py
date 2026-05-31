import numpy as np
from typing import Dict, List, Tuple
from dataclasses import dataclass


@dataclass
class Signal:
    symbol: str
    action: str  # 'buy', 'sell', 'hold'
    confidence: float
    strategy_name: str
    price: float
    metadata: dict = None


@dataclass
class CombinedSignal:
    symbol: str
    action: str
    confidence: float
    signals: List[Signal]
    weighted_score: float
    agreement_ratio: float


class SignalCombiner:
    def __init__(self, min_confidence: float = 0.6):
        self.min_confidence = min_confidence

    def combine(self, signals: List[Signal], strategy_weights: Dict[str, float] = None) -> CombinedSignal:
        if not signals:
            return CombinedSignal(
                symbol="", action="hold", confidence=0.0,
                signals=[], weighted_score=0.0, agreement_ratio=0.0
            )

        symbol = signals[0].symbol
        if strategy_weights is None:
            strategy_weights = {}
        weights = strategy_weights

        buy_signals = [s for s in signals if s.action == 'buy']
        sell_signals = [s for s in signals if s.action == 'sell']
        hold_signals = [s for s in signals if s.action == 'hold']

        buy_weighted = sum(
            s.confidence * weights.get(s.strategy_name, 1.0)
            for s in buy_signals
        )
        sell_weighted = sum(
            s.confidence * weights.get(s.strategy_name, 1.0)
            for s in sell_signals
        )
        total_weight = sum(
            weights.get(s.strategy_name, 1.0)
            for s in signals
        )

        if total_weight == 0:
            return CombinedSignal(
                symbol=symbol, action="hold", confidence=0.0,
                signals=signals, weighted_score=0.0, agreement_ratio=0.0
            )

        net_score = (buy_weighted - sell_weighted) / total_weight
        agreement = max(len(buy_signals), len(sell_signals)) / max(len(signals), 1)

        if net_score > 0.15 and agreement >= 0.3:
            action = 'buy'
            confidence = min(abs(net_score) * 1.5, 1.0) * agreement
        elif net_score < -0.15 and agreement >= 0.3:
            action = 'sell'
            confidence = min(abs(net_score) * 1.5, 1.0) * agreement
        else:
            action = 'hold'
            confidence = 0.0

        return CombinedSignal(
            symbol=symbol,
            action=action,
            confidence=round(confidence, 4),
            signals=signals,
            weighted_score=round(net_score, 4),
            agreement_ratio=round(agreement, 4)
        )

    def filter_by_confidence(self, combined: CombinedSignal) -> CombinedSignal:
        if combined.confidence < self.min_confidence:
            combined.action = 'hold'
            combined.confidence = 0.0
        return combined
