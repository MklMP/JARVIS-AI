import os, json, math
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import numpy as np

DATA_DIR = os.path.join(os.path.dirname(__file__), 'data', 'patterns')
os.makedirs(DATA_DIR, exist_ok=True)


def _load_json(path):
    if os.path.exists(path):
        with open(path, 'r') as f:
            return json.load(f)
    return []


def _save_json(path, data):
    with open(path, 'w') as f:
        json.dump(data, f, indent=2, default=str)


class PatternAnalyzer:
    def __init__(self, symbol: str):
        self.symbol = symbol
        self.patterns_file = os.path.join(DATA_DIR, f'{symbol}_patterns.json')
        self.learnings_file = os.path.join(DATA_DIR, f'{symbol}_learnings.json')
        self.patterns = _load_json(self.patterns_file)
        self.learnings = _load_json(self.learnings_file)

    def analyze(self, candles: list) -> dict:
        if not candles or len(candles) < 20:
            return {"patterns": [], "summary": "Datos insuficientes"}

        prices = [c['c'] for c in candles]
        highs = [c['h'] for c in candles]
        lows = [c['l'] for c in candles]
        opens = [c['o'] for c in candles]
        volumes = [c.get('v', 0) for c in candles]
        timestamps = [c.get('t') for c in candles]
        bb_h = [c.get('bb_h') for c in candles]
        bb_l = [c.get('bb_l') for c in candles]

        detected = []
        n = len(candles)

        # --- Trend patterns ---
        trend_result = self._detect_trend(prices, highs, lows)
        if trend_result:
            detected.append(trend_result)

        # --- Bollinger patterns ---
        bb_result = self._detect_bb_patterns(prices, bb_h, bb_l)
        detected.extend(bb_result)

        # --- Volatility patterns ---
        vol_result = self._detect_volatility(prices, highs, lows)
        if vol_result:
            detected.append(vol_result)

        # --- Candle patterns (last 10) ---
        candle_pats = self._detect_candle_patterns(opens, highs, lows, prices, volumes)
        detected.extend(candle_pats[:5])

        # --- Support/Resistance ---
        sr_result = self._detect_support_resistance(prices, highs, lows)
        if sr_result:
            detected.append(sr_result)

        # --- Seasonal patterns ---
        seasonal = self._detect_seasonal(timestamps, prices)
        if seasonal:
            detected.append(seasonal)

        # Store patterns for learning
        self._store_patterns(detected, prices, timestamps)

        # Generate summary
        summary = self._generate_summary(prices, highs, lows, volumes, candles)

        return {
            "symbol": self.symbol,
            "patterns": detected[:15],
            "summary": summary,
            "total_detected": len(detected),
        }

    def _detect_trend(self, prices, highs, lows) -> Optional[dict]:
        n = len(prices)
        if n < 20:
            return None
        recent = prices[-20:]
        mid = prices[-10:]
        # Check HH/HL (uptrend)
        hh = sum(1 for i in range(5, len(mid)) if mid[i] > mid[i-1])
        hl = sum(1 for i in range(5, len(mid)) if mid[i] < mid[i-1])

        # EMA slope
        ema9 = sum(prices[-9:]) / 9
        ema21 = sum(prices[-21:]) / 21 if n >= 21 else sum(prices) / len(prices)
        ema_slope = (prices[-1] - prices[-5]) / prices[-5] * 100 if n >= 5 else 0

        # Volatility-based trend strength
        avg_range = sum(h - l for h, l in zip(highs[-10:], lows[-10:])) / 10
        current_range = (highs[-1] - lows[-1]) if len(highs) > 0 else 0
        vol_ratio = current_range / avg_range if avg_range > 0 else 1

        if ema_slope > 1 and hh >= 4:
            return {"type": "uptrend", "strength": "fuerte" if ema_slope > 3 else "moderada",
                    "ema_slope": round(ema_slope, 2), "volatility_ratio": round(vol_ratio, 2),
                    "desc": f"Tendencia alcista activa. EMA slope {ema_slope:.1f}%. "
                            f"Impulso {hh}/5 velas alcistas."}
        if ema_slope < -1 and hl >= 4:
            return {"type": "downtrend", "strength": "fuerte" if ema_slope < -3 else "moderada",
                    "ema_slope": round(ema_slope, 2), "volatility_ratio": round(vol_ratio, 2),
                    "desc": f"Tendencia bajista activa. EMA slope {ema_slope:.1f}%."}
        return None

    def _detect_bb_patterns(self, prices, bb_h, bb_l) -> list:
        patterns = []
        n = len(prices)
        if n < 5:
            return patterns
        valid = [i for i in range(n) if bb_h[i] is not None and bb_l[i] is not None]
        if len(valid) < 3:
            return patterns

        last = valid[-1]
        if bb_h[last] and bb_l[last]:
            pos = (prices[last] - bb_l[last]) / (bb_h[last] - bb_l[last]) if bb_h[last] != bb_l[last] else 0.5
        else:
            pos = 0.5
        if pos > 0.95:
            patterns.append({"type": "bb_top", "position": round(pos, 3),
                             "desc": "Precio en extremo superior de BB. Posible resistencia."})
        elif pos < 0.05:
            patterns.append({"type": "bb_bottom", "position": round(pos, 3),
                             "desc": "Precio en extremo inferior de BB. Posible soporte."})
        # Squeeze
        if len(valid) >= 10:
            widths = [(bb_h[i] - bb_l[i]) / prices[i] for i in valid[-10:]]
            avg_w = sum(widths) / len(widths)
            if avg_w < 0.02 and len(widths) >= 5:
                patterns.append({"type": "bb_squeeze", "width": round(avg_w, 4),
                                 "desc": "Bollinger Squeeze detectado. Expectativa de expansion."})
        return patterns

    def _detect_volatility(self, prices, highs, lows) -> Optional[dict]:
        n = len(prices)
        if n < 15:
            return None
        ranges = [(h - l) for h, l in zip(highs[-15:], lows[-15:])]
        ranges_pct = [r / prices[i] * 100 for i, r in enumerate(ranges)]
        avg_vol = sum(ranges_pct) / len(ranges_pct)
        recent = ranges_pct[-3:]
        avg_recent = sum(recent) / 3
        if avg_recent > avg_vol * 1.5:
            return {"type": "volatility_expansion", "ratio": round(avg_recent / avg_vol, 2),
                    "desc": f"Volatilidad expandiendose ({avg_recent:.1f}% vs media {avg_vol:.1f}%). "
                            "Movimiento fuerte en curso."}
        if avg_recent < avg_vol * 0.5:
            return {"type": "volatility_contraction", "ratio": round(avg_recent / avg_vol, 2),
                    "desc": "Volatilidad contrayendose. Posible acumulacion antes de ruptura."}
        return None

    def _detect_candle_patterns(self, opens, highs, lows, closes, volumes) -> list:
        patterns = []
        n = len(closes)
        if n < 3:
            return patterns
        for i in range(max(0, n - 10), n):
            o, h, l, c = opens[i], highs[i], lows[i], closes[i]
            body = abs(c - o)
            wick_up = h - max(c, o)
            wick_dn = min(c, o) - l
            total_range = h - l
            if total_range == 0:
                continue
            # Doji
            if body / total_range < 0.1 and body > 0:
                patterns.append({"type": "doji", "index": i,
                                 "desc": "Doji - indecision del mercado. Posible cambio de tendencia."})
            # Hammer
            if wick_dn > body * 2 and wick_up < body * 0.5 and i > 0 and c > opens[i-1] and o > opens[i-1]:
                patterns.append({"type": "hammer", "index": i,
                                 "desc": "Hammer - posible agotamiento bajista. Reversion alcista."})
            # Shooting Star
            if wick_up > body * 2 and wick_dn < body * 0.5 and i > 0 and c < opens[i-1]:
                patterns.append({"type": "shooting_star", "index": i,
                                 "desc": "Shooting Star - posible agotamiento alcista. Reversion bajista."})
            # Engulfing (need 2 candles)
            if i > 0:
                prev_body = abs(closes[i-1] - opens[i-1])
                if c > o and opens[i-1] > closes[i-1] and c > opens[i-1] and o < closes[i-1]:
                    patterns.append({"type": "bullish_engulfing", "index": i,
                                     "desc": "Engulfing alcista - fuerte presion compradora."})
                if c < o and opens[i-1] < closes[i-1] and c < opens[i-1] and o > closes[i-1]:
                    patterns.append({"type": "bearish_engulfing", "index": i,
                                     "desc": "Engulfing bajista - fuerte presion vendedora."})
        return patterns

    def _detect_support_resistance(self, prices, highs, lows) -> Optional[dict]:
        n = len(prices)
        if n < 30:
            return None
        pivots = []
        window = 5
        for i in range(window, n - window):
            if highs[i] == max(highs[i-window:i+window+1]):
                pivots.append(("high", i, highs[i]))
            if lows[i] == min(lows[i-window:i+window+1]):
                pivots.append(("low", i, lows[i]))
        if len(pivots) < 3:
            return None
        # Cluster resistance levels (within 1%)
        resistance_clusters = {}
        support_clusters = {}
        for ptype, idx, val in pivots:
            key = round(val * 4) / 4  # round to nearest 0.25
            if ptype == "high":
                resistance_clusters[key] = resistance_clusters.get(key, 0) + 1
            else:
                support_clusters[key] = support_clusters.get(key, 0) + 1
        top_res = sorted(resistance_clusters.items(), key=lambda x: x[1], reverse=True)[:3]
        top_sup = sorted(support_clusters.items(), key=lambda x: x[1], reverse=True)[:3]
        levels = []
        sup_levels = [f"${v:.2f}" for v, c in top_sup if c >= 2]
        res_levels = [f"${v:.2f}" for v, c in top_res if c >= 2]
        if sup_levels or res_levels:
            return {"type": "sr_levels",
                    "soportes": sup_levels, "resistencias": res_levels,
                    "desc": "Niveles S/R detectados: "
                            + (f"Sop: {', '.join(sup_levels)} " if sup_levels else "")
                            + (f"Res: {', '.join(res_levels)}" if res_levels else "")}
        return None

    def _detect_seasonal(self, timestamps, prices) -> Optional[dict]:
        if not timestamps or len(timestamps) < 60:
            return None
        months = {}
        for i, ts in enumerate(timestamps):
            if isinstance(ts, (int, float)):
                dt = datetime.fromtimestamp(ts)
                m = dt.month
                if m not in months:
                    months[m] = {"first": prices[i], "count": 0, "sum": 0}
                months[m]["sum"] += prices[i]
                months[m]["count"] += 1
        if len(months) < 3:
            return None
        monthly_perf = {}
        for m, d in months.items():
            if d["count"] > 0:
                monthly_perf[m] = round(d["sum"] / d["count"], 2)
        current_month = datetime.now().month
        avg_month = monthly_perf.get(current_month, 0)
        overall_avg = sum(monthly_perf.values()) / len(monthly_perf) if monthly_perf else 0
        if avg_month and overall_avg and abs(avg_month - overall_avg) / overall_avg > 0.02:
            dir = "alcista" if avg_month > overall_avg else "bajista"
            return {"type": "seasonal", "month": current_month,
                    "avg_price": round(avg_month, 2),
                    "overall_avg": round(overall_avg, 2),
                    "desc": f"Mes {current_month}: tendencia {dir}. "
                            f"Precio medio ${avg_month:.2f} vs media ${overall_avg:.2f}."}
        return None

    def _generate_summary(self, prices, highs, lows, volumes, candles) -> dict:
        n = len(prices)
        if n < 2:
            return {"error": "Datos insuficientes"}
        pct_changes = [(prices[i] - prices[i-1]) / prices[i-1] * 100 for i in range(1, n)]
        avg_change = sum(pct_changes) / len(pct_changes) if pct_changes else 0
        volatility = sum(abs(p) for p in pct_changes) / len(pct_changes) if pct_changes else 0
        total_return = (prices[-1] - prices[0]) / prices[0] * 100
        max_dd = 0
        peak = prices[0]
        for p in prices:
            if p > peak:
                peak = p
            dd = (peak - p) / peak * 100
            if dd > max_dd:
                max_dd = dd
        up_days = sum(1 for i in range(1, n) if prices[i] > prices[i-1])
        down_days = n - 1 - up_days
        avg_vol = sum(volumes[-20:]) / 20 if len(volumes) >= 20 else (sum(volumes) / len(volumes) if volumes else 0)
        recent_vol = sum(volumes[-5:]) / 5 if len(volumes) >= 5 else 0
        vol_ratio = round(recent_vol / avg_vol, 2) if avg_vol > 0 else 1
        avg_range = sum(h - l for h, l in zip(highs, lows)) / n
        sr = self._detect_support_resistance(prices, highs, lows)
        return {
            "periodos": n,
            "retorno_total": round(total_return, 2),
            "volatilidad_diaria_pct": round(volatility, 2),
            "cambio_promedio_pct": round(avg_change, 2),
            "max_drawdown_pct": round(max_dd, 2),
            "dias_subida": up_days,
            "dias_bajada": down_days,
            "ratio_subida": round(up_days / (n - 1) * 100, 1) if n > 1 else 0,
            "rango_promedio": round(avg_range, 2),
            "volumen_ratio": vol_ratio,
            "sr": sr,
            "desc": (f"Analisis de {n} periodos. Retorno: {total_return:+.1f}%. "
                     f"Volatilidad diaria: {volatility:.1f}%. "
                     f"Max Drawdown: {max_dd:.1f}%. "
                     f"Dias alcistas: {up_days}/{n-1} ({up_days/(n-1)*100:.0f}%). "
                     f"Rango promedio: ${avg_range:.2f}.")
        }

    def _store_patterns(self, patterns, prices, timestamps):
        now = datetime.now().isoformat()
        for p in patterns:
            entry = {
                "type": p.get("type"),
                "symbol": self.symbol,
                "detected_at": now,
                "details": p,
                "price": round(prices[-1], 2) if prices else 0,
                "outcome": None,
            }
            self.patterns.append(entry)
        _save_json(self.patterns_file, self.patterns)

    def get_learnings(self) -> dict:
        return {
            "total_patterns": len(self.patterns),
            "patterns_by_type": self._count_by_type(),
            "recurring_patterns": self._find_recurring(),
            "insights": self._generate_insights(),
        }

    def _count_by_type(self) -> dict:
        counts = {}
        for p in self.patterns:
            t = p.get("type", "unknown")
            counts[t] = counts.get(t, 0) + 1
        return dict(sorted(counts.items(), key=lambda x: x[1], reverse=True))

    def _find_recurring(self) -> list:
        type_counts = self._count_by_type()
        recurring = []
        for t, c in type_counts.items():
            if c >= 3:
                recurring.append({"pattern": t, "occurrences": c})
        return recurring

    def _generate_insights(self) -> list:
        insights = []
        by_type = self._count_by_type()
        total = sum(by_type.values())
        if total > 5:
            top = max(by_type, key=by_type.get)
            insights.append(f"Patron mas recurrente: '{top}' ({by_type[top]} veces, "
                            f"{by_type[top]/total*100:.0f}% del total).")
        if "uptrend" in by_type or "downtrend" in by_type:
            trends = by_type.get("uptrend", 0) + by_type.get("downtrend", 0)
            if trends > 3:
                bull = by_type.get("uptrend", 0)
                bear = by_type.get("downtrend", 0)
                if bull > bear:
                    insights.append(f"El activo tiende a tener tendencias alcistas "
                                    f"({bull} vs {bear} bajistas).")
                else:
                    insights.append(f"El activo tiende a tener tendencias bajistas "
                                    f"({bear} vs {bull} alcistas).")
        if "bb_squeeze" in by_type and by_type["bb_squeeze"] > 2:
            insights.append("Squeezes de Bollinger recurrentes. "
                            "Suelen preceder movimientos direccionales fuertes.")
        if "volatility_expansion" in by_type:
            v = by_type["volatility_expansion"]
            insights.append(f"{v} expansions de volatilidad detectadas. "
                            f"La volatilidad tiende a expandirse tras periodos de contraccion.")
        pattern_names = {
            "hammer": "Martillos", "doji": "Dojis", "shooting_star": "Estrellas Fugaces",
            "bullish_engulfing": "Engulfings Alcistas", "bearish_engulfing": "Engulfings Bajistas"
        }
        for t, name in pattern_names.items():
            if t in by_type and by_type[t] >= 2:
                insights.append(f"Patron de vela '{name}' detectado {by_type[t]} veces. "
                                f"Presta atencion a estos niveles.")
        return insights


def analyze_market_longterm(symbol: str, candles: list) -> dict:
    pa = PatternAnalyzer(symbol)
    result = pa.analyze(candles)
    learnings = pa.get_learnings()
    result["learnings"] = learnings
    return result
