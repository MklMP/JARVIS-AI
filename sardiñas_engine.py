"""
Motor de análisis del sistema de trading Yoel Sardiñas "The Tradingway".
Sin dependencias de Flask. Usa yfinance, matplotlib, pytz.
"""

import yfinance as yf
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime, timezone, timedelta
from io import BytesIO
import pytz
import warnings
warnings.filterwarnings("ignore", category=FutureWarning)

_ET = pytz.timezone("US/Eastern")

# ── Símbolos especiales para TradingView ──
_TV_MAP = {
    "^GSPC": "SP:SPX",
    "^IXIC": "NASDAQ:IXIC",
    "^DJI": "DJ:DJI",
    "^IBEX": "TVC:IBEX",
    "GC=F": "TVC:GOLD",
    "SI=F": "TVC:SILVER",
    "CL=F": "TVC:USOIL",
    "EURUSD=X": "FX:EURUSD",
    "GBPUSD=X": "FX:GBPUSD",
}


def _tv_symbol(symbol):
    return _TV_MAP.get(symbol, symbol)


def evaluar_ventana(now_et=None):
    """Devuelve (ventana_str, operable_bool, mensaje)."""
    if now_et is None:
        now_et = datetime.now(_ET)
    wd = now_et.weekday()
    if wd == 4:  # viernes
        return ("VIERNES", False,
                "HOY ES VIERNES — NO OPERAR. El sistema Sardiñas prohíbe operar "
                "los viernes. Use el día para repasar trades y ajustar el plan.")
    if wd >= 5:
        return ("FINDE", False,
                "Mercado cerrado (fin de semana). Prepare el análisis para el lunes.")
    hora = now_et.hour + now_et.minute / 60.0
    if 9.5 <= hora < 10.0:
        return ("MAGICA", True,
                "Ventana MÁGICA (9:30-10:00 ET). Máxima volatilidad. "
                "Mejor momento para setups A1 y A3.")
    if 10.0 <= hora < 11.5:
        return ("ACTIVA", True,
                "Ventana ACTIVA (10:00-11:30 ET). Alta liquidez. "
                "Buen momento para A2 y A4.")
    if 11.5 <= hora < 14.5:
        return ("MUERTA", False,
                "VENTANA MUERTA (11:30-14:30 ET). NO OPERAR. "
                "Baja volatilidad. Solo preparación y análisis.")
    if 14.5 <= hora < 16.0:
        return ("CIERRE", True,
                "Ventana de CIERRE (14:30-16:00 ET). "
                "Posible aumento de volatilidad, operar con cautela.")
    return ("CERRADO", False,
            "Mercado cerrado fuera del horario (9:30-16:00 ET).")


def obtener_datos(symbol: str, interval: str = "15m", period: str = "5d"):
    """Descarga velas OHLCV de yfinance. Devuelve (df, error)."""
    try:
        symbol = symbol.replace('$', '').strip().upper() if symbol else symbol
        ticker = yf.Ticker(symbol)
        df = ticker.history(interval=interval, period=period)
        if df.empty or len(df) < 30:
            return None, "Datos insuficientes (mínimo 30 velas requeridas)."
        df.dropna(inplace=True)
        return df, None
    except Exception as e:
        return None, f"Error descargando datos: {e}"


def calcular_bollinger(df: pd.DataFrame, window=20, num_std=2):
    """Añade columnas SMA, BB_Upper, BB_Lower, BB_Width al DataFrame."""
    df = df.copy()
    df["SMA"] = df["Close"].rolling(window=window).mean()
    df["BB_STD"] = df["Close"].rolling(window=window).std()
    df["BB_Upper"] = df["SMA"] + num_std * df["BB_STD"]
    df["BB_Lower"] = df["SMA"] - num_std * df["BB_STD"]
    df["BB_Width"] = (df["BB_Upper"] - df["BB_Lower"]) / df["SMA"] * 100
    return df


def detectar_setup(df: pd.DataFrame):
    """
    Detecta setups según Yoel Sardiñas.
    Devuelve (tipo_setup, direccion, compresion_bool, descripcion).
    """
    if df is None or len(df) < 30:
        return ("NINGUNO", "N/A", False, "Datos insuficientes.")

    df = calcular_bollinger(df)
    close = df["Close"]
    high = df["High"]
    low = df["Low"]
    volume = df["Volume"]
    mme20 = close.ewm(span=20).mean()
    atr = (high - low).rolling(14).mean()

    current = close.iloc[-1]
    bb_up = df["BB_Upper"].iloc[-1]
    bb_lo = df["BB_Lower"].iloc[-1]
    bb_sma = df["SMA"].iloc[-1]
    bb_width = df["BB_Width"].iloc[-1]
    avg_width = df["BB_Width"].mean()

    # Compresión?
    compresion = bb_width < avg_width * 0.75 and len(df) > 20

    # Tendencia
    trend = "ALCISTA" if current > mme20.iloc[-1] else "BAJISTA"
    cur_atr = atr.iloc[-1] if not atr.empty else 0
    if cur_atr == 0:
        cur_atr = (high - low).iloc[-10:].mean()

    # A1: Pullback a MME20
    dist_mme = abs(current - mme20.iloc[-1])
    if dist_mme < cur_atr * 0.3:
        direc = "LONG" if trend == "ALCISTA" else "SHORT"
        return ("A1 - Pullback a MME20", direc, compresion,
                f"Precio touchando MME20. {trend} a 1D.")

    # A2: Quiebre MME20 + volumen
    prev = close.iloc[-2] if len(close) > 1 else current
    avg_vol = volume.rolling(20).mean().iloc[-1]
    vol_spike = volume.iloc[-1] > avg_vol * 1.4
    crossover_up = prev < mme20.iloc[-1] and current > mme20.iloc[-1]
    crossover_down = prev > mme20.iloc[-1] and current < mme20.iloc[-1]
    if vol_spike and (crossover_up or crossover_down):
        direc = "LONG" if crossover_up else "SHORT"
        return ("A2 - Quiebre MME20 + Volumen", direc, compresion,
                f"Quiebre con volumen. Momentum {'alcista' if direc == 'LONG' else 'bajista'}.")

    # A4: Doble test BB + divergencia
    touch_lower = abs(low.iloc[-1] - bb_lo) < cur_atr * 0.5 if cur_atr else False
    touch_upper = abs(high.iloc[-1] - bb_up) < cur_atr * 0.5 if cur_atr else False
    if touch_lower or touch_upper:
        direc = "LONG" if touch_lower else "SHORT"
        extra = "en BB inferior" if touch_lower else "en BB superior"
        return ("A4 - Doble Test " + extra, direc, compresion,
                f"Precio tocando banda. Posible rebote.")

    # A3: FVG
    for i in range(len(df) - 3, max(len(df) - 10, 0), -1):
        c1h, c1l = high.iloc[i], low.iloc[i]
        c2h, c2l = high.iloc[i + 1], low.iloc[i + 1]
        c3c = close.iloc[i + 2]
        rng = c1h - c1l
        if rng == 0:
            continue
        # alcista
        if c1h < c2l and c3c > c2l and (c2l - c1h) > rng * 0.3:
            return ("A3 - FVG Alcista", "LONG", compresion,
                    f"FVG alcista detectado en vela {len(df) - i - 1} atrás.")
        # bajista
        if c1l > c2h and c3c < c2h and (c1l - c2h) > rng * 0.3:
            return ("A3 - FVG Bajista", "SHORT", compresion,
                    f"FVG bajista detectado en vela {len(df) - i - 1} atrás.")

    return ("NINGUNO", "N/A", compresion,
            "Sin setup claro. Esperar señales definidas.")


def generar_grafico(symbol: str, interval: str = "15m", period: str = "3d"):
    """
    Genera un gráfico Bollinger + precio + volumen con estilo HUD oscuro.
    Devuelve BytesIO con PNG o None si error.
    """
    df, err = obtener_datos(symbol, interval=interval, period=period)
    if err or df is None:
        return None
    df = calcular_bollinger(df)
    df = df.tail(60)

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(8, 5), gridspec_kw={"height_ratios": [3, 1]},
                                     sharex=True)
    fig.patch.set_facecolor("#0a0a12")
    bg = "#0a0a12"
    for ax in (ax1, ax2):
        ax.set_facecolor(bg)
        ax.tick_params(colors="#888")
        ax.spines["bottom"].set_color("#333")
        ax.spines["top"].set_color("#333")
        ax.spines["left"].set_color("#333")
        ax.spines["right"].set_color("#333")
        ax.grid(True, alpha=0.15, color="#00d4ff")

    # Precio
    ax1.plot(df.index, df["Close"], color="#00d4ff", linewidth=1.5, label="Close")
    ax1.plot(df.index, df["SMA"], color="#ffaa00", linewidth=0.8, alpha=0.7, label="SMA 20")
    ax1.fill_between(df.index, df["BB_Upper"], df["BB_Lower"],
                     alpha=0.1, color="#00d4ff", label="BB (20,2)")
    ax1.plot(df.index, df["BB_Upper"], color="#00d4ff", linewidth=0.6, alpha=0.5)
    ax1.plot(df.index, df["BB_Lower"], color="#00d4ff", linewidth=0.6, alpha=0.5)
    ax1.set_ylabel("Precio", color="#aaa")
    ax1.legend(loc="upper left", facecolor=bg, edgecolor="#333", labelcolor="#ccc", fontsize=8)

    # Volumen
    colors = ["#00ff88" if c >= o else "#ff4444" for c, o in zip(df["Close"], df["Open"])]
    ax2.bar(df.index, df["Volume"], color=colors, alpha=0.6, width=0.8)
    ax2.set_ylabel("Vol", color="#aaa")
    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
    plt.xticks(rotation=30, color="#888")

    fig.suptitle(f"{symbol} — Bollinger (20,2) {interval}",
                 color="#00d4ff", fontsize=12, fontweight="bold")
    plt.tight_layout()
    buf = BytesIO()
    plt.savefig(buf, format="png", dpi=100, facecolor=bg)
    plt.close(fig)
    buf.seek(0)
    return buf


def generar_enlaces(symbol: str, interval: str = "15"):
    """Devuelve URLs de TradingView y Finviz."""
    tv_sym = _tv_symbol(symbol)
    tv = f"https://www.tradingview.com/chart/?symbol={tv_sym}&interval={interval}"
    fv = f"https://finviz.com/quote.ashx?t={symbol}&ty=c&ta=1&p=d"
    return {"tradingview": tv, "finviz": fv}


def paso_inicial(symbol: str):
    """Ejecuta el primer paso (ventana) y devuelve el estado inicial."""
    ventana, operable, msg = evaluar_ventana()
    return {
        "ventana": ventana,
        "operable": operable,
        "mensaje_ventana": msg,
    }
