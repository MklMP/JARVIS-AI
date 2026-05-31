import numpy as np
from typing import Dict, List, Tuple
from dataclasses import dataclass
from collections import defaultdict
from strategies.micro_strategies import (
    ALL_MICRO_STRATEGIES, MICRO_GROUPS, MicroSignal, SignalType
)


@dataclass
class CompositeResult:
    name: str
    action: str
    confidence: float
    buy_count: int
    sell_count: int
    total_count: int
    micro_signals: List[dict]
    group_scores: Dict[str, float]


class CompositeStrategy:
    def __init__(self, name: str, micro_names: List[str], group: str, weights: Dict[str, float] = None):
        self.name = name
        self.micro_names = micro_names
        self.group = group
        self.weights = weights or {}
        self.micro_strategies = [m for m in ALL_MICRO_STRATEGIES if m.name in micro_names]

    def analyze(self, df) -> CompositeResult:
        signals = []
        for micro in self.micro_strategies:
            try:
                sig = micro.analyze(df)
                w = self.weights.get(micro.name, micro.weight)
                raw_action = sig.action
                if isinstance(raw_action, str):
                    action_str = raw_action
                elif hasattr(raw_action, 'value'):
                    action_str = raw_action.value
                else:
                    action_str = str(raw_action).lower().replace('signaltype.', '')
                signals.append({
                    'name': micro.name,
                    'action': action_str,
                    'confidence': sig.confidence,
                    'weight': w
                })
            except Exception:
                signals.append({
                    'name': micro.name,
                    'action': 'hold',
                    'confidence': 0.0,
                    'weight': 1.0
                })

        buy_signals = [s for s in signals if s['action'] == 'buy']
        sell_signals = [s for s in signals if s['action'] == 'sell']
        buy_count = len(buy_signals)
        sell_count = len(sell_signals)
        buy_score = sum(s['confidence'] * s['weight'] for s in buy_signals)
        sell_score = sum(s['confidence'] * s['weight'] for s in sell_signals)
        total_weight = sum(s['weight'] for s in signals)
        net = (buy_score - sell_score) / total_weight if total_weight > 0 else 0
        agreement = max(buy_count, sell_count) / max(len(signals), 1)

        if net > 0.02:
            action = 'buy'
            confidence = min(abs(net) * 2.0, 0.9) * min(agreement * 1.5, 1.0)
        elif net < -0.02:
            action = 'sell'
            confidence = min(abs(net) * 2.0, 0.9) * min(agreement * 1.5, 1.0)
        else:
            action = 'hold'
            confidence = 0.0

        group_scores = {}
        for group_name, micro_names in MICRO_GROUPS.items():
            group_sigs = [s for s in signals if s['name'] in micro_names]
            if group_sigs:
                g_buy = sum(s['confidence'] * s['weight'] for s in group_sigs if s['action'] == 'buy')
                g_sell = sum(s['confidence'] * s['weight'] for s in group_sigs if s['action'] == 'sell')
                g_total = sum(s['weight'] for s in group_sigs)
                group_scores[group_name] = (g_buy - g_sell) / g_total if g_total > 0 else 0

        return CompositeResult(
            name=self.name,
            action=action,
            confidence=round(confidence, 4),
            buy_count=buy_count,
            sell_count=sell_count,
            total_count=len(signals),
            micro_signals=signals,
            group_scores=group_scores
        )


COMPOSITE_STRATEGIES = [
    CompositeStrategy("Smart Money (ICT)", [
        "FVG (Fair Value Gap)", "Order Block", "BOS (Break of Structure)",
        "CHoCH (Change of Character)", "Liquidity Sweep", "Power of Three", "PoT (Power of Three)",
        "Displacement", "Imbalance", "Sesión AMD (Asia-Londres-NY)"
    ], "ict", {
        "FVG (Fair Value Gap)": 1.2, "Order Block": 1.1, "BOS (Break of Structure)": 1.0,
        "CHoCH (Change of Character)": 1.0, "Liquidity Sweep": 1.1, "Power of Three": 1.0,
        "PoT (Power of Three)": 1.0, "Displacement": 0.9, "Imbalance": 0.8,
        "Sesión AMD (Asia-Londres-NY)": 0.9
    }),
    CompositeStrategy("Momento + RSI", [
        "RSI Divergence", "RSI Flash", "MACD Acceleration", "MACD Cross", "Momentum Acceleration"
    ], "momentum", {
        "RSI Divergence": 1.2, "RSI Flash": 1.0, "MACD Acceleration": 1.0, "MACD Cross": 0.8, "Momentum Acceleration": 0.8
    }),
    CompositeStrategy("Tendencia + Medias", [
        "Multi-TF Alignment", "EMA Flash", "ADX Trend Strength"
    ], "trend", {
        "Multi-TF Alignment": 1.2, "EMA Flash": 0.8, "ADX Trend Strength": 1.0
    }),
    CompositeStrategy("Volatilidad (BB + ATR)", [
        "Volatility Expansion", "BB Squeeze + Direction"
    ], "volatility"),
    CompositeStrategy("Volumen Inteligente", [
        "Volume Confirmation", "OBV Confirmation", "NY Open Volumen"
    ], "volume"),
    CompositeStrategy("Reversión a la Media (VWAP)", [
        "VWAP Position"
    ], "mean_reversion"),
    CompositeStrategy("Price Action + Velas", [
        "Price Action", "Candle Comparison", "Lectura de Vela Diaria"
    ], "price_action"),
    CompositeStrategy("Soporte / Resistencia", [
        "S/R Dynamic", "HH/HL Pattern", "Price Trend (5 bars)"
    ], "structure"),
    CompositeStrategy("Yoel Sardiñas (OTE + BB)", [
        "Yoel BB Squeeze", "Yoel OTE Entry", "Yoel EMA Trend", "Yoel Volume + PA", "Yoel RSI + BB"
    ], "yoel", {
        "Yoel BB Squeeze": 1.0, "Yoel OTE Entry": 1.3, "Yoel EMA Trend": 0.8,
        "Yoel Volume + PA": 0.9, "Yoel RSI + BB": 1.1
    }),
    CompositeStrategy("Webull (Vega Quant + Técnico)", [
        "Webull Quant Momentum", "Webull Estructura Técnica", "Webull Riesgo/Sentimiento"
    ], "webull", {
        "Webull Quant Momentum": 1.2, "Webull Estructura Técnica": 1.0, "Webull Riesgo/Sentimiento": 0.9
    }),
]


class CompositeOrchestrator:
    def __init__(self):
        self.composites = COMPOSITE_STRATEGIES
        self.history = []

    def analyze(self, df) -> Dict:
        results = [c.analyze(df) for c in self.composites]

        buy_score = sum(r.confidence for r in results if r.action == 'buy')
        sell_score = sum(r.confidence for r in results if r.action == 'sell')
        total = len(results)
        net = (buy_score - sell_score) / total
        buy_count = sum(1 for r in results if r.action == 'buy')
        sell_count = sum(1 for r in results if r.action == 'sell')
        agreement = max(buy_count, sell_count) / max(total, 1)

        if net > 0.02:
            action = 'buy'
            confidence = min(abs(net) * 1.5 + agreement * 0.2, 0.9)
        elif net < -0.02:
            action = 'sell'
            confidence = min(abs(net) * 1.5 + agreement * 0.2, 0.9)
        else:
            action = 'hold'
            confidence = 0.0

        all_micros = []
        for r in results:
            all_micros.extend(r.micro_signals)

        group_scores = {}
        for r in results:
            for g, score in r.group_scores.items():
                group_scores[g] = group_scores.get(g, 0) + score
        group_scores = {k: round(v, 3) for k, v in sorted(group_scores.items(), key=lambda x: abs(x[1]), reverse=True)}

        composite_details = [{
            'name': r.name,
            'action': r.action,
            'confidence': r.confidence,
            'buy': r.buy_count,
            'sell': r.sell_count,
            'total': r.total_count
        } for r in results]

        return {
            'action': action,
            'confidence': round(confidence, 4),
            'net_score': round(net, 4),
            'agreement': round(agreement, 4),
            'buy_count': buy_count,
            'sell_count': sell_count,
            'composite_count': total,
            'micro_count': len(all_micros),
            'composites': composite_details,
            'micro_signals': all_micros,
            'group_scores': group_scores
        }
