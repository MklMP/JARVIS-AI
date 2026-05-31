import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from enum import Enum


class SignalType(Enum):
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"


@dataclass
class MicroSignal:
    name: str
    group: str
    action: SignalType
    confidence: float
    weight: float = 1.0


class MicroStrategyBase:
    def __init__(self, name: str, group: str, weight: float = 1.0):
        self.name = name
        self.group = group
        self.weight = weight

    def analyze(self, df: pd.DataFrame) -> MicroSignal:
        return MicroSignal(self.name, self.group, SignalType.HOLD, 0.0)


# ============================================================
# ICT / SMART MONEY CONCEPTS
# ============================================================

class FVGDetector(MicroStrategyBase):
    def __init__(self):
        super().__init__("FVG (Fair Value Gap)", "ict")

    def analyze(self, df: pd.DataFrame) -> MicroSignal:
        if len(df) < 5:
            return MicroSignal(self.name, self.group, SignalType.HOLD, 0.0)
        h, l, c = df['high'].values, df['low'].values, df['close'].values
        bullish_fvg = h[-3] < l[-1]
        bearish_fvg = l[-3] > h[-1]
        if bullish_fvg:
            gap_size = (l[-1] - h[-3]) / h[-3]
            conf = min(gap_size * 5, 0.85)
            if c[-1] > h[-3] and c[-1] < l[-1]:
                conf += 0.1
            return MicroSignal(self.name, self.group, SignalType.BUY, min(conf, 0.9))
        if bearish_fvg:
            gap_size = (l[-3] - h[-1]) / h[-1]
            conf = min(gap_size * 5, 0.85)
            if c[-1] < l[-3] and c[-1] > h[-1]:
                conf += 0.1
            return MicroSignal(self.name, self.group, SignalType.SELL, min(conf, 0.9))
        return MicroSignal(self.name, self.group, SignalType.HOLD, 0.0)


class OrderBlockDetector(MicroStrategyBase):
    def __init__(self):
        super().__init__("Order Block", "ict")

    def analyze(self, df: pd.DataFrame) -> MicroSignal:
        if len(df) < 10:
            return MicroSignal(self.name, self.group, SignalType.HOLD, 0.0)
        h, l, c, o = df['high'].values, df['low'].values, df['close'].values, df['open'].values
        bullish_obs, bearish_obs = [], []
        for i in range(3, min(12, len(df))):
            if c[-i] < o[-i] and c[-i+1] > o[-i+1] and c[-i+2] > o[-i+2]:
                bullish_obs.append(i)
            if c[-i] > o[-i] and c[-i+1] < o[-i+1] and c[-i+2] < o[-i+2]:
                bearish_obs.append(i)
        current_price = c[-1]
        for idx in bullish_obs:
            ob_high, ob_low = h[-idx], l[-idx]
            if ob_low <= current_price <= ob_high + (ob_high - ob_low) * 0.1:
                dist = abs(current_price - ob_low) / (ob_high - ob_low) if ob_high != ob_low else 0
                conf = max(0.5, 1.0 - dist)
                return MicroSignal(self.name, self.group, SignalType.BUY, min(conf, 0.85))
        for idx in bearish_obs:
            ob_high, ob_low = h[-idx], l[-idx]
            if ob_low - (ob_high - ob_low) * 0.1 <= current_price <= ob_high:
                dist = abs(current_price - ob_high) / (ob_high - ob_low) if ob_high != ob_low else 0
                conf = max(0.5, 1.0 - dist)
                return MicroSignal(self.name, self.group, SignalType.SELL, min(conf, 0.85))
        return MicroSignal(self.name, self.group, SignalType.HOLD, 0.0)


class BreakOfStructure(MicroStrategyBase):
    def __init__(self):
        super().__init__("BOS (Break of Structure)", "ict")

    def analyze(self, df: pd.DataFrame) -> MicroSignal:
        if len(df) < 20:
            return MicroSignal(self.name, self.group, SignalType.HOLD, 0.0)
        h, l, c = df['high'].values, df['low'].values, df['close'].values
        hh = h[-5:-1].max()
        ll = l[-5:-1].min()
        prev_hh = h[-12:-5].max() if len(df) > 12 else hh
        prev_ll = l[-12:-5].min() if len(df) > 12 else ll
        bos_bull = h[-1] > hh and hh > prev_hh and c[-1] > c[-2]
        bos_bear = l[-1] < ll and ll < prev_ll and c[-1] < c[-2]
        vol_ratio = df['volume_ratio'].iloc[-1] if 'volume_ratio' in df.columns else 1.0
        if bos_bull:
            conf = 0.5 + min((c[-1] - hh) / hh * 10, 0.25)
            if vol_ratio > 1.2:
                conf = min(conf + 0.1, 0.9)
            return MicroSignal(self.name, self.group, SignalType.BUY, conf)
        if bos_bear:
            conf = 0.5 + min((ll - c[-1]) / ll * 10, 0.25)
            if vol_ratio > 1.2:
                conf = min(conf + 0.1, 0.9)
            return MicroSignal(self.name, self.group, SignalType.SELL, conf)
        return MicroSignal(self.name, self.group, SignalType.HOLD, 0.0)


class ChangeOfCharacter(MicroStrategyBase):
    def __init__(self):
        super().__init__("CHoCH (Change of Character)", "ict")

    def analyze(self, df: pd.DataFrame) -> MicroSignal:
        if len(df) < 30:
            return MicroSignal(self.name, self.group, SignalType.HOLD, 0.0)
        h, l, c = df['high'].values, df['low'].values, df['close'].values

        uptrend = sum(1 for i in range(-5, -1) if c[i] > c[i-1]) >= 4
        downtrend = sum(1 for i in range(-5, -1) if c[i] < c[i-1]) >= 4

        if uptrend and c[-1] < min(l[-5:-1]):
            return MicroSignal(self.name, self.group, SignalType.SELL, 0.6)
        if downtrend and c[-1] > max(h[-5:-1]):
            return MicroSignal(self.name, self.group, SignalType.BUY, 0.6)

        recent_highs = h[-10:]
        recent_lows = l[-10:]
        older_highs = h[-20:-10]
        older_lows = l[-20:-10]

        bearish_structure = all(older_highs[i] >= older_highs[i+1] for i in range(len(older_highs)-3))
        bullish_structure = all(older_lows[i] <= older_lows[i+1] for i in range(len(older_lows)-3))

        if bearish_structure:
            if c[-1] > older_highs[-1] and h[-1] > max(recent_highs[:-1]):
                return MicroSignal(self.name, self.group, SignalType.BUY, 0.7)
        if bullish_structure:
            if c[-1] < older_lows[-1] and l[-1] < min(recent_lows[:-1]):
                return MicroSignal(self.name, self.group, SignalType.SELL, 0.7)
        return MicroSignal(self.name, self.group, SignalType.HOLD, 0.0)


class LiquiditySweep(MicroStrategyBase):
    def __init__(self):
        super().__init__("Liquidity Sweep", "ict")

    def analyze(self, df: pd.DataFrame) -> MicroSignal:
        if len(df) < 20:
            return MicroSignal(self.name, self.group, SignalType.HOLD, 0.0)
        h, l, c = df['high'].values, df['low'].values, df['close'].values

        prior_high = max(h[-11:-1])
        prior_low = min(l[-11:-1])

        sweep_high = h[-1] > prior_high and c[-1] < c[-2]
        sweep_low = l[-1] < prior_low and c[-1] > c[-2]

        if sweep_high:
            vol_ratio = df['volume_ratio'].iloc[-1] if 'volume_ratio' in df.columns else 1.0
            conf = 0.5 + min((h[-1] - prior_high) / prior_high * 5, 0.2)
            if vol_ratio > 1.3:
                conf += 0.1
            return MicroSignal(self.name, self.group, SignalType.SELL, min(conf, 0.85))
        if sweep_low:
            vol_ratio = df['volume_ratio'].iloc[-1] if 'volume_ratio' in df.columns else 1.0
            conf = 0.5 + min((prior_low - l[-1]) / prior_low * 5, 0.2)
            if vol_ratio > 1.3:
                conf += 0.1
            return MicroSignal(self.name, self.group, SignalType.BUY, min(conf, 0.85))
        return MicroSignal(self.name, self.group, SignalType.HOLD, 0.0)


class PowerOfThree(MicroStrategyBase):
    def __init__(self):
        super().__init__("Power of Three", "ict")

    def analyze(self, df: pd.DataFrame) -> MicroSignal:
        if len(df) < 15:
            return MicroSignal(self.name, self.group, SignalType.HOLD, 0.0)
        h, l, c, o = df['high'].values, df['low'].values, df['close'].values, df['open'].values

        range_5 = h[-6:-1].max() - l[-6:-1].min()
        range_10 = h[-11:-6].max() - l[-11:-6].min()

        accumulation = range_5 < range_10 * 0.7

        if accumulation:
            if l[-1] < l[-6:-1].min() and c[-1] > l[-6:-1].min():
                return MicroSignal(self.name, self.group, SignalType.BUY, 0.7)
            if h[-1] > h[-6:-1].max() and c[-1] < h[-6:-1].max():
                return MicroSignal(self.name, self.group, SignalType.SELL, 0.7)
        return MicroSignal(self.name, self.group, SignalType.HOLD, 0.0)


class DisplacementDetector(MicroStrategyBase):
    def __init__(self):
        super().__init__("Displacement", "ict")

    def analyze(self, df: pd.DataFrame) -> MicroSignal:
        if len(df) < 10:
            return MicroSignal(self.name, self.group, SignalType.HOLD, 0.0)
        h, l, c, o = df['high'].values, df['low'].values, df['close'].values, df['open'].values
        vol = df['volume'].values
        avg_range = np.mean(h[-10:-1] - l[-10:-1])
        avg_vol = np.mean(vol[-10:-1]) if len(vol) > 10 else np.mean(vol)
        current_range = h[-1] - l[-1]
        current_vol = vol[-1]

        is_bullish = c[-1] > o[-1] and current_range > avg_range * 1.5 and current_vol > avg_vol * 1.5
        is_bearish = c[-1] < o[-1] and current_range > avg_range * 1.5 and current_vol > avg_vol * 1.5

        if is_bullish:
            rsi = df['rsi'].iloc[-1] if 'rsi' in df.columns else 50
            if rsi < 75:
                return MicroSignal(self.name, self.group, SignalType.BUY, min(0.5 + (current_range/avg_range - 1) * 0.3, 0.85))
        if is_bearish:
            rsi = df['rsi'].iloc[-1] if 'rsi' in df.columns else 50
            if rsi > 25:
                return MicroSignal(self.name, self.group, SignalType.SELL, min(0.5 + (current_range/avg_range - 1) * 0.3, 0.85))
        return MicroSignal(self.name, self.group, SignalType.HOLD, 0.0)


class ImbalanceDetector(MicroStrategyBase):
    def __init__(self):
        super().__init__("Imbalance", "ict")

    def analyze(self, df: pd.DataFrame) -> MicroSignal:
        if len(df) < 10 or 'volume' not in df.columns:
            return MicroSignal(self.name, self.group, SignalType.HOLD, 0.0)
        c, o, vol = df['close'].values, df['open'].values, df['volume'].values
        bullish_vol = sum(vol[i] for i in range(-5, 0) if c[i] > o[i])
        bearish_vol = sum(vol[i] for i in range(-5, 0) if c[i] < o[i])
        total = bullish_vol + bearish_vol
        if total == 0:
            return MicroSignal(self.name, self.group, SignalType.HOLD, 0.0)
        ratio = bullish_vol / total
        if ratio > 0.65 and c[-1] > o[-1]:
            return MicroSignal(self.name, self.group, SignalType.BUY, min((ratio - 0.5) * 2, 0.8))
        if ratio < 0.35 and c[-1] < o[-1]:
            return MicroSignal(self.name, self.group, SignalType.SELL, min((0.5 - ratio) * 2, 0.8))
        return MicroSignal(self.name, self.group, SignalType.HOLD, 0.0)


# ============================================================
# MOMENTUM
# ============================================================

class RSIDivergenceMicro(MicroStrategyBase):
    def __init__(self):
        super().__init__("RSI Divergence", "momentum")

    def analyze(self, df: pd.DataFrame) -> MicroSignal:
        if len(df) < 20 or 'rsi' not in df.columns:
            return MicroSignal(self.name, self.group, SignalType.HOLD, 0.0)
        c, r = df['close'].values, df['rsi'].values
        for lookback in [10, 14, 20]:
            price_low_idx = c[-lookback:].argmin() + len(c) - lookback
            rsi_low_idx = r[-lookback:].argmin() + len(r) - lookback
            price_high_idx = c[-lookback:].argmax() + len(c) - lookback
            rsi_high_idx = r[-lookback:].argmax() + len(r) - lookback
            if price_low_idx < rsi_low_idx and c[price_low_idx] < c[price_low_idx - 1] and r[rsi_low_idx] > r[rsi_low_idx - 1]:
                return MicroSignal(self.name, self.group, SignalType.BUY, 0.7)
            if price_high_idx < rsi_high_idx and c[price_high_idx] > c[price_high_idx - 1] and r[rsi_high_idx] < r[rsi_high_idx - 1]:
                return MicroSignal(self.name, self.group, SignalType.SELL, 0.7)
        return MicroSignal(self.name, self.group, SignalType.HOLD, 0.0)


class RSIFlash(MicroStrategyBase):
    def __init__(self):
        super().__init__("RSI Flash", "momentum")

    def analyze(self, df: pd.DataFrame) -> MicroSignal:
        if len(df) < 5 or 'rsi' not in df.columns:
            return MicroSignal(self.name, self.group, SignalType.HOLD, 0.0)
        r = df['rsi'].values
        c = df['close'].values
        rsi_val = r[-1]

        if rsi_val < 30 and c[-1] > c[-2]:
            return MicroSignal(self.name, self.group, SignalType.BUY, min((30 - rsi_val) / 30 * 0.8, 0.75))
        if rsi_val > 70 and c[-1] < c[-2]:
            return MicroSignal(self.name, self.group, SignalType.SELL, min((rsi_val - 70) / 30 * 0.8, 0.75))

        if rsi_val < 35:
            return MicroSignal(self.name, self.group, SignalType.BUY, 0.25)
        if rsi_val > 65:
            return MicroSignal(self.name, self.group, SignalType.SELL, 0.25)
        return MicroSignal(self.name, self.group, SignalType.HOLD, 0.0)


class MACDAccelerationMicro(MicroStrategyBase):
    def __init__(self):
        super().__init__("MACD Acceleration", "momentum")

    def analyze(self, df: pd.DataFrame) -> MicroSignal:
        if len(df) < 5 or 'macd_diff' not in df.columns:
            return MicroSignal(self.name, self.group, SignalType.HOLD, 0.0)
        hist = df['macd_diff'].values
        if len(hist) < 4:
            return MicroSignal(self.name, self.group, SignalType.HOLD, 0.0)
        h1, h2, h3 = hist[-1], hist[-2], hist[-3]
        accelerating_bull = h1 > h2 > h3 and h1 > 0
        accelerating_bear = h1 < h2 < h3 and h1 < 0
        if accelerating_bull:
            return MicroSignal(self.name, self.group, SignalType.BUY, min(abs(h1) * 10, 0.8))
        if accelerating_bear:
            return MicroSignal(self.name, self.group, SignalType.SELL, min(abs(h1) * 10, 0.8))
        decelerating_bull = h1 < h2 and h2 > h3 and h1 > 0
        decelerating_bear = h1 > h2 and h2 < h3 and h1 < 0
        if decelerating_bull:
            return MicroSignal(self.name, self.group, SignalType.SELL, 0.3)
        if decelerating_bear:
            return MicroSignal(self.name, self.group, SignalType.BUY, 0.3)
        return MicroSignal(self.name, self.group, SignalType.HOLD, 0.0)


class MACDCrossMicro(MicroStrategyBase):
    def __init__(self):
        super().__init__("MACD Cross", "momentum")

    def analyze(self, df: pd.DataFrame) -> MicroSignal:
        if len(df) < 3 or 'macd' not in df.columns or 'macd_signal' not in df.columns:
            return MicroSignal(self.name, self.group, SignalType.HOLD, 0.0)
        m, s = df['macd'].values, df['macd_signal'].values
        c = df['close'].values

        cross_up = m[-1] > s[-1] and m[-2] <= s[-2]
        cross_down = m[-1] < s[-1] and m[-2] >= s[-2]

        if cross_up:
            return MicroSignal(self.name, self.group, SignalType.BUY, 0.55)
        if cross_down:
            return MicroSignal(self.name, self.group, SignalType.SELL, 0.55)

        if m[-1] > s[-1] and m[-1] > 0:
            return MicroSignal(self.name, self.group, SignalType.BUY, 0.3)
        if m[-1] < s[-1] and m[-1] < 0:
            return MicroSignal(self.name, self.group, SignalType.SELL, 0.3)
        return MicroSignal(self.name, self.group, SignalType.HOLD, 0.0)


class MomentumAcceleration(MicroStrategyBase):
    def __init__(self):
        super().__init__("Momentum Acceleration", "momentum")

    def analyze(self, df: pd.DataFrame) -> MicroSignal:
        if len(df) < 10:
            return MicroSignal(self.name, self.group, SignalType.HOLD, 0.0)
        c = df['close'].values
        mom1 = c[-1] / c[-3] - 1
        mom2 = c[-3] / c[-6] - 1
        mom3 = c[-6] / c[-10] - 1 if len(c) >= 10 else mom2
        accelerating_bull = mom1 > mom2 > mom3 and mom1 > 0
        accelerating_bear = mom1 < mom2 < mom3 and mom1 < 0
        if accelerating_bull:
            return MicroSignal(self.name, self.group, SignalType.BUY, min(mom1 * 10 + 0.3, 0.8))
        if accelerating_bear:
            return MicroSignal(self.name, self.group, SignalType.SELL, min(abs(mom1) * 10 + 0.3, 0.8))
        decelerating = abs(mom1) < abs(mom2) and abs(mom2) > abs(mom3)
        if decelerating and mom1 > 0:
            return MicroSignal(self.name, self.group, SignalType.SELL, 0.25)
        if decelerating and mom1 < 0:
            return MicroSignal(self.name, self.group, SignalType.BUY, 0.25)
        return MicroSignal(self.name, self.group, SignalType.HOLD, 0.0)


# ============================================================
# TREND
# ============================================================

class MultipleTFFilter(MicroStrategyBase):
    def __init__(self):
        super().__init__("Multi-TF Alignment", "trend")

    def analyze(self, df: pd.DataFrame) -> MicroSignal:
        if len(df) < 50 or 'ema_9' not in df.columns or 'ema_50' not in df.columns:
            return MicroSignal(self.name, self.group, SignalType.HOLD, 0.0)
        ema9, ema21, ema50 = df['ema_9'].values, df['ema_21'].values, df['ema_50'].values
        c = df['close'].values
        bullish_aligned = ema9[-1] > ema21[-1] > ema50[-1] and c[-1] > ema9[-1]
        bearish_aligned = ema9[-1] < ema21[-1] < ema50[-1] and c[-1] < ema9[-1]
        if bullish_aligned:
            rsi = df['rsi'].iloc[-1] if 'rsi' in df.columns else 50
            if rsi < 70:
                return MicroSignal(self.name, self.group, SignalType.BUY, 0.6)
        if bearish_aligned:
            rsi = df['rsi'].iloc[-1] if 'rsi' in df.columns else 50
            if rsi > 30:
                return MicroSignal(self.name, self.group, SignalType.SELL, 0.6)

        if c[-1] > ema9[-1] > ema21[-1]:
            return MicroSignal(self.name, self.group, SignalType.BUY, 0.3)
        if c[-1] < ema9[-1] < ema21[-1]:
            return MicroSignal(self.name, self.group, SignalType.SELL, 0.3)
        return MicroSignal(self.name, self.group, SignalType.HOLD, 0.0)


class EMAFlash(MicroStrategyBase):
    def __init__(self):
        super().__init__("EMA Flash", "trend")

    def analyze(self, df: pd.DataFrame) -> MicroSignal:
        if len(df) < 3 or 'ema_9' not in df.columns or 'ema_21' not in df.columns:
            return MicroSignal(self.name, self.group, SignalType.HOLD, 0.0)
        e9, e21 = df['ema_9'].values, df['ema_21'].values

        cross_over = e9[-1] > e21[-1] and e9[-2] <= e21[-2]
        cross_under = e9[-1] < e21[-1] and e9[-2] >= e21[-2]

        if cross_over:
            return MicroSignal(self.name, self.group, SignalType.BUY, 0.5)
        if cross_under:
            return MicroSignal(self.name, self.group, SignalType.SELL, 0.5)

        if e9[-1] > e21[-1]:
            return MicroSignal(self.name, self.group, SignalType.BUY, 0.2)
        if e9[-1] < e21[-1]:
            return MicroSignal(self.name, self.group, SignalType.SELL, 0.2)
        return MicroSignal(self.name, self.group, SignalType.HOLD, 0.0)


class ADXTrendMicro(MicroStrategyBase):
    def __init__(self):
        super().__init__("ADX Trend Strength", "trend")

    def analyze(self, df: pd.DataFrame) -> MicroSignal:
        if len(df) < 20 or 'adx' not in df.columns:
            return MicroSignal(self.name, self.group, SignalType.HOLD, 0.0)
        adx = df['adx'].values
        c = df['close'].values
        strong_trend = adx[-1] > 25
        if not strong_trend:
            return MicroSignal(self.name, self.group, SignalType.HOLD, 0.0)
        trend_strength = min((adx[-1] - 25) / 25, 1.0)
        if c[-1] > c[-2] and adx[-1] > adx[-2]:
            return MicroSignal(self.name, self.group, SignalType.BUY, 0.4 + trend_strength * 0.3)
        if c[-1] < c[-2] and adx[-1] > adx[-2]:
            return MicroSignal(self.name, self.group, SignalType.SELL, 0.4 + trend_strength * 0.3)
        return MicroSignal(self.name, self.group, SignalType.HOLD, 0.0)


# ============================================================
# VOLATILITY
# ============================================================

class VolatilityExpansion(MicroStrategyBase):
    def __init__(self):
        super().__init__("Volatility Expansion", "volatility")

    def analyze(self, df: pd.DataFrame) -> MicroSignal:
        if len(df) < 20 or 'volatility' not in df.columns:
            return MicroSignal(self.name, self.group, SignalType.HOLD, 0.0)
        vol = df['volatility'].values
        c = df['close'].values
        avg_vol = np.mean(vol[-15:-1])
        expansion = vol[-1] > avg_vol * 1.3
        if expansion:
            if c[-1] > c[-2]:
                return MicroSignal(self.name, self.group, SignalType.BUY, min(0.4 + (vol[-1]/avg_vol - 1) * 0.3, 0.8))
            return MicroSignal(self.name, self.group, SignalType.SELL, min(0.4 + (vol[-1]/avg_vol - 1) * 0.3, 0.8))
        return MicroSignal(self.name, self.group, SignalType.HOLD, 0.0)


class BollingerSqueezeMicro(MicroStrategyBase):
    def __init__(self):
        super().__init__("BB Squeeze + Direction", "volatility")

    def analyze(self, df: pd.DataFrame) -> MicroSignal:
        if len(df) < 25 or 'bb_width' not in df.columns:
            return MicroSignal(self.name, self.group, SignalType.HOLD, 0.0)
        bbw = df['bb_width'].values
        bb_pos = df['bb_position'].values
        c = df['close'].values
        squeeze = bbw[-1] < np.mean(bbw[-20:-1]) * 0.8
        if squeeze:
            return MicroSignal(self.name, self.group, SignalType.HOLD, 0.4)
        if bb_pos[-1] < 0.1 and c[-1] > c[-2]:
            return MicroSignal(self.name, self.group, SignalType.BUY, 0.6)
        if bb_pos[-1] > 0.9 and c[-1] < c[-2]:
            return MicroSignal(self.name, self.group, SignalType.SELL, 0.6)
        if bb_pos[-1] < 0.05:
            return MicroSignal(self.name, self.group, SignalType.BUY, 0.45)
        if bb_pos[-1] > 0.95:
            return MicroSignal(self.name, self.group, SignalType.SELL, 0.45)
        return MicroSignal(self.name, self.group, SignalType.HOLD, 0.0)


# ============================================================
# VOLUME
# ============================================================

class VolumeConfirmationMicro(MicroStrategyBase):
    def __init__(self):
        super().__init__("Volume Confirmation", "volume")

    def analyze(self, df: pd.DataFrame) -> MicroSignal:
        if len(df) < 10 or 'volume_ratio' not in df.columns:
            return MicroSignal(self.name, self.group, SignalType.HOLD, 0.0)
        vr = df['volume_ratio'].values
        c = df['close'].values
        vol_surge = vr[-1] > 1.3
        if vol_surge and c[-1] > c[-2]:
            obv = df['obv'].values if 'obv' in df.columns else None
            if obv is not None and obv[-1] > obv[-2]:
                return MicroSignal(self.name, self.group, SignalType.BUY, 0.55)
            return MicroSignal(self.name, self.group, SignalType.BUY, 0.4)
        if vol_surge and c[-1] < c[-2]:
            obv = df['obv'].values if 'obv' in df.columns else None
            if obv is not None and obv[-1] < obv[-2]:
                return MicroSignal(self.name, self.group, SignalType.SELL, 0.55)
            return MicroSignal(self.name, self.group, SignalType.SELL, 0.4)
        if vr[-1] > 2.0 and c[-1] > c[-2]:
            return MicroSignal(self.name, self.group, SignalType.SELL, 0.25)
        if vr[-1] > 2.0 and c[-1] < c[-2]:
            return MicroSignal(self.name, self.group, SignalType.BUY, 0.25)
        return MicroSignal(self.name, self.group, SignalType.HOLD, 0.0)


class OBVConfirmMicro(MicroStrategyBase):
    def __init__(self):
        super().__init__("OBV Confirmation", "volume")

    def analyze(self, df: pd.DataFrame) -> MicroSignal:
        if len(df) < 5 or 'obv' not in df.columns:
            return MicroSignal(self.name, self.group, SignalType.HOLD, 0.0)
        obv = df['obv'].values
        c = df['close'].values

        obv_up = obv[-1] > obv[-2] > obv[-3]
        obv_down = obv[-1] < obv[-2] < obv[-3]
        price_up = c[-1] > c[-2]
        price_down = c[-1] < c[-2]

        if obv_up and price_up:
            return MicroSignal(self.name, self.group, SignalType.BUY, 0.45)
        if obv_down and price_down:
            return MicroSignal(self.name, self.group, SignalType.SELL, 0.45)
        if obv_up and price_down:
            return MicroSignal(self.name, self.group, SignalType.BUY, 0.25)
        if obv_down and price_up:
            return MicroSignal(self.name, self.group, SignalType.SELL, 0.25)
        return MicroSignal(self.name, self.group, SignalType.HOLD, 0.0)


# ============================================================
# MEAN REVERSION
# ============================================================

class VWAPPositionMicro(MicroStrategyBase):
    def __init__(self):
        super().__init__("VWAP Position", "mean_reversion")

    def analyze(self, df: pd.DataFrame) -> MicroSignal:
        if len(df) < 20 or 'vwap' not in df.columns:
            return MicroSignal(self.name, self.group, SignalType.HOLD, 0.0)
        c, vwap = df['close'].values, df['vwap'].values
        dist = (c[-1] - vwap[-1]) / vwap[-1]
        bb_pos = df['bb_position'].iloc[-1] if 'bb_position' in df.columns else 0.5
        if dist < -0.01 and bb_pos < 0.3:
            return MicroSignal(self.name, self.group, SignalType.BUY, min(abs(dist) * 5, 0.65))
        if dist > 0.01 and bb_pos > 0.7:
            return MicroSignal(self.name, self.group, SignalType.SELL, min(dist * 5, 0.65))
        if dist < -0.005:
            return MicroSignal(self.name, self.group, SignalType.BUY, 0.2)
        if dist > 0.005:
            return MicroSignal(self.name, self.group, SignalType.SELL, 0.2)
        return MicroSignal(self.name, self.group, SignalType.HOLD, 0.0)


# ============================================================
# PRICE ACTION
# ============================================================

class PriceActionPattern(MicroStrategyBase):
    def __init__(self):
        super().__init__("Price Action", "price_action")

    def analyze(self, df: pd.DataFrame) -> MicroSignal:
        if len(df) < 5:
            return MicroSignal(self.name, self.group, SignalType.HOLD, 0.0)
        o, h, l, c = df['open'].values, df['high'].values, df['low'].values, df['close'].values
        vol = df['volume'].values

        def is_engulfing_bull(i):
            return c[i-1] < o[i-1] and c[i] > o[i] and o[i] < c[i-1] and c[i] > o[i-1]
        def is_engulfing_bear(i):
            return c[i-1] > o[i-1] and c[i] < o[i] and o[i] > c[i-1] and c[i] < o[i-1]
        def is_pin_bar_bull(i):
            body = abs(c[i] - o[i])
            lower_wick = min(o[i], c[i]) - l[i]
            upper_wick = h[i] - max(o[i], c[i])
            return lower_wick > body * 2 and upper_wick < body * 0.5
        def is_pin_bar_bear(i):
            body = abs(c[i] - o[i])
            lower_wick = min(o[i], c[i]) - l[i]
            upper_wick = h[i] - max(o[i], c[i])
            return upper_wick > body * 2 and lower_wick < body * 0.5

        if is_engulfing_bull(-1):
            vol_conf = min(vol[-1] / np.mean(vol[-10:-1]) * 0.15, 0.1) if len(vol) > 5 else 0
            return MicroSignal(self.name, self.group, SignalType.BUY, 0.55 + vol_conf)
        if is_engulfing_bear(-1):
            vol_conf = min(vol[-1] / np.mean(vol[-10:-1]) * 0.15, 0.1) if len(vol) > 5 else 0
            return MicroSignal(self.name, self.group, SignalType.SELL, 0.55 + vol_conf)
        if is_pin_bar_bull(-1):
            return MicroSignal(self.name, self.group, SignalType.BUY, 0.5)
        if is_pin_bar_bear(-1):
            return MicroSignal(self.name, self.group, SignalType.SELL, 0.5)

        body = abs(c[-1] - o[-1])
        if body > 0:
            upper = (h[-1] - max(c[-1], o[-1])) / body
            lower = (min(c[-1], o[-1]) - l[-1]) / body
            if c[-1] > o[-1] and lower > 1.0:
                return MicroSignal(self.name, self.group, SignalType.BUY, 0.35)
            if c[-1] < o[-1] and upper > 1.0:
                return MicroSignal(self.name, self.group, SignalType.SELL, 0.35)
        return MicroSignal(self.name, self.group, SignalType.HOLD, 0.0)


class CandleComparison(MicroStrategyBase):
    def __init__(self):
        super().__init__("Candle Comparison", "price_action")

    def analyze(self, df: pd.DataFrame) -> MicroSignal:
        if len(df) < 5:
            return MicroSignal(self.name, self.group, SignalType.HOLD, 0.0)
        o, c = df['open'].values, df['close'].values

        if c[-1] > o[-1] and c[-2] > o[-2] and c[-3] > o[-3]:
            return MicroSignal(self.name, self.group, SignalType.BUY, 0.3)
        if c[-1] < o[-1] and c[-2] < o[-2] and c[-3] < o[-3]:
            return MicroSignal(self.name, self.group, SignalType.SELL, 0.3)
        return MicroSignal(self.name, self.group, SignalType.HOLD, 0.0)


# ============================================================
# STRUCTURE
# ============================================================

class SupportResistanceMicro(MicroStrategyBase):
    def __init__(self):
        super().__init__("S/R Dynamic", "structure")

    def analyze(self, df: pd.DataFrame) -> MicroSignal:
        if len(df) < 30:
            return MicroSignal(self.name, self.group, SignalType.HOLD, 0.0)
        h, l, c = df['high'].values, df['low'].values, df['close'].values
        pivots_high, pivots_low = [], []
        for i in range(2, min(len(df) - 2, 30)):
            if h[-i] > h[-i-1] and h[-i] > h[-i-2] and h[-i] > h[-i+1] and h[-i] > h[-i+2]:
                pivots_high.append(h[-i])
            if l[-i] < l[-i-1] and l[-i] < l[-i-2] and l[-i] < l[-i+1] and l[-i] < l[-i+2]:
                pivots_low.append(l[-i])
        if not pivots_high or not pivots_low:
            return MicroSignal(self.name, self.group, SignalType.HOLD, 0.0)
        resistance = np.median(pivots_high)
        support = np.median(pivots_low)
        price = c[-1]
        prox_pct = 0.01
        if abs(price - support) / price < prox_pct:
            rsi = df['rsi'].iloc[-1] if 'rsi' in df.columns else 50
            return MicroSignal(self.name, self.group, SignalType.BUY, 0.45 if rsi < 50 else 0.35)
        if abs(price - resistance) / price < prox_pct:
            rsi = df['rsi'].iloc[-1] if 'rsi' in df.columns else 50
            return MicroSignal(self.name, self.group, SignalType.SELL, 0.45 if rsi > 50 else 0.35)
        if price < support * 0.97:
            return MicroSignal(self.name, self.group, SignalType.BUY, 0.25)
        if price > resistance * 1.03:
            return MicroSignal(self.name, self.group, SignalType.SELL, 0.25)
        return MicroSignal(self.name, self.group, SignalType.HOLD, 0.0)


class HHHLDetection(MicroStrategyBase):
    def __init__(self):
        super().__init__("HH/HL Pattern", "structure")

    def analyze(self, df: pd.DataFrame) -> MicroSignal:
        if len(df) < 20:
            return MicroSignal(self.name, self.group, SignalType.HOLD, 0.0)
        h, l, c = df['high'].values, df['low'].values, df['close'].values

        last3_highs = [h[-5], h[-3], h[-1]]
        last3_lows = [l[-5], l[-3], l[-1]]

        if last3_highs[-1] > last3_highs[-2] > last3_highs[-3] and last3_lows[-1] > last3_lows[-2] > last3_lows[-3]:
            return MicroSignal(self.name, self.group, SignalType.BUY, 0.5)
        if last3_highs[-1] < last3_highs[-2] < last3_highs[-3] and last3_lows[-1] < last3_lows[-2] < last3_lows[-3]:
            return MicroSignal(self.name, self.group, SignalType.SELL, 0.5)
        return MicroSignal(self.name, self.group, SignalType.HOLD, 0.0)


class PriceTrendMicro(MicroStrategyBase):
    def __init__(self):
        super().__init__("Price Trend (5 bars)", "structure")

    def analyze(self, df: pd.DataFrame) -> MicroSignal:
        if len(df) < 10:
            return MicroSignal(self.name, self.group, SignalType.HOLD, 0.0)
        c = df['close'].values
        sma10 = np.mean(c[-10:])

        up = sum(1 for i in range(-5, 0) if c[i] > c[i-1])
        down = sum(1 for i in range(-5, 0) if c[i] < c[i-1])

        if up >= 4 and c[-1] > sma10:
            return MicroSignal(self.name, self.group, SignalType.BUY, 0.35)
        if down >= 4 and c[-1] < sma10:
            return MicroSignal(self.name, self.group, SignalType.SELL, 0.35)

        if up >= 3 and c[-1] > sma10:
            return MicroSignal(self.name, self.group, SignalType.BUY, 0.2)
        if down >= 3 and c[-1] < sma10:
            return MicroSignal(self.name, self.group, SignalType.SELL, 0.2)
        return MicroSignal(self.name, self.group, SignalType.HOLD, 0.0)


# ============================================================
# ALL MICRO-STRATEGIES REGISTRY
# ============================================================

# ============================================================
# WEBULL — Vega-inspired strategies
# Based on Webull Vega Analyst's Technical Analysis, Quant Rating,
# and Risk Alert modules used by professional traders.
# ============================================================

class WebullQuantMomentum(MicroStrategyBase):
    """Multi-factor momentum: price trend + RSI momentum + volume confirmation + volatility adj.
    Inspired by Webull's Quant Rating for momentum."""
    def __init__(self):
        super().__init__("Webull Quant Momentum", "webull")

    def analyze(self, df: pd.DataFrame) -> MicroSignal:
        if len(df) < 20:
            return MicroSignal(self.name, self.group, SignalType.HOLD, 0.0)
        c = df['close'].values
        v = df['volume'].values if 'volume' in df.columns else None
        has_rsi = 'rsi' in df.columns
        has_bb = 'bb_position' in df.columns
        has_adx = 'adx' in df.columns

        signals_up = 0; signals_down = 0; total = 0

        # 1. Price momentum: 5-bar return vs 20-bar volatility
        ret_5 = (c[-1] / c[-6] - 1) * 100 if len(c) > 6 else 0
        ret_20 = (c[-1] / c[-21] - 1) * 100 if len(c) > 21 else 0
        vol_20 = np.std(c[-20:] / c[-21:-1] - 1) * 100 if len(c) > 21 else 1
        mom_score = (ret_5 / vol_20) if vol_20 > 0.01 else 0
        if mom_score > 1.0:
            signals_up += 2
        elif mom_score > 0.5:
            signals_up += 1
        elif mom_score < -1.0:
            signals_down += 2
        elif mom_score < -0.5:
            signals_down += 1
        total += 2

        # 2. Trend quality (ADX)
        if has_adx:
            adx = df['adx'].values[-1]
            di_plus = df['plus_di'].values[-1] if 'plus_di' in df.columns else 0
            di_minus = df['minus_di'].values[-1] if 'minus_di' in df.columns else 0
            if adx > 20 and di_plus > di_minus:
                signals_up += 2
            elif adx > 20 and di_minus > di_plus:
                signals_down += 2
            total += 2

        # 3. RSI momentum velocity
        if has_rsi:
            r = df['rsi'].values
            if len(r) > 5:
                rsi_delta = r[-1] - r[-5]
                if rsi_delta > 8 and r[-1] < 70:
                    signals_up += 1
                elif rsi_delta < -8 and r[-1] > 30:
                    signals_down += 1
                total += 1

        # 4. Volume confirmation
        if v is not None and len(v) > 5:
            vol_ratio = v[-1] / np.mean(v[-6:-1]) if np.mean(v[-6:-1]) > 0 else 1
            if vol_ratio > 1.5 and c[-1] > c[-2]:
                signals_up += 1
            elif vol_ratio > 1.5 and c[-1] < c[-2]:
                signals_down += 1
            total += 1

        # 5. BB position for mean reversion context
        if has_bb:
            bp = df['bb_position'].values[-1]
            if bp < 0.05:
                signals_up += 1
            elif bp > 0.95:
                signals_down += 1
            total += 1

        net = (signals_up - signals_down) / max(total, 1)
        conf = min(abs(net) * 1.2, 0.85)
        if net > 0.05:
            return MicroSignal(self.name, self.group, SignalType.BUY, conf)
        elif net < -0.05:
            return MicroSignal(self.name, self.group, SignalType.SELL, conf)
        return MicroSignal(self.name, self.group, SignalType.HOLD, 0.0)


class WebullTechnicalStructure(MicroStrategyBase):
    """Chart structure: S/R breaks, trendline quality, candle confirmation at levels.
    Inspired by Webull Vega's Technical Analysis module."""
    def __init__(self):
        super().__init__("Webull Estructura Técnica", "webull")

    def analyze(self, df: pd.DataFrame) -> MicroSignal:
        if len(df) < 30:
            return MicroSignal(self.name, self.group, SignalType.HOLD, 0.0)
        h, l, c, o = df['high'].values, df['low'].values, df['close'].values, df['open'].values
        signals_up = 0; signals_down = 0; total = 0

        # 1. Break of recent range (20-bar)
        recent_high = np.max(h[-20:-1])
        recent_low = np.min(l[-20:-1])
        if c[-1] > recent_high and l[-1] > np.max(l[-6:-1]):
            signals_up += 2
        elif c[-1] < recent_low and h[-1] < np.min(h[-6:-1]):
            signals_down += 2
        total += 2

        # 2. Pullback to EMA20/50 bounce
        if 'ema20' in df.columns:
            ema20 = df['ema20'].values[-1]
            if c[-1] > ema20 and l[-2] <= ema20 * 1.005 and c[-1] > c[-2]:
                signals_up += 2
            elif c[-1] < ema20 and h[-2] >= ema20 * 0.995 and c[-1] < c[-2]:
                signals_down += 2
            total += 2

        if 'ema50' in df.columns:
            ema50 = df['ema50'].values[-1]
            if c[-1] > ema50 and abs(c[-1] - ema50) / ema50 < 0.005:
                signals_up += 1
            elif c[-1] < ema50 and abs(c[-1] - ema50) / ema50 < 0.005:
                signals_down += 1
            total += 1

        # 3. Candlestick confirmation at extremes
        body = abs(c[-1] - o[-1])
        range_10 = np.max(h[-10:]) - np.min(l[-10:])
        if range_10 > 0:
            body_ratio = body / range_10
            wick_up = h[-1] - max(c[-1], o[-1])
            wick_dn = min(c[-1], o[-1]) - l[-1]
            # Bullish hammer / engulfing at support
            if wick_dn > body * 2 and wick_up < body * 0.5 and c[-1] > o[-1]:
                if c[-1] <= recent_low * 1.02:
                    signals_up += 2
                else:
                    signals_up += 1
            # Bearish shooting star at resistance
            if wick_up > body * 2 and wick_dn < body * 0.5 and c[-1] < o[-1]:
                if c[-1] >= recent_high * 0.98:
                    signals_down += 2
                else:
                    signals_down += 1
            total += 2

        net = (signals_up - signals_down) / max(total, 1)
        conf = min(abs(net) * 1.3, 0.85)
        if net > 0.05:
            return MicroSignal(self.name, self.group, SignalType.BUY, conf)
        elif net < -0.05:
            return MicroSignal(self.name, self.group, SignalType.SELL, conf)
        return MicroSignal(self.name, self.group, SignalType.HOLD, 0.0)


class WebullRiskSentiment(MicroStrategyBase):
    """Risk alert detection: divergences, volume exhaustion, volatility spikes, overextension.
    Inspired by Webull Vega's Risk Alerts module."""
    def __init__(self):
        super().__init__("Webull Riesgo/Sentimiento", "webull")

    def analyze(self, df: pd.DataFrame) -> MicroSignal:
        if len(df) < 30:
            return MicroSignal(self.name, self.group, SignalType.HOLD, 0.0)
        c, h, l = df['close'].values, df['high'].values, df['low'].values
        v = df['volume'].values if 'volume' in df.columns else None
        signals_up = 0; signals_down = 0; total = 0

        # 1. RSI divergence detection (bearish = price up, RSI down)
        if 'rsi' in df.columns and len(c) > 10:
            r = df['rsi'].values
            if c[-1] > c[-6] and r[-1] < r[-6] and r[-1] > 50:
                signals_down += 2
            elif c[-1] < c[-6] and r[-1] > r[-6] and r[-1] < 50:
                signals_up += 2
            total += 2

        # 2. Volume exhaustion
        if v is not None and len(v) > 10:
            avg_vol = np.mean(v[-11:-1])
            vol_ratio = v[-1] / avg_vol if avg_vol > 0 else 1
            if vol_ratio > 2.5:
                if c[-1] > c[-2] and c[-1] > c[-3]:
                    signals_down += 1
                elif c[-1] < c[-2] and c[-1] < c[-3]:
                    signals_up += 1
                total += 1

        # 3. Volatility spike (BB width expansion)
        if 'bb_width' in df.columns and len(df['bb_width']) > 5:
            bw = df['bb_width'].values
            bw_ratio = bw[-1] / np.mean(bw[-6:-1]) if np.mean(bw[-6:-1]) > 0 else 1
            if bw_ratio > 1.5 and c[-1] > c[-2]:
                signals_down += 1
            elif bw_ratio > 1.5 and c[-1] < c[-2]:
                signals_up += 1
            total += 1

        # 4. Overextension (price far from EMA20)
        if 'ema20' in df.columns:
            ema = df['ema20'].values[-1]
            dist_pct = abs(c[-1] - ema) / ema
            if dist_pct > 0.04:
                if c[-1] > ema:
                    signals_down += 1
                else:
                    signals_up += 1
                total += 1

        # 5. OBV divergence
        if 'obv' in df.columns and len(c) > 10:
            obv = df['obv'].values
            if c[-1] > c[-6] and obv[-1] < obv[-6]:
                signals_down += 1
            elif c[-1] < c[-6] and obv[-1] > obv[-6]:
                signals_up += 1
            total += 1

        net = (signals_up - signals_down) / max(total, 1)
        conf = min(abs(net) * 1.3, 0.85)
        if net > 0.05:
            return MicroSignal(self.name, self.group, SignalType.BUY, conf)
        elif net < -0.05:
            return MicroSignal(self.name, self.group, SignalType.SELL, conf)
        return MicroSignal(self.name, self.group, SignalType.HOLD, 0.0)


# ============================================================
# SESSION PATTERNS & POWER OF THREE
# ============================================================

class PowerOfThreeV2(MicroStrategyBase):
    def __init__(self):
        super().__init__("PoT (Power of Three)", "ict")

    def analyze(self, df: pd.DataFrame) -> MicroSignal:
        if len(df) < 20:
            return MicroSignal(self.name, self.group, SignalType.HOLD, 0.0)
        h, l, c, o = df['high'].values, df['low'].values, df['close'].values

        mid = len(df) - 10
        if mid < 5: return MicroSignal(self.name, self.group, SignalType.HOLD, 0.0)

        range_accum = h[-10:-4].max() - l[-10:-4].min()
        range_prior = h[-18:-10].max() - l[-18:-10].min() if len(df) > 18 else range_accum
        accumulation = range_accum < range_prior * 0.75

        if not accumulation:
            range_accum = np.std(c[-10:-4]) / np.mean(c[-10:-4])
            range_prior = np.std(c[-18:-10]) / np.mean(c[-18:-10]) if len(df) > 18 else range_accum
            accumulation = range_accum < range_prior * 0.8

        if accumulation:
            recent_low = min(l[-6:-1])
            recent_high = max(h[-6:-1])
            body = abs(c[-1] - o[-1])
            wick_dn = min(o[-1], c[-1]) - l[-1]
            wick_up = h[-1] - max(o[-1], c[-1])

            manipulation_dn = l[-2] < recent_low and c[-2] > l[-2] and c[-1] > c[-2]
            manipulation_up = h[-2] > recent_high and c[-2] < h[-2] and c[-1] < c[-2]

            if manipulation_dn:
                dist = (c[-1] - recent_low) / recent_low
                vol = df['volume_ratio'].iloc[-1] if 'volume_ratio' in df.columns else 1.0
                conf = 0.55 + min(dist * 8, 0.2)
                if vol > 1.3: conf += 0.1
                return MicroSignal(self.name, self.group, SignalType.BUY, min(conf, 0.85))

            if manipulation_up:
                dist = (recent_high - c[-1]) / recent_high
                vol = df['volume_ratio'].iloc[-1] if 'volume_ratio' in df.columns else 1.0
                conf = 0.55 + min(dist * 8, 0.2)
                if vol > 1.3: conf += 0.1
                return MicroSignal(self.name, self.group, SignalType.SELL, min(conf, 0.85))

            single_candle_manip = wick_dn > body * 2.5 and c[-1] > o[-1] and c[-1] > np.mean(c[-5:-1])
            single_candle_manip_sell = wick_up > body * 2.5 and c[-1] < o[-1] and c[-1] < np.mean(c[-5:-1])
            if single_candle_manip:
                return MicroSignal(self.name, self.group, SignalType.BUY, 0.6)
            if single_candle_manip_sell:
                return MicroSignal(self.name, self.group, SignalType.SELL, 0.6)

        return MicroSignal(self.name, self.group, SignalType.HOLD, 0.0)


class SessionAMDBreakout(MicroStrategyBase):
    def __init__(self):
        super().__init__("Sesión AMD (Asia-Londres-NY)", "ict")

    def analyze(self, df: pd.DataFrame) -> MicroSignal:
        if len(df) < 15:
            return MicroSignal(self.name, self.group, SignalType.HOLD, 0.0)
        h, l, c, o = df['high'].values, df['low'].values, df['close'].values

        asia_range = h[-8:-5].max() - l[-8:-5].min() if len(df) >= 8 else 0
        london_range = h[-5:-2].max() - l[-5:-2].min() if len(df) >= 5 else 0
        ny_range = h[-2:].max() - l[-2:].min()

        if asia_range <= 0: return MicroSignal(self.name, self.group, SignalType.HOLD, 0.0)

        london_breakout = london_range > asia_range * 1.3
        ny_continuation = ny_range > asia_range * 1.5

        if london_breakout and ny_continuation:
            london_bull = c[-3] > o[-3] if len(c) >= 3 else False
            london_bear = c[-3] < o[-3] if len(c) >= 3 else False
            ny_bull = c[-1] > o[-1] and c[-1] > c[-2]
            ny_bear = c[-1] < o[-1] and c[-1] < c[-2]

            vol = df['volume_ratio'].iloc[-1] if 'volume_ratio' in df.columns else 1.0
            if london_bull and ny_bull:
                conf = 0.5 + min(ny_range / asia_range * 0.15, 0.3)
                if vol > 1.3: conf += 0.1
                return MicroSignal(self.name, self.group, SignalType.BUY, min(conf, 0.85))
            if london_bear and ny_bear:
                conf = 0.5 + min(ny_range / asia_range * 0.15, 0.3)
                if vol > 1.3: conf += 0.1
                return MicroSignal(self.name, self.group, SignalType.SELL, min(conf, 0.85))
            if london_bull and ny_bear:
                return MicroSignal(self.name, self.group, SignalType.SELL, 0.45)
            if london_bear and ny_bull:
                return MicroSignal(self.name, self.group, SignalType.BUY, 0.45)

        asia_high = h[-8:-5].max() if len(df) >= 8 else max(h[-5:-1])
        asia_low = l[-8:-5].min() if len(df) >= 8 else min(l[-5:-1])
        if asia_high and asia_low:
            asia_mid = (asia_high + asia_low) / 2
            asia_range = asia_high - asia_low
            london_above = c[-3] > asia_high if len(c) >= 3 else False
            london_below = c[-3] < asia_low if len(c) >= 3 else False
            if london_above and c[-1] > asia_high + asia_range * 0.5:
                vol = df['volume_ratio'].iloc[-1] if 'volume_ratio' in df.columns else 1.0
                conf = 0.45
                if vol > 1.5: conf += 0.1
                return MicroSignal(self.name, self.group, SignalType.BUY, min(conf, 0.75))
            if london_below and c[-1] < asia_low - asia_range * 0.5:
                vol = df['volume_ratio'].iloc[-1] if 'volume_ratio' in df.columns else 1.0
                conf = 0.45
                if vol > 1.5: conf += 0.1
                return MicroSignal(self.name, self.group, SignalType.SELL, min(conf, 0.75))

        return MicroSignal(self.name, self.group, SignalType.HOLD, 0.0)


class NYOpenVolume(MicroStrategyBase):
    def __init__(self):
        super().__init__("NY Open Volumen", "volume")

    def analyze(self, df: pd.DataFrame) -> MicroSignal:
        if len(df) < 10 or 'volume_ratio' not in df.columns:
            return MicroSignal(self.name, self.group, SignalType.HOLD, 0.0)
        c, o, h_vals = df['close'].values, df['open'].values, df['high'].values
        l_vals = df['low'].values
        vr = df['volume_ratio'].values

        vol_spike = vr[-1] > 1.8
        body = abs(c[-1] - o[-1])
        wick_up = h_vals[-1] - max(c[-1], o[-1])
        wick_dn = min(c[-1], o[-1]) - l_vals[-1]

        if vol_spike:
            range_avg = np.mean(df['high'].values[-10:-1] - df['low'].values[-10:-1])
            current_range = df['high'].values[-1] - df['low'].values[-1]
            range_expansion = current_range > range_avg * 1.3 if range_avg > 0 else False

            if range_expansion and c[-1] > o[-1] and wick_dn < body * 0.3:
                conf = 0.45 + min((vr[-1] - 1.5) * 0.15, 0.2)
                if wick_up < body * 0.3: conf += 0.1
                return MicroSignal(self.name, self.group, SignalType.BUY, min(conf, 0.8))
            if range_expansion and c[-1] < o[-1] and wick_up < body * 0.3:
                conf = 0.45 + min((vr[-1] - 1.5) * 0.15, 0.2)
                if wick_dn < body * 0.3: conf += 0.1
                return MicroSignal(self.name, self.group, SignalType.SELL, min(conf, 0.8))

            prev_trend_up = c[-1] > c[-3] and c[-3] > c[-5]
            prev_trend_dn = c[-1] < c[-3] and c[-3] < c[-5]
            if vol_spike and vr[-1] > 2.5:
                if prev_trend_up and c[-1] < o[-1]:
                    return MicroSignal(self.name, self.group, SignalType.SELL, 0.5)
                if prev_trend_dn and c[-1] > o[-1]:
                    return MicroSignal(self.name, self.group, SignalType.BUY, 0.5)

        return MicroSignal(self.name, self.group, SignalType.HOLD, 0.0)


class DailyCandleReading(MicroStrategyBase):
    def __init__(self):
        super().__init__("Lectura de Vela Diaria", "price_action")

    def analyze(self, df: pd.DataFrame) -> MicroSignal:
        if len(df) < 5:
            return MicroSignal(self.name, self.group, SignalType.HOLD, 0.0)
        o, h, l, c = df['open'].values, df['high'].values, df['low'].values, df['close'].values
        v = df['volume'].values if 'volume' in df.columns else None
        vr = df['volume_ratio'].values if 'volume_ratio' in df.columns else None

        body = abs(c[-1] - o[-1])
        if body == 0: return MicroSignal(self.name, self.group, SignalType.HOLD, 0.0)
        wick_up = h[-1] - max(c[-1], o[-1])
        wick_dn = min(c[-1], o[-1]) - l[-1]
        full_range = h[-1] - l[-1]
        body_pct = body / full_range if full_range > 0 else 1

        signals_up = 0; signals_down = 0; total = 0

        marubozu_bull = body_pct > 0.9 and c[-1] > o[-1] and wick_up < body * 0.1 and wick_dn < body * 0.1
        marubozu_bear = body_pct > 0.9 and c[-1] < o[-1] and wick_up < body * 0.1 and wick_dn < body * 0.1
        if marubozu_bull:
            signals_up += 3
        if marubozu_bear:
            signals_down += 3
        total += 3

        doji = body < full_range * 0.15 and full_range > 0
        if doji:
            prev_bull = c[-2] > o[-2] and c[-2] > c[-3]
            prev_bear = c[-2] < o[-2] and c[-2] < c[-3]
            if prev_bull:
                signals_down += 2
            elif prev_bear:
                signals_up += 2
            total += 2

        engulfing_bull = c[-2] < o[-2] and c[-1] > o[-1] and o[-1] < c[-2] and c[-1] > o[-2]
        engulfing_bear = c[-2] > o[-2] and c[-1] < o[-1] and o[-1] > c[-2] and c[-1] < o[-2]
        if engulfing_bull:
            signals_up += 2
            if vr and vr[-1] > 1.3: signals_up += 1
        if engulfing_bear:
            signals_down += 2
            if vr and vr[-1] > 1.3: signals_down += 1
        total += 2

        gap_up = l[-1] > h[-2]
        gap_down = h[-1] < l[-2]
        if gap_up:
            if c[-1] > o[-1]:
                signals_up += 2
                total += 2
            else:
                signals_down += 1
                total += 1
        if gap_down:
            if c[-1] < o[-1]:
                signals_down += 2
                total += 2
            else:
                signals_up += 1
                total += 1

        wick_test_bull = wick_dn > body * 2 and c[-1] > o[-1] and l[-1] < l[-2]
        wick_test_bear = wick_up > body * 2 and c[-1] < o[-1] and h[-1] > h[-2]
        if wick_test_bull:
            signals_up += 2
            total += 2
        if wick_test_bear:
            signals_down += 2
            total += 2

        net = (signals_up - signals_down) / max(total, 1)
        conf = min(abs(net) * 0.7, 0.8)
        if net > 0.1:
            return MicroSignal(self.name, self.group, SignalType.BUY, conf)
        elif net < -0.1:
            return MicroSignal(self.name, self.group, SignalType.SELL, conf)
        return MicroSignal(self.name, self.group, SignalType.HOLD, 0.0)


ALL_MICRO_STRATEGIES = [
    FVGDetector(), OrderBlockDetector(), BreakOfStructure(),
    ChangeOfCharacter(), LiquiditySweep(), PowerOfThree(), PowerOfThreeV2(),
    DisplacementDetector(), ImbalanceDetector(),
    RSIDivergenceMicro(), RSIFlash(), MACDAccelerationMicro(), MACDCrossMicro(), MomentumAcceleration(),
    MultipleTFFilter(), EMAFlash(), ADXTrendMicro(),
    VolatilityExpansion(), BollingerSqueezeMicro(),
    VolumeConfirmationMicro(), OBVConfirmMicro(), NYOpenVolume(),
    VWAPPositionMicro(),
    PriceActionPattern(), CandleComparison(), DailyCandleReading(),
    SupportResistanceMicro(), HHHLDetection(), PriceTrendMicro(),
    # Session patterns
    SessionAMDBreakout(),
    # Webull strategies
    WebullQuantMomentum(), WebullTechnicalStructure(), WebullRiskSentiment(),
]

# Add Yoel Sardiñas strategies (lazy import to avoid circular)
try:
    from strategies.yoel_sardenas import YOEL_STRATEGIES
    ALL_MICRO_STRATEGIES.extend(YOEL_STRATEGIES)
except ImportError:
    pass

MICRO_GROUPS = {
    "ict": ["FVG (Fair Value Gap)", "Order Block", "BOS (Break of Structure)",
            "CHoCH (Change of Character)", "Liquidity Sweep", "Power of Three", "PoT (Power of Three)",
            "Displacement", "Imbalance", "Sesión AMD (Asia-Londres-NY)"],
    "momentum": ["RSI Divergence", "RSI Flash", "MACD Acceleration", "MACD Cross", "Momentum Acceleration"],
    "trend": ["Multi-TF Alignment", "EMA Flash", "ADX Trend Strength"],
    "volatility": ["Volatility Expansion", "BB Squeeze + Direction"],
    "volume": ["Volume Confirmation", "OBV Confirmation", "NY Open Volumen"],
    "mean_reversion": ["VWAP Position"],
    "price_action": ["Price Action", "Candle Comparison", "Lectura de Vela Diaria"],
    "structure": ["S/R Dynamic", "HH/HL Pattern", "Price Trend (5 bars)"],
    "yoel": ["Yoel BB Squeeze", "Yoel OTE Entry", "Yoel EMA Trend", "Yoel Volume + PA", "Yoel RSI + BB"],
    "webull": ["Webull Quant Momentum", "Webull Estructura Técnica", "Webull Riesgo/Sentimiento"],
}
