import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from enum import Enum
from strategies.micro_strategies import MicroSignal, SignalType


@dataclass
class OTEZone:
    direction: str
    entry_min: float
    entry_max: float
    stop_loss: float
    take_profit_1: float
    take_profit_2: float
    take_profit_3: float
    fibonacci_level: float
    confidence: float
    confluence_score: int = 0       # 0-100
    has_trend_filter: bool = False
    has_liquidity_sweep: bool = False
    has_cisd: bool = False
    has_volume_confirm: bool = False
    rr_ratio: float = 0.0
    atr_entry: float = 0.0
    hypothesis_arrow: str = ''      # 'up' or 'down'
    strength_label: str = ''        # Debil, Moderada, Fuerte, Muy Fuerte


@dataclass
class DirectionPrediction:
    direction: str
    confidence: float
    target_1: Optional[float]
    target_2: Optional[float]
    target_3: Optional[float]
    stop_loss: Optional[float]
    ote_zone: Optional[OTEZone]
    reason: str
    confluence_score: int = 0


def detect_swing_points(high: np.ndarray, low: np.ndarray, lookback: int = 10) -> Tuple[Optional[int], Optional[int]]:
    last = len(high) - 1
    swing_high_idx = None
    swing_low_idx = None
    for i in range(last - lookback, last + 1):
        if i < 2 or i >= len(high) - 2:
            continue
        if high[i] > high[i - 1] and high[i] > high[i - 2] and high[i] > high[i + 1] and high[i] > high[i + 2]:
            if swing_high_idx is None or high[i] > high[swing_high_idx]:
                swing_high_idx = i
        if low[i] < low[i - 1] and low[i] < low[i - 2] and low[i] < low[i + 1] and low[i] < low[i + 2]:
            if swing_low_idx is None or low[i] < low[swing_low_idx]:
                swing_low_idx = i
    return swing_high_idx, swing_low_idx


def detect_hhhl_structure(high: np.ndarray, low: np.ndarray, lookback: int = 20) -> str:
    last = len(high) - 1
    if last < lookback:
        return 'neutral'
    highs = high[last - lookback:last + 1]
    lows = low[last - lookback:last + 1]
    half = lookback // 2
    recent_highs = highs[half:]
    recent_lows = lows[half:]
    old_highs = highs[:half]
    old_lows = lows[:half]

    hh = recent_highs[-1] > max(recent_highs[:-1]) and recent_highs[-1] > max(old_highs)
    hl = recent_lows[-1] > min(recent_lows[:-1]) and recent_lows[-1] > min(old_lows)
    lh = recent_highs[-1] < max(recent_highs[:-1]) and recent_highs[-1] < max(old_highs)
    ll = recent_lows[-1] < min(recent_lows[:-1]) and recent_lows[-1] < min(old_lows)

    if hh and hl:
        return 'bullish'
    if lh and ll:
        return 'bearish'
    return 'neutral'


def detect_liquidity_sweep(high: np.ndarray, low: np.ndarray, close: np.ndarray, lookback: int = 15) -> Tuple[bool, Optional[int]]:
    last = len(close) - 1
    if last < lookback + 3:
        return False, None
    recent_highs = high[last - lookback:last]
    recent_lows = low[last - lookback:last]
    old_high = np.max(recent_highs)
    old_low = np.min(recent_lows)

    sweep_high_idx = None
    sweep_low_idx = None

    for i in range(last - 3, last + 1):
        if high[i] > old_high * 1.001:
            sweep_high_idx = i
        if low[i] < old_low * 0.999:
            sweep_low_idx = i

    if sweep_high_idx and close[-1] < high[sweep_high_idx] - (high[sweep_high_idx] - low[sweep_high_idx]) * 0.3:
        return True, sweep_high_idx
    if sweep_low_idx and close[-1] > low[sweep_low_idx] + (high[sweep_low_idx] - low[sweep_low_idx]) * 0.3:
        return True, sweep_low_idx
    return False, None


def detect_cisd(high: np.ndarray, low: np.ndarray, close: np.ndarray, open_p: np.ndarray, zone_dir: str, zone_entry_min: float, zone_entry_max: float) -> Tuple[bool, str]:
    last = len(close) - 1
    if last < 3:
        return False, ''
    body = abs(close[-1] - open_p[-1])
    upper_wick = high[-1] - max(close[-1], open_p[-1])
    lower_wick = min(close[-1], open_p[-1]) - low[-1]
    avg_body = np.mean([abs(close[i] - open_p[i]) for i in range(last - 5, last)]) if last >= 5 else body

    in_zone = zone_entry_min <= close[-1] <= zone_entry_max

    if zone_dir == 'buy':
        # Rechazo en zona de compra: mecha larga abajo + vela verde
        if in_zone and lower_wick > body * 2 and close[-1] > open_p[-1]:
            return True, 'long_wick_buy'
        if in_zone and body > avg_body * 1.5 and close[-1] > open_p[-1] and open_p[-1] < open_p[-2] and close[-1] > close[-2]:
            return True, 'bullish_engulfing'
        if in_zone and close[-1] > open_p[-1] and close[-1] > close[-2] and body > 0:
            if upper_wick < body * 0.3:
                return True, 'strong_close_buy'
        # Exhaustion after sell move
        if in_zone and lower_wick > body * 3:
            return True, 'hammer_buy'

    if zone_dir == 'sell':
        if in_zone and upper_wick > body * 2 and close[-1] < open_p[-1]:
            return True, 'long_wick_sell'
        if in_zone and body > avg_body * 1.5 and close[-1] < open_p[-1] and open_p[-1] > open_p[-2] and close[-1] < close[-2]:
            return True, 'bearish_engulfing'
        if in_zone and close[-1] < open_p[-1] and close[-1] < close[-2] and body > 0:
            if lower_wick < body * 0.3:
                return True, 'strong_close_sell'
        if in_zone and upper_wick > body * 3:
            return True, 'shooting_star_sell'

    return False, ''


def check_volume_profile(df: pd.DataFrame, entry_min: float, entry_max: float) -> Tuple[bool, float]:
    if 'volume' not in df.columns or 'vwap' not in df.columns:
        return False, 0.0
    vwap = df['vwap'].values
    volume = df['volume'].values
    c = df['close'].values
    midpoint = (entry_min + entry_max) / 2
    vwap_proximity = abs(c[-1] - vwap[-1]) / vwap[-1] if vwap[-1] > 0 else 1

    near_vwap = vwap_proximity < 0.02
    near_mid = entry_min <= vwap[-1] <= entry_max if not np.isnan(vwap[-1]) else False

    avg_vol = np.mean(volume[-20:]) if len(volume) >= 20 else np.mean(volume)
    last_vol_ratio = volume[-1] / avg_vol if avg_vol > 0 else 1

    if (near_vwap or near_mid) and last_vol_ratio > 0.8:
        return True, last_vol_ratio
    if last_vol_ratio > 1.3:
        return True, last_vol_ratio
    return False, last_vol_ratio


def compute_atr(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14) -> float:
    if len(high) < period + 1:
        return 0.0
    trs = []
    for i in range(1, len(high)):
        tr = max(high[i] - low[i], abs(high[i] - close[i - 1]), abs(low[i] - close[i - 1]))
        trs.append(tr)
    if not trs:
        return 0.0
    return float(np.mean(trs[-period:]))


def compute_ote_zones(high: np.ndarray, low: np.ndarray, close: np.ndarray, df: pd.DataFrame = None, boost_score: int = 0) -> List[OTEZone]:
    zones = []
    last = len(close) - 1
    if last < 30:
        return zones

    sh_idx, sl_idx = detect_swing_points(high, low)
    if sh_idx is None or sl_idx is None:
        return zones

    # Trend filter
    trend = detect_hhhl_structure(high, low)

    # Liquidity sweep
    has_sweep, sweep_idx = detect_liquidity_sweep(high, low, close)

    # ATR
    atr = compute_atr(high, low, close)

    # Volume profile
    vol_confirm = False
    vol_ratio = 1.0
    if df is not None:
        vol_confirm, vol_ratio = check_volume_profile(df, 0, 0)

    open_p = df['open'].values if df is not None and 'open' in df.columns else close

    def build_zone(direction, entry_min, entry_max, swing_high, swing_low, range_val, fib_level, is_buy):
        nonlocal vol_confirm, vol_ratio
        current = close[last]

        has_cisd, cisd_type = detect_cisd(high, low, close, open_p, direction, entry_min, entry_max)

        if df is not None:
            vol_confirm, vol_ratio = check_volume_profile(df, entry_min, entry_max)

        trend_ok = (trend == 'bullish' and direction == 'buy') or (trend == 'bearish' and direction == 'sell') or (trend == 'neutral')

        price_in_zone = entry_min <= current <= entry_max

        # Confluence score (0-100) - WITHOUT distance penalty so zones always show
        score = 20  # Base: Fibonacci OTE zone

        if trend_ok and trend != 'neutral':
            score += 15
        if has_sweep:
            score += 15
        if has_cisd:
            score += 20
        if vol_confirm:
            score += 10
        if price_in_zone:
            score += 10  # Premium for being at the zone right now
        if df is not None and 'rsi' in df.columns:
            r = df['rsi'].values[-1]
            if direction == 'buy' and 30 <= r <= 50:
                score += 5
            elif direction == 'sell' and 50 <= r <= 70:
                score += 5
        zone_entry = (entry_min + entry_max) / 2
        dist_pct = abs(current - zone_entry) / range_val if range_val > 0 else 0
        if dist_pct < 0.15 and price_in_zone:
            score += 5

        # Risk-based TP/SL using ATR for guaranteed R:R 1:2 / 1:3
        if is_buy:
            sl = swing_low - atr * 0.5 if atr > 0 else swing_low - range_val * 0.02
            risk = zone_entry - sl
            tp1 = zone_entry + risk * 2.0
            tp2 = zone_entry + risk * 3.0
            tp3 = zone_entry + risk * 4.0
        else:
            sl = swing_high + atr * 0.5 if atr > 0 else swing_high + range_val * 0.02
            risk = sl - zone_entry
            tp1 = zone_entry - risk * 2.0
            tp2 = zone_entry - risk * 3.0
            tp3 = zone_entry - risk * 4.0

        # Guaranteed R:R 1:2 from risk-based TP above
        rr = 2.0

        # Boost OTE score with prediction confidence (from overall strategy analysis)
        if boost_score > 0:
            score = min(score + boost_score, 100)

        conf = min(score / 100.0, 0.92)

        if score >= 80:
            label = 'Muy Fuerte'
        elif score >= 60:
            label = 'Fuerte'
        elif score >= 40:
            label = 'Moderada'
        else:
            label = 'Debil'

        hypothesis = 'up' if is_buy else 'down'

        return OTEZone(
            direction=direction,
            entry_min=entry_min, entry_max=entry_max,
            stop_loss=round(sl, 2),
            take_profit_1=round(tp1, 2), take_profit_2=round(tp2, 2), take_profit_3=round(tp3, 2),
            fibonacci_level=fib_level,
            confidence=min(conf, 0.92),
            confluence_score=score,
            has_trend_filter=trend_ok,
            has_liquidity_sweep=has_sweep,
            has_cisd=has_cisd,
            has_volume_confirm=vol_confirm,
            rr_ratio=round(rr, 2),
            atr_entry=round(atr, 2),
            hypothesis_arrow=hypothesis,
            strength_label=label,
        )

    # Helper: expand narrow zones to at least 0.5× ATR wide
    def expand_zone(lo, hi, atr_val):
        width = hi - lo
        min_w = max(atr_val * 0.5, 0.01)
        if width < min_w:
            mid = (lo + hi) / 2
            lo = mid - min_w / 2
            hi = mid + min_w / 2
        return lo, hi

    # Build buy zone if we have a swing low before swing high (uptrend pair)
    if sl_idx < sh_idx:
        swing_low = low[sl_idx]
        swing_high = high[sh_idx]
        range_val = swing_high - swing_low
        if range_val > 0:
            fib_50  = swing_high - range_val * 0.500
            fib_786 = swing_high - range_val * 0.786
            entry_min, entry_max = expand_zone(min(fib_50, fib_786), max(fib_50, fib_786), atr)
            zone = build_zone('buy', entry_min, entry_max, swing_high, swing_low, range_val, fib_50, True)
            if zone:
                zones.append(zone)

    # Build sell zone if we have a swing high before swing low (downtrend pair)
    if sh_idx < sl_idx:
        swing_high = high[sh_idx]
        swing_low = low[sl_idx]
        range_val = swing_low - swing_high
        if range_val >= 0:
            range_val = swing_high - swing_low
        if range_val != 0:
            range_val = abs(range_val)
            fib_236 = swing_low + range_val * 0.236
            fib_500 = swing_low + range_val * 0.500
            entry_min, entry_max = expand_zone(min(fib_236, fib_500), max(fib_236, fib_500), atr)
            zone = build_zone('sell', entry_min, entry_max, swing_high, swing_low, range_val, fib_236, False)
            if zone:
                zones.append(zone)

    # Also try to find additional zones from older swing pairs for context
    # Look at second-most-recent swings
    sh2_idx, sl2_idx = detect_swing_points(high, low, lookback=20)
    if sh2_idx is not None and sl2_idx is not None:
        # Prevent duplicates - only add zones from different swing pairs
        if sl2_idx < sh2_idx and (abs(sl2_idx - sl_idx) > 3 or abs(sh2_idx - sh_idx) > 3):
            swing_low2 = low[sl2_idx]
            swing_high2 = high[sh2_idx]
            rv2 = swing_high2 - swing_low2
            if rv2 > 0:
                f50  = swing_high2 - rv2 * 0.500
                f786 = swing_high2 - rv2 * 0.786
                emin, emax = expand_zone(min(f50, f786), max(f50, f786), atr)
                zone2 = build_zone('buy', emin, emax, swing_high2, swing_low2, rv2, f50, True)
                if zone2 and not any(abs(z.entry_min - zone2.entry_min) < 1 for z in zones):
                    zones.append(zone2)
        if sh2_idx < sl2_idx and (abs(sl2_idx - sl_idx) > 3 or abs(sh2_idx - sh_idx) > 3):
            swing_high2 = high[sh2_idx]
            swing_low2 = low[sl2_idx]
            rv2 = swing_low2 - swing_high2
            if rv2 >= 0: rv2 = swing_high2 - swing_low2
            if rv2 != 0:
                rv2 = abs(rv2)
                f236 = swing_low2 + rv2 * 0.236
                f500 = swing_low2 + rv2 * 0.500
                emin2, emax2 = expand_zone(min(f236, f500), max(f236, f500), atr)
                zone2 = build_zone('sell', emin2, emax2, swing_high2, swing_low2, rv2, f236, False)
                if zone2 and not any(abs(z.entry_min - zone2.entry_min) < 1 for z in zones):
                    zones.append(zone2)

    return zones


def predict_direction(df: pd.DataFrame) -> DirectionPrediction:
    if df is None or len(df) < 30:
        return DirectionPrediction('sideways', 0.0, None, None, None, None, None, 'datos insuficientes')

    h, l, c, o = df['high'].values, df['low'].values, df['close'].values, df['open'].values
    has_bb = all(x in df.columns for x in ['bb_high', 'bb_low', 'bb_mid', 'bb_position', 'bb_width'])
    has_ema = all(x in df.columns for x in ['ema_9', 'ema_21', 'ema_50'])
    has_rsi = 'rsi' in df.columns
    has_vol = 'volume_ratio' in df.columns

    signals_up = 0
    signals_down = 0
    total_signals = 0
    reasons = []
    confluence_score = 50  # start neutral

    # 1. Trend structure
    trend = detect_hhhl_structure(h, l)
    if trend == 'bullish':
        signals_up += 3
        reasons.append('Estructura HH/HL alcista')
        confluence_score += 10
    elif trend == 'bearish':
        signals_down += 3
        reasons.append('Estructura LH/LL bajista')
        confluence_score -= 10
    total_signals += 3

    # 2. Bollinger Band
    if has_bb:
        bb_pos = df['bb_position'].values
        bbw = df['bb_width'].values
        last_pos = bb_pos[-1]
        if last_pos < 0.05:
            signals_up += 2; reasons.append('BB extremo inferior'); confluence_score += 5
        elif last_pos < 0.2:
            signals_up += 1; reasons.append('BB cerca inferior'); confluence_score += 3
        if last_pos > 0.95:
            signals_down += 2; reasons.append('BB extremo superior'); confluence_score -= 5
        elif last_pos > 0.8:
            signals_down += 1; reasons.append('BB cerca superior'); confluence_score -= 3
        if len(bbw) > 10:
            avg_bbw = np.mean(bbw[-10:-1])
            if bbw[-1] > avg_bbw * 1.3:
                if c[-1] > c[-2]:
                    signals_up += 1; reasons.append('Expansion BB alcista'); confluence_score += 3
                else:
                    signals_down += 1; reasons.append('Expansion BB bajista'); confluence_score -= 3
        total_signals += 3

    # 3. EMA alignment + EMA200
    if has_ema:
        e9, e21, e50 = df['ema_9'].values, df['ema_21'].values, df['ema_50'].values
        # EMA200 if available
        ema200 = df['ema_200'].values if 'ema_200' in df.columns else None

        if e9[-1] > e21[-1] > e50[-1] and c[-1] > e9[-1]:
            signals_up += 2; reasons.append('EMAs alcistas'); confluence_score += 8
        elif e9[-1] < e21[-1] < e50[-1] and c[-1] < e9[-1]:
            signals_down += 2; reasons.append('EMAs bajistas'); confluence_score -= 8

        e9_slope = (e9[-1] - e9[-3]) / e9[-3] if len(e9) > 3 else 0
        if e9_slope > 0.005:
            signals_up += 1; reasons.append('EMA9 subiendo')
        elif e9_slope < -0.005:
            signals_down += 1; reasons.append('EMA9 bajando')

        if ema200 is not None and not np.isnan(ema200[-1]):
            if c[-1] > ema200[-1]:
                signals_up += 2; reasons.append('Precio sobre EMA200 (largo plazo alcista)'); confluence_score += 5
            else:
                signals_down += 2; reasons.append('Precio bajo EMA200 (largo plazo bajista)'); confluence_score -= 5
            total_signals += 2
        total_signals += 2

    # 4. RSI
    if has_rsi:
        r = df['rsi'].values
        rsi_val = r[-1]
        if rsi_val < 30:
            signals_up += 2; reasons.append('RSI sobrevendido'); confluence_score += 5
        elif rsi_val < 40:
            signals_up += 1; reasons.append('RSI bajo'); confluence_score += 3
        if rsi_val > 70:
            signals_down += 2; reasons.append('RSI sobrecomprado'); confluence_score -= 5
        elif rsi_val > 60:
            signals_down += 1; reasons.append('RSI alto'); confluence_score -= 3
        if len(r) > 3:
            if r[-1] > r[-3]:
                signals_up += 1; reasons.append('RSI subiendo')
            elif r[-1] < r[-3]:
                signals_down += 1; reasons.append('RSI bajando')
        total_signals += 2

    # 5. Volume
    if has_vol:
        vr = df['volume_ratio'].values
        if vr[-1] > 1.5 and c[-1] > c[-2]:
            signals_up += 1; reasons.append('Volumen alcista'); confluence_score += 3
        elif vr[-1] > 1.5 and c[-1] < c[-2]:
            signals_down += 1; reasons.append('Volumen bajista'); confluence_score -= 3
        obv = df['obv'].values if 'obv' in df.columns else None
        if obv is not None and len(obv) > 3:
            if obv[-1] > obv[-3] and c[-1] > c[-3]:
                signals_up += 1; reasons.append('OBV confirma tendencia')
            elif obv[-1] < obv[-3] and c[-1] < c[-3]:
                signals_down += 1; reasons.append('OBV confirma tendencia')
        total_signals += 2

    # 6. Price Action
    if len(c) > 3:
        if c[-1] > c[-2] > c[-3]:
            signals_up += 1; reasons.append('3 velas alcistas'); confluence_score += 3
        elif c[-1] < c[-2] < c[-3]:
            signals_down += 1; reasons.append('3 velas bajistas'); confluence_score -= 3
        if len(o) > 2 and c[-1] > o[-1] and c[-2] < o[-2] and o[-1] < c[-2] and c[-1] > o[-2]:
            signals_up += 1; reasons.append('Envolvente alcista'); confluence_score += 4
        if len(o) > 2 and c[-1] < o[-1] and c[-2] > o[-2] and o[-1] > c[-2] and c[-1] < o[-2]:
            signals_down += 1; reasons.append('Envolvente bajista'); confluence_score -= 4
        total_signals += 2

    # 7. OTE v2
    ote_zones = compute_ote_zones(h, l, c, df)
    for zone in ote_zones:
        if zone.direction == 'buy':
            signals_up += int(2 + zone.confluence_score / 25)
            reasons.append(f"OTE compra ({zone.strength_label}, conf:{zone.confluence_score})")
            confluence_score += min(zone.confluence_score // 10, 10)
        else:
            signals_down += int(2 + zone.confluence_score / 25)
            reasons.append(f"OTE venta ({zone.strength_label}, conf:{zone.confluence_score})")
            confluence_score -= min(zone.confluence_score // 10, 10)
        total_signals += 2

    total_signals = max(total_signals, 1)
    net = (signals_up - signals_down) / total_signals
    confluence_score = max(0, min(100, confluence_score))

    if net > 0.06 and signals_up > signals_down:
        direction = 'up'
        confidence = min(abs(net) * 1.5, 0.9)
        atr = compute_atr(h, l, c)
        tp1 = c[-1] + atr * 1.0 if atr > 0 else c[-1] * (1 + abs(net) * 0.5)
        tp2 = c[-1] + atr * 2.0 if atr > 0 else c[-1] * (1 + abs(net) * 1.0)
        tp3 = c[-1] + atr * 3.0 if atr > 0 else c[-1] * (1 + abs(net) * 1.5)
        sl = c[-1] - atr * 0.8 if atr > 0 else c[-1] * (1 - abs(net) * 0.25)
    elif net < -0.06 and signals_down > signals_up:
        direction = 'down'
        confidence = min(abs(net) * 1.5, 0.9)
        atr = compute_atr(h, l, c)
        tp1 = c[-1] - atr * 1.0 if atr > 0 else c[-1] * (1 - abs(net) * 0.5)
        tp2 = c[-1] - atr * 2.0 if atr > 0 else c[-1] * (1 - abs(net) * 1.0)
        tp3 = c[-1] - atr * 3.0 if atr > 0 else c[-1] * (1 - abs(net) * 1.5)
        sl = c[-1] + atr * 0.8 if atr > 0 else c[-1] * (1 + abs(net) * 0.25)
    else:
        direction = 'sideways'
        confidence = 0.0
        tp1 = tp2 = tp3 = sl = None
        reasons = ['Sin direccion clara']

    # Boost OTE zones aligned with prediction direction using overall confluence
    if direction in ('up', 'down') and confluence_score > 30:
        boost_amt = min(confluence_score // 3, 25)
        for z in ote_zones:
            if (direction == 'up' and z.direction == 'buy') or (direction == 'down' and z.direction == 'sell'):
                z.confluence_score = min(z.confluence_score + boost_amt, 100)
                z.confidence = min(z.confluence_score / 100.0, 0.92)
                if z.confluence_score >= 80:
                    z.strength_label = 'Muy Fuerte'
                elif z.confluence_score >= 60:
                    z.strength_label = 'Fuerte'
                elif z.confluence_score >= 40:
                    z.strength_label = 'Moderada'
                else:
                    z.strength_label = 'Debil'

    ote_zone = ote_zones[0] if ote_zones else None

    return DirectionPrediction(
        direction=direction,
        confidence=round(confidence, 4),
        target_1=round(tp1, 2) if tp1 else None,
        target_2=round(tp2, 2) if tp2 else None,
        target_3=round(tp3, 2) if tp3 else None,
        stop_loss=round(sl, 2) if sl else None,
        ote_zone=ote_zone,
        reason=', '.join(reasons[:5]),
        confluence_score=confluence_score,
    )


class YoelBollingerSqueeze:
    def __init__(self):
        self.name = "Yoel BB Squeeze"
        self.group = "yoel"

    def analyze(self, df: pd.DataFrame) -> MicroSignal:
        if len(df) < 25 or 'bb_width' not in df.columns:
            return MicroSignal(self.name, self.group, SignalType.HOLD, 0.0)
        bbw = df['bb_width'].values
        c = df['close'].values
        bb_pos = df['bb_position'].values
        squeeze = bbw[-1] < np.mean(bbw[-20:-1]) * 0.85 if len(bbw) > 20 else False
        expansion = bbw[-1] > np.mean(bbw[-10:-1]) * 1.3 if len(bbw) > 10 else False
        if squeeze:
            return MicroSignal(self.name, self.group, SignalType.HOLD, 0.3)
        if expansion:
            if c[-1] > c[-2] and bb_pos[-1] > 0.5:
                return MicroSignal(self.name, self.group, SignalType.BUY, 0.55)
            elif c[-1] < c[-2] and bb_pos[-1] < 0.5:
                return MicroSignal(self.name, self.group, SignalType.SELL, 0.55)
        if bb_pos[-1] < 0.02:
            rsi = df['rsi'].iloc[-1] if 'rsi' in df.columns else 50
            return MicroSignal(self.name, self.group, SignalType.BUY, 0.65 if rsi < 40 else 0.35)
        if bb_pos[-1] > 0.98:
            rsi = df['rsi'].iloc[-1] if 'rsi' in df.columns else 50
            return MicroSignal(self.name, self.group, SignalType.SELL, 0.65 if rsi > 60 else 0.35)
        if bb_pos[-1] < 0.15:
            return MicroSignal(self.name, self.group, SignalType.BUY, 0.25)
        if bb_pos[-1] > 0.85:
            return MicroSignal(self.name, self.group, SignalType.SELL, 0.25)
        return MicroSignal(self.name, self.group, SignalType.HOLD, 0.0)


class YoelOTEStrategy:
    def __init__(self):
        self.name = "Yoel OTE Entry"
        self.group = "yoel"

    def analyze(self, df: pd.DataFrame) -> MicroSignal:
        if df is None or len(df) < 30:
            return MicroSignal(self.name, self.group, SignalType.HOLD, 0.0)
        h, l, c_arr = df['high'].values, df['low'].values, df['close'].values
        zones = compute_ote_zones(h, l, c_arr, df)
        if not zones:
            return MicroSignal(self.name, self.group, SignalType.HOLD, 0.0)
        zone = zones[0]
        current = c_arr[-1]
        if zone.direction == 'buy' and zone.entry_min <= current <= zone.entry_max:
            conf = min(zone.confidence + 0.05, 0.95)
            rsi = df['rsi'].iloc[-1] if 'rsi' in df.columns else 50
            if 30 <= rsi <= 50:
                conf = min(conf + 0.05, 0.95)
            return MicroSignal(self.name, self.group, SignalType.BUY, conf)
        if zone.direction == 'sell' and zone.entry_min <= current <= zone.entry_max:
            conf = min(zone.confidence + 0.05, 0.95)
            rsi = df['rsi'].iloc[-1] if 'rsi' in df.columns else 50
            if 50 <= rsi <= 70:
                conf = min(conf + 0.05, 0.95)
            return MicroSignal(self.name, self.group, SignalType.SELL, conf)
        return MicroSignal(self.name, self.group, SignalType.HOLD, 0.0)


class YoelEMATrend:
    def __init__(self):
        self.name = "Yoel EMA Trend"
        self.group = "yoel"

    def analyze(self, df: pd.DataFrame) -> MicroSignal:
        if len(df) < 30 or 'ema_9' not in df.columns:
            return MicroSignal(self.name, self.group, SignalType.HOLD, 0.0)
        e9, e21, e50 = df['ema_9'].values, df['ema_21'].values, df['ema_50'].values
        c = df['close'].values
        bull = e9[-1] > e21[-1] > e50[-1] and c[-1] > e9[-1]
        bear = e9[-1] < e21[-1] < e50[-1] and c[-1] < e9[-1]
        e9_slope = (e9[-1] - e9[-4]) / e9[-4] if len(e9) > 4 else 0
        if bull and e9_slope > 0.003:
            rsi = df['rsi'].iloc[-1] if 'rsi' in df.columns else 50
            return MicroSignal(self.name, self.group, SignalType.BUY, 0.65 if rsi < 65 else 0.35)
        if bear and e9_slope < -0.003:
            rsi = df['rsi'].iloc[-1] if 'rsi' in df.columns else 50
            return MicroSignal(self.name, self.group, SignalType.SELL, 0.65 if rsi > 35 else 0.35)
        if c[-1] > e9[-1] > e21[-1]:
            return MicroSignal(self.name, self.group, SignalType.BUY, 0.25)
        if c[-1] < e9[-1] < e21[-1]:
            return MicroSignal(self.name, self.group, SignalType.SELL, 0.25)
        return MicroSignal(self.name, self.group, SignalType.HOLD, 0.0)


class YoelVolumeConfirmation:
    def __init__(self):
        self.name = "Yoel Volume + PA"
        self.group = "yoel"

    def analyze(self, df: pd.DataFrame) -> MicroSignal:
        if len(df) < 10 or 'volume_ratio' not in df.columns:
            return MicroSignal(self.name, self.group, SignalType.HOLD, 0.0)
        vr = df['volume_ratio'].values
        c, o = df['close'].values, df['open'].values
        h, l = df['high'].values, df['low'].values
        vol_surge = vr[-1] > 1.4
        body = abs(c[-1] - o[-1])
        upper_wick = h[-1] - max(c[-1], o[-1])
        lower_wick = min(c[-1], o[-1]) - l[-1]
        if vol_surge and c[-1] > o[-1] and c[-1] > c[-2]:
            return MicroSignal(self.name, self.group, SignalType.BUY, 0.6 if lower_wick > body * 0.5 else 0.4)
        if vol_surge and c[-1] < o[-1] and c[-1] < c[-2]:
            return MicroSignal(self.name, self.group, SignalType.SELL, 0.6 if upper_wick > body * 0.5 else 0.4)
        if vr[-1] > 1.8 and c[-1] > o[-1] and upper_wick < body * 0.3:
            return MicroSignal(self.name, self.group, SignalType.BUY, 0.5)
        if vr[-1] > 1.8 and c[-1] < o[-1] and lower_wick < body * 0.3:
            return MicroSignal(self.name, self.group, SignalType.SELL, 0.5)
        return MicroSignal(self.name, self.group, SignalType.HOLD, 0.0)


class YoelRSIConfirmation:
    def __init__(self):
        self.name = "Yoel RSI + BB"
        self.group = "yoel"

    def analyze(self, df: pd.DataFrame) -> MicroSignal:
        if len(df) < 20 or 'rsi' not in df.columns or 'bb_position' not in df.columns:
            return MicroSignal(self.name, self.group, SignalType.HOLD, 0.0)
        r = df['rsi'].values
        bb_pos = df['bb_position'].values
        rsi_val = r[-1]
        rsi_dir = r[-1] > r[-3] if len(r) > 3 else True
        if rsi_val < 30 and rsi_dir and bb_pos[-1] < 0.15:
            return MicroSignal(self.name, self.group, SignalType.BUY, 0.7)
        if rsi_val > 70 and not rsi_dir and bb_pos[-1] > 0.85:
            return MicroSignal(self.name, self.group, SignalType.SELL, 0.7)
        if rsi_val < 35 and bb_pos[-1] < 0.25:
            return MicroSignal(self.name, self.group, SignalType.BUY, 0.45)
        if rsi_val > 65 and bb_pos[-1] > 0.75:
            return MicroSignal(self.name, self.group, SignalType.SELL, 0.45)
        if 35 <= rsi_val <= 45 and bb_pos[-1] < 0.35:
            return MicroSignal(self.name, self.group, SignalType.BUY, 0.25)
        if 55 <= rsi_val <= 65 and bb_pos[-1] > 0.65:
            return MicroSignal(self.name, self.group, SignalType.SELL, 0.25)
        return MicroSignal(self.name, self.group, SignalType.HOLD, 0.0)


YOEL_STRATEGIES = [
    YoelBollingerSqueeze(),
    YoelOTEStrategy(),
    YoelEMATrend(),
    YoelVolumeConfirmation(),
    YoelRSIConfirmation(),
]
