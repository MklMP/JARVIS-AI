import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta
import pytz

# ──────────────────────────────────────────────
#  Utilidades Generales
# ──────────────────────────────────────────────

_ET = pytz.timezone("US/Eastern")

def _ahora_et():
    return datetime.now(_ET)

def _es_viernes(dt=None):
    if dt is None:
        dt = _ahora_et()
    return dt.weekday() == 4

def _ventana_horaria(dt=None):
    """Determina la ventana de trading actual según la hora ET."""
    if dt is None:
        dt = _ahora_et()
    hora = dt.hour + dt.minute / 60
    if 9.5 <= hora < 10.0:
        return "MAGICA", "9:30 - 10:00 AM ET", "Máxima atención. Mayor volatilidad y volumen de apertura. Mejor ventana para setups A1 y A3."
    elif 10.0 <= hora < 11.5:
        return "ACTIVA", "10:00 - 11:30 AM ET", "Alta liquidez. Buen momento para A2 y A4. Seguir tendencia dominante."
    elif 11.5 <= hora < 14.5:
        return "MUERTA", "11:30 AM - 2:30 PM ET", "BAJA VOLATILIDAD. NO OPERAR. Solo revisar Plan del 35% y preparar análisis para la tarde."
    elif 14.5 <= hora < 16.0:
        return "CIERRE", "2:30 - 4:00 PM ET", "Posible aumento de volatilidad hacia el cierre. Operar con cautela, solo setups de alta probabilidad."
    else:
        return "FUERA", "Fuera del horario", "El mercado está cerrado. Prepara el análisis para mañana."

def _obtener_datos(symbol, interval="15m", period="5d"):
    """Obtiene datos OHLCV de yfinance."""
    try:
        symbol = symbol.replace('$', '').strip().upper() if symbol else symbol
        ticker = yf.Ticker(symbol)
        df = ticker.history(interval=interval, period=period)
        if df.empty or len(df) < 20:
            return None, "Datos insuficientes para el análisis."
        df.dropna(inplace=True)
        return df, None
    except Exception as e:
        return None, f"Error obteniendo datos: {e}"


# ──────────────────────────────────────────────
#  Módulo 1: Bandas de Bollinger (20,2)
# ──────────────────────────────────────────────

def _bollinger_bands(df, window=20, num_std=2):
    close = df["Close"]
    sma = close.rolling(window=window).mean()
    std = close.rolling(window=window).std()
    bb_upper = sma + num_std * std
    bb_lower = sma - num_std * std
    bb_width = (bb_upper - bb_lower) / sma * 100
    current_close = close.iloc[-1]
    current_upper = bb_upper.iloc[-1]
    current_lower = bb_lower.iloc[-1]
    current_sma = sma.iloc[-1]
    current_width = bb_width.iloc[-1]
    avg_width = bb_width.mean()

    # Squeeze detection: width < 70% of avg width (last 5 periods)
    recent_width = bb_width.iloc[-5:].mean() if len(bb_width) >= 5 else current_width
    squeeze = recent_width < avg_width * 0.7

    # Position within bands
    if current_close >= current_upper:
        position = "FUERA arriba (sobrecomprado)"
    elif current_close <= current_lower:
        position = "FUERA abajo (sobrevendido)"
    elif current_close > current_sma:
        position = "Mitad superior"
    else:
        position = "Mitad inferior"

    # Volatility description
    if current_width > avg_width * 1.3:
        volatilidad = "ALTA"
    elif current_width < avg_width * 0.7:
        volatilidad = "BAJA (posible squeeze)"
    else:
        volatilidad = "NORMAL"

    return {
        "upper": round(current_upper, 2),
        "lower": round(current_lower, 2),
        "sma": round(current_sma, 2),
        "close": round(current_close, 2),
        "width_pct": round(current_width, 2),
        "avg_width_pct": round(avg_width, 2),
        "squeeze": squeeze,
        "position": position,
        "volatilidad": volatilidad,
    }


# ──────────────────────────────────────────────
#  Módulo 2: Ventanas Horarias + Setup Detection
# ──────────────────────────────────────────────

def _setup_detection(df, bb, ventana):
    """Detecta los 4 setups de Yoel Sardiñas."""
    close = df["Close"]
    high = df["High"]
    low = df["Low"]
    volume = df["Volume"]
    mme20 = close.ewm(span=20).mean()

    if len(df) < 30:
        return [], "Datos insuficientes para detección de setups."

    setups = []

    # --- MME20 (exponential moving average 20) ---
    current_mme20 = mme20.iloc[-1]
    prev_close = close.iloc[-2] if len(close) > 1 else close.iloc[-1]
    current_close = close.iloc[-1]

    # Tendencia básica: precio > MME20 = alcista, < MME20 = bajista
    trend = "ALCISTA" if current_close > current_mme20 else "BAJISTA"

    # --- A1: Pullback a MME20 en tendencia ---
    atr = (high - low).rolling(14).mean().iloc[-1]
    dist_to_mme = abs(current_close - current_mme20)
    pullback_touch = dist_to_mme < (atr * 0.3)
    if pullback_touch:
        direction = "LONG" if trend == "ALCISTA" else "SHORT"
        entry = round(current_mme20, 2)
        stop = round(entry - atr * 1.5, 2) if direction == "LONG" else round(entry + atr * 1.5, 2)
        target = round(entry + atr * 2.5, 2) if direction == "LONG" else round(entry - atr * 2.5, 2)
        setups.append({
            "setup": "A1 - Pullback a MME20",
            "direction": direction,
            "entry": entry,
            "stop": stop,
            "target": target,
            "rr": round(abs(target - entry) / abs(stop - entry), 2),
            "confidence": "ALTA" if ventana == "MAGICA" else "MEDIA",
        })

    # --- A2: Quiebre de MME20 con volumen ---
    avg_vol = volume.rolling(20).mean().iloc[-1]
    vol_spike = volume.iloc[-1] > avg_vol * 1.5
    crossover_up = prev_close < current_mme20 and current_close > current_mme20
    crossover_down = prev_close > current_mme20 and current_close < current_mme20
    if vol_spike and (crossover_up or crossover_down):
        direction = "LONG" if crossover_up else "SHORT"
        entry = round(current_close, 2)
        stop = round(entry - atr * 1.2, 2) if direction == "LONG" else round(entry + atr * 1.2, 2)
        target = round(entry + atr * 2.0, 2) if direction == "LONG" else round(entry - atr * 2.0, 2)
        setups.append({
            "setup": "A2 - Quiebre de MME20 + Volumen",
            "direction": direction,
            "entry": entry,
            "stop": stop,
            "target": target,
            "rr": round(abs(target - entry) / abs(stop - entry), 2),
            "confidence": "ALTA",
        })

    # --- A3: FVG en zona de liquidez ---
    fvg_found = False
    for i in range(len(df) - 3, max(len(df) - 10, 0), -1):
        c1_high = high.iloc[i]
        c1_low = low.iloc[i]
        c2_high = high.iloc[i + 1]
        c2_low = low.iloc[i + 1]
        c3_high = high.iloc[i + 2]
        c3_low = low.iloc[i + 2]
        # Bullish FVG: c1_high < c2_low (gap up) + c3 closes above
        if c1_high < c2_low and close.iloc[i + 2] > c2_low:
            gap = c2_low - c1_high
            if gap > (c1_high - c1_low) * 0.3:
                entry = round(c2_low, 2)
                stop = round(c1_high - atr * 0.5, 2)
                target = round(entry + atr * 2.0, 2)
                setups.append({
                    "setup": "A3 - FVG alcista en zona de liquidez",
                    "direction": "LONG",
                    "entry": entry,
                    "stop": stop,
                    "target": target,
                    "rr": round(abs(target - entry) / abs(stop - entry), 2),
                    "confidence": "ALTA" if ventana == "MAGICA" else "MEDIA",
                })
                fvg_found = True
                break
        # Bearish FVG: c1_low > c2_high (gap down) + c3 closes below
        if c1_low > c2_high and close.iloc[i + 2] < c2_high:
            gap = c1_low - c2_high
            if gap > (c1_high - c1_low) * 0.3:
                entry = round(c2_high, 2)
                stop = round(c1_low + atr * 0.5, 2)
                target = round(entry - atr * 2.0, 2)
                setups.append({
                    "setup": "A3 - FVG bajista en zona de liquidez",
                    "direction": "SHORT",
                    "entry": entry,
                    "stop": stop,
                    "target": target,
                    "rr": round(abs(target - entry) / abs(stop - entry), 2),
                    "confidence": "ALTA" if ventana == "MAGICA" else "MEDIA",
                })
                fvg_found = True
                break

    # --- A4: Doble test en BB inferior/superior + divergencia ---
    if len(df) > 40:
        recent_low = low.iloc[-10:].min()
        recent_high = high.iloc[-10:].max()
        bb_lower = bb["lower"]
        bb_upper = bb["upper"]
        touch_lower = abs(low.iloc[-1] - bb_lower) < atr * 0.3
        touch_upper = abs(high.iloc[-1] - bb_upper) < atr * 0.3
        rsi = 100 - (100 / (1 + close.diff().clip(lower=0).rolling(14).mean() /
                     (-close.diff().clip(upper=0).rolling(14).mean() + 1e-10)))
        rsi_val = rsi.iloc[-1]
        rsi_prev = rsi.iloc[-5] if len(rsi) > 5 else rsi_val
        # Divergencia alcista: precio hace mínimo más bajo, RSI hace mínimo más alto
        low_prev = low.iloc[-10:-5].min()
        low_now = low.iloc[-5:].min()
        rsi_low_prev = rsi.iloc[-10:-5].min()
        rsi_low_now = rsi.iloc[-5:].min()
        bullish_div = low_now < low_prev and rsi_low_now > rsi_low_prev
        bearish_div = low_now > low_prev and rsi_low_now < rsi_low_prev
        if touch_lower and bullish_div:
            entry = round(current_close, 2)
            stop = round(low.iloc[-1] - atr * 0.8, 2)
            target = round(entry + atr * 2.0, 2)
            setups.append({
                "setup": "A4 - Doble test BB inferior + divergencia alcista",
                "direction": "LONG",
                "entry": entry,
                "stop": stop,
                "target": target,
                "rr": round(abs(target - entry) / abs(stop - entry), 2),
                "confidence": "ALTA",
            })
        elif touch_upper and bearish_div:
            entry = round(current_close, 2)
            stop = round(high.iloc[-1] + atr * 0.8, 2)
            target = round(entry - atr * 2.0, 2)
            setups.append({
                "setup": "A4 - Doble test BB superior + divergencia bajista",
                "direction": "SHORT",
                "entry": entry,
                "stop": stop,
                "target": target,
                "rr": round(abs(target - entry) / abs(stop - entry), 2),
                "confidence": "ALTA",
            })

    return setups, trend


# ──────────────────────────────────────────────
#  Módulo 3: FVG (Fair Value Gap) Detection
# ──────────────────────────────────────────────

def _detectar_fvgs(df):
    """Detecta Fair Value Gaps en las últimas 20 velas."""
    high = df["High"]
    low = df["Low"]
    close = df["Close"]
    open_ = df["Open"]
    fvgs = []
    n = min(20, len(df) - 2)
    for i in range(len(df) - n, len(df) - 2):
        c1_high = high.iloc[i]
        c1_low = low.iloc[i]
        c1_range = c1_high - c1_low
        c2_high = high.iloc[i + 1]
        c2_low = low.iloc[i + 1]
        c3_high = high.iloc[i + 2]
        c3_low = low.iloc[i + 2]
        c3_close = close.iloc[i + 2]
        c3_open = open_.iloc[i + 2]

        # Bullish FVG: gap up, c3 body confirms
        if c1_high < c2_low and c3_close > c2_low:
            gap_size = c2_low - c1_high
            if gap_size >= c1_range * 0.3:
                fvgs.append({
                    "tipo": "ALCISTA",
                    "gap_start": round(c1_high, 2),
                    "gap_end": round(c2_low, 2),
                    "gap_size_pct": round(gap_size / c1_range * 100, 1),
                    "posicion": i - (len(df) - n),
                    "filled": c1_high < c3_close,
                })
        # Bearish FVG: gap down, c3 body confirms
        if c1_low > c2_high and c3_close < c2_high:
            gap_size = c1_low - c2_high
            if gap_size >= c1_range * 0.3:
                fvgs.append({
                    "tipo": "BAJISTA",
                    "gap_start": round(c2_high, 2),
                    "gap_end": round(c1_low, 2),
                    "gap_size_pct": round(gap_size / c1_range * 100, 1),
                    "posicion": i - (len(df) - n),
                    "filled": c1_low > c3_close,
                })
    return fvgs[:5]


# ──────────────────────────────────────────────
#  Módulo 4: Plan del 35%
# ──────────────────────────────────────────────

def _plan_del_35(meta_semanal=1000, ganancia_hoy=0, trades_hoy=0, max_trades=2):
    """
    Calcula el Plan del 35% de Yoel Sardiñas.
    - Si hoy ya ganaste >=35% de la meta semanal, PARAR.
    - Máximo 2 trades por día.
    """
    objetivo_diario = meta_semanal * 0.35
    restante = max(0, objetivo_diario - ganancia_hoy)
    cumplido = ganancia_hoy >= objetivo_diario
    trades_restantes = max(0, max_trades - trades_hoy)

    return {
        "meta_semanal": meta_semanal,
        "objetivo_diario": round(objetivo_diario, 2),
        "ganancia_hoy": round(ganancia_hoy, 2),
        "restante_para_objetivo": round(restante, 2),
        "objetivo_cumplido": cumplido,
        "trades_hoy": trades_hoy,
        "trades_restantes": trades_restantes,
        "max_trades": max_trades,
        "recomendacion": "OBJETIVO DIARIO CUMPLIDO. DEJAR DE OPERAR POR HOY." if cumplido else
                         f"Faltan ${restante:.2f} para el objetivo del día. Tienes {trades_restantes} trade(s) restante(s)." if trades_restantes > 0 else
                         "No más trades disponibles hoy.",
    }


# ──────────────────────────────────────────────
#  Módulo 5: Gestión de Riesgo
# ──────────────────────────────────────────────

def _gestion_riesgo(saldo_cuenta=5000, riesgo_pct=1.5, entry=0, stop=0):
    if entry == 0 or stop == 0 or entry == stop:
        return {"error": "Precios inválidos para calcular riesgo."}
    riesgo_dolares = saldo_cuenta * (riesgo_pct / 100)
    distancia_stop = abs(entry - stop)
    if distancia_stop == 0:
        return {"error": "Distancia al stop es cero."}
    tamanio = riesgo_dolares / distancia_stop
    direccion = "LONG" if entry < stop else "SHORT"
    if direccion == "LONG":
        tamanio = riesgo_dolares / distancia_stop
    else:
        tamanio = riesgo_dolares / distancia_stop
    return {
        "saldo_cuenta": saldo_cuenta,
        "riesgo_pct": riesgo_pct,
        "riesgo_dolares": round(riesgo_dolares, 2),
        "distancia_stop": round(distancia_stop, 2),
        "tamanio_posicion": round(tamanio, 4),
        "tamanio_formateado": f"{tamanio:.2f} unidades",
    }


# ──────────────────────────────────────────────
#  Función Principal
# ──────────────────────────────────────────────

def analisis_sardiñas(symbol: str, meta_semanal: float = 1000, saldo_cuenta: float = 5000) -> str:
    """
    Sistema de Trading de Yoel Sardiñas "The Tradingway".
    Analiza un activo y devuelve un reporte completo con los 5 módulos.
    """
    parts = []
    ahora = _ahora_et()

    # ── Cabecera ──
    parts.append(f"╔{'═'*65}╗")
    parts.append(f"║  SISTEMA DE TRADING YOEL SARDIÑAS — THE TRADINGWAY")
    parts.append(f"║  Análisis de: {symbol}")
    parts.append(f"║  Fecha/Hora ET: {ahora.strftime('%Y-%m-%d %I:%M %p ET')}")
    parts.append(f"╚{'═'*65}╝")

    # ── Verificación de día: evitar viernes ──
    if _es_viernes(ahora):
        parts.append(f"\n{'!'*65}")
        parts.append("⚠️ HOY ES VIERNES — NO OPERAR SEGÚN EL SISTEMA.")
        parts.append("   El sistema de Yoel Sardiñas recomienda NO operar los viernes.")
        parts.append("   Dedicar el día a repasar trades, ajustar el plan y preparar la próxima semana.")
        parts.append(f"{'!'*65}")
        parts.append(f"\n{'─'*65}")
        parts.append("[ANÁLISIS INFORMATIVO — SIN SETUPS ACTIVOS]")
        parts.append("(El análisis de bandas, FVG y plan del 35% se muestra solo como referencia.)")
        solo_informativo = True
    else:
        solo_informativo = False

    # ── Ventana Horaria ──
    ventana_id, ventana_rango, ventana_desc = _ventana_horaria(ahora)
    parts.append(f"\n{'─'*65}")
    parts.append(f"> VENTANA HORARIA: {ventana_id} ({ventana_rango})")
    parts.append(f"   {ventana_desc}")
    if ventana_id == "MUERTA" and not solo_informativo:
        parts.append(f"\n   ⚠️ VENTANA MUERTA: NO OPERAR. Solo preparación y análisis.")
        solo_informativo = True

    if solo_informativo and ventana_id == "MUERTA":
        solo_informativo = True

    # ── Obtener datos ──
    df, error = _obtener_datos(symbol)
    if error or df is None:
        parts.append(f"\n⚠️ Error obteniendo datos: {error}")
        parts.append(f"\n{'═'*65}")
        return "\n".join(parts)

    # ── SECCIÓN 1: BANDAS DE BOLLINGER ──
    bb = _bollinger_bands(df)
    parts.append(f"\n{'─'*65}")
    parts.append("📊 BANDAS DE BOLLINGER (20, 2)")
    parts.append(f"   Precio actual: ${bb['close']}")
    parts.append(f"   BB Superior: ${bb['upper']} | BB Inferior: ${bb['lower']}")
    parts.append(f"   SMA 20: ${bb['sma']}")
    parts.append(f"   Ancho de bandas: {bb['width_pct']}% (promedio: {bb['avg_width_pct']}%)")
    parts.append(f"   Posición del precio: {bb['position']}")
    parts.append(f"   Volatilidad: {bb['volatilidad']}")
    if bb['squeeze']:
        parts.append(f"   ⚠️ SQUEEZE DETECTADO: Bandas estrechas. Prepararse para expansión de volatilidad.")

    # ── SECCIÓN 2: VENTANA HORARIA Y SETUPS ──
    parts.append(f"\n{'─'*65}")
    parts.append(f"🕐 VENTANA HORARIA: {ventana_id}")
    parts.append(f"   Horario: {ventana_rango}")
    parts.append(f"   Nota: {ventana_desc}")

    # ── SECCIÓN 3: SETUP DETECTADO ──
    setups, trend = _setup_detection(df, bb, ventana_id)
    parts.append(f"\n{'─'*65}")
    parts.append(f"🎯 SETUP DETECTADO")
    parts.append(f"   Tendencia: {trend}")
    if not setups:
        parts.append(f"   No se detectaron setups activos en este momento.")
        parts.append(f"   Consejo: Esperar a que el precio se acerque a MME20 o se forme un FVG.")
    else:
        for s in setups:
            parts.append(f"\n   {'='*50}")
            parts.append(f"   ✅ SETUP: {s['setup']}")
            parts.append(f"   Dirección: {s['direction']}")
            parts.append(f"   Entrada: ${s['entry']}")
            parts.append(f"   Stop Loss: ${s['stop']}")
            parts.append(f"   Take Profit: ${s['target']}")
            parts.append(f"   Riesgo/Beneficio: 1:{s['rr']}")
            parts.append(f"   Confianza: {s['confidence']}")

    # ── SECCIÓN 4: ENTRADA, STOP LOSS, TAKE PROFIT ──
    parts.append(f"\n{'─'*65}")
    parts.append(f"💰 ENTRADA / STOP LOSS / TAKE PROFIT")
    if setups:
        for s in setups:
            parts.append(f"\n   Setup: {s['setup']}")
            parts.append(f"   Entrada: ${s['entry']} | SL: ${s['stop']} | TP: ${s['target']}")
            parts.append(f"   Ratio R:R: 1:{s['rr']}")
    else:
        parts.append(f"   Sin setups activos. Esperar señales de entrada.")

    # ── SECCIÓN 5: GESTIÓN DE RIESGO ──
    parts.append(f"\n{'─'*65}")
    parts.append(f"🔒 GESTION DE RIESGO")
    if setups:
        primary = setups[0]
        riesgo = _gestion_riesgo(saldo_cuenta=saldo_cuenta, entry=primary["entry"], stop=primary["stop"])
        if "error" not in riesgo:
            parts.append(f"   Saldo de cuenta: ${riesgo['saldo_cuenta']}")
            parts.append(f"   Riesgo por operación: {riesgo['riesgo_pct']}% (${riesgo['riesgo_dolares']})")
            parts.append(f"   Distancia al stop: ${riesgo['distancia_stop']}")
            parts.append(f"   Tamaño de posición sugerido: {riesgo['tamanio_formateado']}")
    else:
        parts.append(f"   Sin setups activos. No aplicar riesgo ahora.")

    # ── SECCIÓN 6: FVG DETECTADOS ──
    fvgs = _detectar_fvgs(df)
    parts.append(f"\n{'─'*65}")
    parts.append(f"🔍 FAIR VALUE GAPS (FVG)")
    if fvgs:
        for fvg in fvgs:
            direc = "🟢" if fvg["tipo"] == "ALCISTA" else "🔴"
            parts.append(f"   {direc} FVG {fvg['tipo']}: ${fvg['gap_start']} → ${fvg['gap_end']}")
            parts.append(f"      Tamaño: {fvg['gap_size_pct']}% del rango de vela anterior")
    else:
        parts.append(f"   No se detectaron FVGs significativos en las últimas 20 velas.")

    # ── SECCIÓN 7: CHECKLIST ──
    parts.append(f"\n{'─'*65}")
    parts.append(f"📋 CHECKLIST PRE-OPERACION")
    parts.append(f"   {'✅' if ventana_id != 'MUERTA' and ventana_id != 'FUERA' else '❌'} Ventana horaria valida ({ventana_id})")
    parts.append(f"   {'✅' if not _es_viernes(ahora) else '❌'} Dia valido (no viernes)")
    parts.append(f"   {'✅' if setups else '❌'} Setup de entrada detectado")
    parts.append(f"   {'✅' if not bb['squeeze'] else '⚠️'} Sin squeeze (o squeeze detectado)")
    parts.append(f"   {'✅' if fvgs else '⚠️'} FVG disponible como referencia")
    parts.append(f"   {'✅' if bb['volatilidad'] != 'BAJA (posible squeeze)' else '⚠️'} Volatilidad adecuada para operar")

    # ── SECCIÓN 8: RECORDATORIOS ──
    parts.append(f"\n{'─'*65}")
    parts.append(f"💡 RECORDATORIOS Y RECOMENDACIONES")
    parts.append(f"   • Respetar la ventana horaria — no operar en ventana MUERTA.")
    parts.append(f"   • No operar los viernes (filosofía Sardiñas).")
    parts.append(f"   • Máximo 2 trades por día (Plan del 35%).")
    parts.append(f"   • Relación R:R mínima 1:2.")
    parts.append(f"   • Usar siempre stop loss. No moverlo en contra.")
    parts.append(f"   • Si hay squeeze: esperar la expansión, no anticiparla.")
    parts.append(f"   • No promediar posiciones perdedoras.")
    parts.append(f"   • La mejor operación es la que NO haces.")

    # ── SECCIÓN 9: PLAN DEL 35% ──
    parts.append(f"\n{'─'*65}")
    parts.append(f"🎯 PLAN DEL 35%")
    plan = _plan_del_35(meta_semanal=meta_semanal)
    parts.append(f"   Meta semanal: ${plan['meta_semanal']}")
    parts.append(f"   Objetivo diario (35%): ${plan['objetivo_diario']}")
    parts.append(f"   Trades hoy: {plan['trades_hoy']} / {plan['max_trades']}")
    parts.append(f"   Trades restantes: {plan['trades_restantes']}")
    parts.append(f"   ▶  {plan['recomendacion']}")

    # ── Cierre ──
    parts.append(f"\n{'═'*65}")
    parts.append("SISTEMA DE TRADING YOEL SARDIÑAS — THE TRADINGWAY")
    parts.append(f"{'═'*65}")
    parts.append("\n⚠️ Esto es un analisis estadistico, no un consejo financiero.")
    parts.append("Opere con gestión de riesgo y disciplina.")

    return "\n".join(parts)
