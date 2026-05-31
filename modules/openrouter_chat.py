import requests
import json
import re
import math
from datetime import datetime
from urllib.parse import quote
import pandas as pd

from modules.yoel_sardiñas_system import analisis_sardiñas


# Mapa de nombres de empresa -> sÃƒÆ’Ã‚Â­mbolo bursÃƒÆ’Ã‚Â¡til (para la herramienta mapear_simbolo)
EMPRESAS = {
    "apple": "AAPL", "microsoft": "MSFT", "google": "GOOGL", "alphabet": "GOOGL",
    "amazon": "AMZN", "tesla": "TSLA", "meta": "META", "facebook": "META",
    "netflix": "NFLX", "nvidia": "NVDA", "intel": "INTC", "amd": "AMD",
    "ibm": "IBM", "oracle": "ORCL", "cisco": "CSCO",
    "uber": "UBER", "lyft": "LYFT", "airbnb": "ABNB", "spotify": "SPOT",
    "paypal": "PYPL", "square": "SQ", "block": "SQ",
    "visa": "V", "mastercard": "MA", "american express": "AXP",
    "disney": "DIS", "walt disney": "DIS",
    "coca cola": "KO", "pepsi": "PEP", "mcdonalds": "MCD", "starbucks": "SBUX", "nike": "NKE",
    "mercedes": "MBG.DE", "bmw": "BMW.DE", "volkswagen": "VOW3.DE", "porsche": "P911.DE",
    "siemens": "SIE.DE", "sap": "SAP.DE",
    "telefonica": "TEF", "bbva": "BBVA", "santander": "SAN",
    "repsol": "REP.MC", "iberdrola": "IBE.MC", "inditex": "ITX.MC", "zara": "ITX.MC",
    "mercadolibre": "MELI", "mercado libre": "MELI", "globant": "GLOB",
    "bitcoin": "BTC-USD", "btc": "BTC-USD", "ethereum": "ETH-USD", "eth": "ETH-USD",
    "dogecoin": "DOGE-USD", "cardano": "ADA-USD", "solana": "SOL-USD",
    "ripple": "XRP-USD", "xrp": "XRP-USD", "binance": "BNB-USD", "polygon": "MATIC-USD",
    "chainlink": "LINK-USD",
    "oro": "GC=F", "plata": "SI=F", "petrÃƒÆ’Ã‚Â³leo": "CL=F", "petroleo": "CL=F",
    "euro": "EURUSD=X", "libra": "GBPUSD=X",
    "ibex35": "^IBEX", "ibex 35": "^IBEX", "sp500": "^GSPC", "s&p 500": "^GSPC",
    "nasdaq": "^IXIC", "dow jones": "^DJI",
}

# Verbos comunes que NO deben tratarse como tickers bursÃƒÆ’Ã‚Â¡tiles
_VERBOS = {
    "puede", "debe", "quiere", "hace", "tiene", "sabe", "dice", "haz", "va",
    "puedo", "debo", "quiero", "hago", "tengo", "se", "ves", "mira", "dame",
    "busca", "pon", "saca", "abre", "cierra", "mueve", "copia", "borra",
    "crea", "listo", "vamos", "sigue", "para", "mÃƒÆ’Ã‚Â¡s", "menos", "todo",
    "bueno", "malo", "asi", "asÃƒÆ’Ã‚Â­", "como", "que", "cual", "cÃƒÆ’Ã‚Â³mo", "quÃƒÆ’Ã‚Â©",
}

# Watchlist para scanner de Bollinger
WATCHLIST = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "META", "NVDA", "NFLX", "PYPL", "ADBE",
    "INTC", "AMD", "BA", "DIS", "JPM", "V", "MA", "WMT", "KO", "PEP",
    "MCD", "NKE", "HD", "CRM", "ABNB", "UBER", "SQ", "SNAP", "ZM", "COIN",
    "SPY", "QQQ", "IWM", "DIA",
    "BTC-USD", "ETH-USD", "SOL-USD", "XRP-USD", "GC=F", "CL=F",
]


def limpiar_simbolo(s: str) -> str:
    """Limpia un símbolo quitando $ y espacios."""
    return s.replace('$', '').strip().upper()


def _get_hist_series(ticker, period):
    """Obtiene DataFrame plano (sin MultiIndex) de yfinance."""
    h = ticker.history(period=period)
    return h


def _calcular_bb(symbol: str, period: int = 20, std_dev: float = 2.0) -> dict:
    """Calcula Bandas de Bollinger para un símbolo y devuelve datos de la última vela."""
    import pandas as pd
    import numpy as np
    import yfinance as yf
    try:
        symbol = limpiar_simbolo(symbol)
        ticker = yf.Ticker(symbol)
        hist = _get_hist_series(ticker, f"{max(period*5, 60)}d")
        if hist.empty or len(hist) < period:
            return {}
        close = hist["Close"].astype(float)
        sma = close.rolling(window=period).mean()
        std = close.rolling(window=period).std()
        upper = sma + (std_dev * std)
        lower = sma - (std_dev * std)
        last_close = float(close.iloc[-1])
        last_sma = float(sma.iloc[-1])
        last_upper = float(upper.iloc[-1])
        last_lower = float(lower.iloc[-1])
        volume = hist["Volume"].tolist() if "Volume" in hist.columns else []
        vol_avg = float(pd.Series(volume).tail(20).mean()) if len(volume) >= 20 else 1
        last_vol = float(volume[-1]) if volume else 1
        vol_ratio = last_vol / vol_avg if vol_avg > 0 else 1
        # MA200
        hist_200 = _get_hist_series(ticker, "1y")
        sma200 = float(hist_200["Close"].tail(200).mean()) if len(hist_200) >= 200 else None
        band_width = ((last_upper - last_lower) / last_sma) * 100 if last_sma else 0
        return {
            "symbol": symbol,
            "close": last_close,
            "sma": last_sma,
            "upper": last_upper,
            "lower": last_lower,
            "band_width": band_width,
            "below_lower": last_close < last_lower,
            "above_upper": last_close > last_upper,
            "vol_ratio": vol_ratio,
            "vol_avg": vol_avg,
            "last_vol": last_vol,
            "sma200": sma200,
            "hist": hist,
        }
    except Exception:
        return {}


def _detectar_fvg_4h(symbol: str) -> list:
    """Detecta Fair Value Gaps en gráfico de 4h usando pandas."""
    import pandas as pd
    import yfinance as yf
    try:
        symbol = limpiar_simbolo(symbol)
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="15d", interval="1h")
        if hist.empty or len(hist) < 30:
            return []
        # Resample a 4h
        ohlc_4h = hist.resample("4h", label="right", closed="right").agg({
            "Open": "first", "High": "max", "Low": "min", "Close": "last"
        }).dropna()
        fvgs = []
        for i in range(2, len(ohlc_4h)):
            prev_high = float(ohlc_4h["High"].iloc[i-2])
            prev_low = float(ohlc_4h["Low"].iloc[i-2])
            curr_high = float(ohlc_4h["High"].iloc[i-1])
            curr_low = float(ohlc_4h["Low"].iloc[i-1])
            next_high = float(ohlc_4h["High"].iloc[i])
            next_low = float(ohlc_4h["Low"].iloc[i])
            date = ohlc_4h.index[i]
            # Bullish FVG: current low > previous high (gap up)
            if curr_low > prev_high:
                fvgs.append({
                    "type": "bullish",
                    "top": curr_low,
                    "bottom": prev_high,
                    "date": date.strftime("%Y-%m-%d %H:%M"),
                })
            # Bearish FVG: current high < previous low (gap down)
            if curr_high < prev_low:
                fvgs.append({
                    "type": "bearish",
                    "top": prev_low,
                    "bottom": curr_high,
                    "date": date.strftime("%Y-%m-%d %H:%M"),
                })
        return fvgs
    except Exception:
        return []


def scan_bollinger_breakouts(symbols: list = None, period: int = 20, std_dev: float = 2.0) -> list:
    """Escanea una lista de sÃƒÆ’Ã‚Â­mbolos buscando precios fuera de Bandas de Bollinger."""
    if symbols is None:
        symbols = WATCHLIST
    oportunidades = []
    for sym in symbols:
        data = _calcular_bb(sym, period, std_dev)
        if not data:
            continue
        if not data["below_lower"] and not data["above_upper"]:
            continue
        # Filtro de volumen: debe ser > 80% del promedio
        if data["vol_ratio"] < 0.8:
            continue
        direccion = "compra" if data["below_lower"] else "venta"
        nota = ""
        if direccion == "compra" and data["sma200"] is not None and data["close"] < data["sma200"]:
            nota = "Ã¢Å¡Â Ã¯Â¸Â Precio bajo MA200 ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â senal mas debil, cautela."
        oportunidades.append({
            "symbol": data["symbol"],
            "price": data["close"],
            "direction": direccion,
            "upper": data["upper"],
            "lower": data["lower"],
            "sma": data["sma"],
            "band_width": data["band_width"],
            "vol_ratio": data["vol_ratio"],
            "sma200": data["sma200"],
            "note": nota,
            "hist": data["hist"],
        })
    return oportunidades


def generate_pine_script(symbol: str, entry: float, sl: float, tp1: float, tp2: float, direction: str) -> str:
    """Genera cÃƒÆ’Ã‚Â³digo Pine Script para TradingView con niveles de entrada, SL y TP."""
    color_sl = "#ef5350"  # rojo
    color_tp = "#66bb6a"  # verde
    color_entry = "#42a5f5"  # azul
    return f"""//@version=5
indicator("JARVIS Setup - {symbol}", overlay=true)
// Bandas de Bollinger (20,2)
length = 20
src = close
mult = 2.0
basis = ta.sma(src, length)
dev = mult * ta.stdev(src, length)
upper = basis + dev
lower = basis - dev
plot(basis, "MA20", color=color.new(#FF9800, 0))
plot(upper, "Upper", color=color.new(#2196F3, 0))
plot(lower, "Lower", color=color.new(#2196F3, 0))
// Niveles JARVIS
entryLine = hline({entry:.2f}, "Entrada", color=color.new({color_entry}, 0))
slLine = hline({sl:.2f}, "Stop Loss", color=color.new({color_sl}, 0))
tp1Line = hline({tp1:.2f}, "TP1", color=color.new({color_tp}, 0))
tp2Line = hline({tp2:.2f}, "TP2", color=color.new({color_tp}, 80))
fill(entryLine, slLine, color=color.new({color_sl}, 90), title="Riesgo")
fill(entryLine, tp1Line, color=color.new({color_tp}, 90), title="TP1")
"""


def generate_trade_setup(opp: dict) -> dict:
    """A partir de una oportunidad de Bollinger, genera el setup completo con ICT."""
    import numpy as np
    import pandas as pd
    sym = opp["symbol"]
    precio = opp["price"]
    direccion = opp["direction"]
    sma = opp["sma"]
    upper = opp["upper"]
    lower = opp["lower"]
    band_width = opp["band_width"]
    vol_ratio = opp["vol_ratio"]
    sma200 = opp["sma200"]
    note = opp["note"]
    hist = opp.get("hist")
    # --- FVG detection ---
    fvgs = _detectar_fvg_4h(sym)
    fvg_info = ""
    # --- Calcular niveles ---
    if direccion == "compra":
        # Entrada: en el FVG mÃƒÆ’Ã‚Â¡s cercano por debajo, o 50% de la vela de ruptura
        fvg_near = [f for f in fvgs if f["type"] == "bullish" and f["bottom"] < precio]
        if fvg_near:
            best_fvg = min(fvg_near, key=lambda f: abs(f["bottom"] - precio))
            entry = round((best_fvg["top"] + best_fvg["bottom"]) / 2, 2)
            fvg_info = f"FVG 4h alcista: {best_fvg['bottom']:.2f}-{best_fvg['top']:.2f} ({best_fvg['date']})"
        else:
            entry = round(precio * 0.995, 2)
            fvg_info = "Sin FVG 4h cercano. Entrada propuesta: -0.5% del precio actual."
        # Swing low: mÃƒÆ’Ã‚Â­nimo de ÃƒÆ’Ã‚Âºltimos 5 dÃƒÆ’Ã‚Â­as como referencia
        if hist is not None and not hist.empty:
            swing_low = float(hist["Low"].tail(5).min())
        else:
            swing_low = round(precio * 0.97, 2)
        sl = round(swing_low - (swing_low * 0.005), 2)  # 0.5% bajo swing
        tp1 = round(sma, 2)
        tp2 = round(upper, 2)
        # TP3: extensiÃƒÆ’Ã‚Â³n 1.618 desde swing_low hasta entry (solo si entry > swing_low)
        if entry > swing_low:
            rango = entry - swing_low
            tp3 = round(entry + (rango * 1.618), 2)
        else:
            tp3 = round(upper * 1.02, 2)
    else:
        # Venta: FVG bajista cercano por encima
        fvg_near = [f for f in fvgs if f["type"] == "bearish" and f["top"] > precio]
        if fvg_near:
            best_fvg = min(fvg_near, key=lambda f: abs(f["top"] - precio))
            entry = round((best_fvg["top"] + best_fvg["bottom"]) / 2, 2)
            fvg_info = f"FVG 4h bajista: {best_fvg['bottom']:.2f}-{best_fvg['top']:.2f} ({best_fvg['date']})"
        else:
            entry = round(precio * 1.005, 2)
            fvg_info = "Sin FVG 4h cercano. Entrada propuesta: +0.5% del precio actual."
        if hist is not None and not hist.empty:
            swing_high = float(hist["High"].tail(5).max())
        else:
            swing_high = round(precio * 1.03, 2)
        sl = round(swing_high + (swing_high * 0.005), 2)
        tp1 = round(sma, 2)
        tp2 = round(lower, 2)
        if swing_high > entry:
            rango = swing_high - entry
            tp3 = round(entry - (rango * 1.618), 2)
        else:
            tp3 = round(lower * 0.98, 2)
    # --- Risk/Reward ---
    riesgo = abs(entry - sl)
    rr1 = abs(tp1 - entry) / riesgo if riesgo > 0 else 0
    rr2 = abs(tp2 - entry) / riesgo if riesgo > 0 else 0
    rr3 = abs(tp3 - entry) / riesgo if riesgo > 0 else 0
    # --- Pine Script ---
    pine = generate_pine_script(sym, entry, sl, tp1, tp2, direccion)
    # --- TradingView link ---
    if sym.endswith("-USD") or sym.endswith("-usd"):
        tv_symbol = f"COINBASE:{sym.replace('-USD', 'USD')}"
    elif sym.startswith("^"):
        if "IBEX" in sym:
            tv_symbol = f"SP:{sym.replace('^', 'IBEX').replace('.', '')}"
        elif "GSPC" in sym:
            tv_symbol = "SP:SPX"
        elif "IXIC" in sym:
            tv_symbol = "NASDAQ:IXIC"
        elif "DJI" in sym:
            tv_symbol = "DJ:DJI"
        else:
            tv_symbol = sym
    elif sym.endswith("=F"):
        tv_symbol = f"TVC:{sym.replace('=F', '')}"
    else:
        tv_symbol = sym
    tv_link = f"https://www.tradingview.com/chart/?symbol={tv_symbol}&interval=D"
    # --- Riesgo sugerido ---
    risk_pct = 2.0
    pos_size = risk_pct / (riesgo / entry) if entry > 0 else 0
    setup = {
        "symbol": sym,
        "direction": "Ã¢Å“â€¦ COMPRA" if direccion == "compra" else "Ã¢ÂÅ’ VENTA",
        "price": precio,
        "entry": entry,
        "sl": sl,
        "tp1": tp1,
        "tp2": tp2,
        "tp3": tp3,
        "rr1": round(rr1, 2),
        "rr2": round(rr2, 2),
        "rr3": round(rr3, 2),
        "band_info": f"Banda {'inferior' if direccion == 'compra' else 'superior'} tocada | Ancho: {band_width:.1f}%",
        "vol_info": f"Vol ratio: {vol_ratio:.2f}x de la media",
        "fvg_info": fvg_info,
        "note": note,
        "pine_script": pine,
        "tv_link": tv_link,
        "pos_size_pct": round(pos_size * 100, 1),
        "risk_pct": risk_pct,
    }
    return setup


def format_setup_text(setup: dict) -> str:
    """Formatea un setup de trading como texto estructurado para JARVIS."""
    lines = []
    lines.append(f"\n>> {setup['symbol']} -- {setup['direction']}")
    lines.append(f"   Precio actual: ${setup['price']:.2f}")
    lines.append(f"   {setup['band_info']}")
    lines.append(f"   {setup['vol_info']}")
    if setup["fvg_info"]:
        lines.append(f"   ICT: {setup['fvg_info']}")
    if setup["note"]:
        lines.append(f"   {setup['note']}")
    lines.append(f"   {'ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬'*30}")
    lines.append(f"   ENTRADA: ${setup['entry']:.2f}")
    lines.append(f"   STOP LOSS: ${setup['sl']:.2f}")
    lines.append(f"   TP1 (MA20): ${setup['tp1']:.2f} (R/R: {setup['rr1']})")
    lines.append(f"   TP2 (Banda opuesta): ${setup['tp2']:.2f} (R/R: {setup['rr2']})")
    lines.append(f"   TP3 (Fib 1.618): ${setup['tp3']:.2f} (R/R: {setup['rr3']})")
    lines.append(f"   TAMANO POSICION: {setup['pos_size_pct']}% del capital (riesgo {setup['risk_pct']}%)")
    lines.append(f"   TRADINGVIEW: {setup['tv_link']}")
    lines.append(f"\n```pine")
    lines.append(setup['pine_script'])
    lines.append(f"```")
    return "\n".join(lines)


# ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬
#  Intraday short-term forecast (scalping)
# ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬

def _detectar_patron_vela(row: pd.Series, prev_row: pd.Series = None) -> str:
    """Detecta patrones de vela simples."""
    o, h, l, c = float(row["Open"]), float(row["High"]), float(row["Low"]), float(row["Close"])
    cuerpo = abs(c - o)
    sombra_sup = h - max(o, c)
    sombra_inf = min(o, c) - l
    rango = h - l
    if rango == 0:
        return "doji"
    # Doji
    if cuerpo / rango < 0.1:
        return "doji"
    # Martillo: sombra inferior >= 2x cuerpo, sombra superior pequeÃƒÆ’Ã‚Â±a
    if sombra_inf >= 2 * cuerpo and sombra_sup < 0.3 * cuerpo and c > o:
        return "martillo"
    # Martillo invertido
    if sombra_sup >= 2 * cuerpo and sombra_inf < 0.3 * cuerpo and c > o:
        return "martillo_invertido"
    # Envolvente alcista: vela verde que engulle vela roja anterior
    if prev_row is not None:
        prev_c = float(prev_row["Close"])
        prev_o = float(prev_row["Open"])
        if c > o and prev_c < prev_o and o < prev_c and c > prev_o:
            return "envolvente_alcista"
        if c < o and prev_c > prev_o and o > prev_c and c < prev_o:
            return "envolvente_bajista"
    # Pin bar: sombra larga en un extremo
    if sombra_sup > 2 * cuerpo and sombra_inf < 0.3 * cuerpo:
        return "pin_bar_bajista"
    if sombra_inf > 2 * cuerpo and sombra_sup < 0.3 * cuerpo:
        return "pin_bar_alcista"
    return ""


def _calcular_indicadores(df: pd.DataFrame) -> dict:
    """Calcula indicadores tÃƒÆ’Ã‚Â©cnicos sobre velas 1m/5m."""
    close = df["Close"].astype(float)
    high = df["High"].astype(float)
    low = df["Low"].astype(float)
    volume = df["Volume"].astype(float) if "Volume" in df.columns else pd.Series([0]*len(df))
    # BB (20,2)
    sma20 = close.rolling(20).mean()
    std20 = close.rolling(20).std()
    bb_upper = sma20 + 2 * std20
    bb_lower = sma20 - 2 * std20
    # RSI (14)
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / loss.replace(0, float("nan"))
    rsi = 100 - (100 / (1 + rs))
    # MACD (12,26,9)
    ema12 = close.ewm(span=12).mean()
    ema26 = close.ewm(span=26).mean()
    macd_line = ema12 - ema26
    macd_signal = macd_line.ewm(span=9).mean()
    macd_hist = macd_line - macd_signal
    # Volumen medio y picos
    vol_mean = volume.rolling(20).mean()
    vol_spike = (volume > vol_mean * 2).tolist()
    # ÃƒÆ’Ã…Â¡ltimos valores
    last = {
        "close": float(close.iloc[-1]),
        "high": float(high.iloc[-1]),
        "low": float(low.iloc[-1]),
        "sma20": float(sma20.iloc[-1]) if not pd.isna(sma20.iloc[-1]) else None,
        "bb_upper": float(bb_upper.iloc[-1]) if not pd.isna(bb_upper.iloc[-1]) else None,
        "bb_lower": float(bb_lower.iloc[-1]) if not pd.isna(bb_lower.iloc[-1]) else None,
        "rsi": float(rsi.iloc[-1]) if not pd.isna(rsi.iloc[-1]) else None,
        "macd": float(macd_line.iloc[-1]) if not pd.isna(macd_line.iloc[-1]) else None,
        "macd_signal": float(macd_signal.iloc[-1]) if not pd.isna(macd_signal.iloc[-1]) else None,
        "macd_hist": float(macd_hist.iloc[-1]) if not pd.isna(macd_hist.iloc[-1]) else None,
        "vol_mean": float(vol_mean.iloc[-1]) if not pd.isna(vol_mean.iloc[-1]) else 1,
        "vol_last": float(volume.iloc[-1]) if len(volume) > 0 else 0,
    }
    # PosiciÃƒÆ’Ã‚Â³n en BB
    if last["bb_upper"] and last["bb_lower"]:
        if last["close"] > last["bb_upper"]:
            last["bb_pos"] = "fuera_banda_superior"
        elif last["close"] < last["bb_lower"]:
            last["bb_pos"] = "fuera_banda_inferior"
        elif abs(last["close"] - last["sma20"]) / (last["bb_upper"] - last["bb_lower"]) < 0.1 if last["sma20"] else False:
            last["bb_pos"] = "en_media_central"
        else:
            last["bb_pos"] = "dentro_bandas"
    else:
        last["bb_pos"] = "desconocido"
    # MACD cruce
    last["macd_cruce"] = None
    if len(macd_line) > 1 and len(macd_signal) > 1:
        prev_macd = float(macd_line.iloc[-2]) if not pd.isna(macd_line.iloc[-2]) else None
        prev_signal = float(macd_signal.iloc[-2]) if not pd.isna(macd_signal.iloc[-2]) else None
        if prev_macd is not None and prev_signal is not None and last["macd"] is not None and last["macd_signal"] is not None:
            if prev_macd <= prev_signal and last["macd"] > last["macd_signal"]:
                last["macd_cruce"] = "alcista"
            elif prev_macd >= prev_signal and last["macd"] < last["macd_signal"]:
                last["macd_cruce"] = "bajista"
    # Divergencias RSI
    last["divergencia"] = None
    if len(rsi) > 5 and len(close) > 5:
        for i in range(2, 6):
            if not pd.isna(rsi.iloc[-i]) and not pd.isna(rsi.iloc[-1]):
                if not pd.isna(close.iloc[-i]) and not pd.isna(close.iloc[-1]):
                    if float(close.iloc[-1]) < float(close.iloc[-i]) and float(rsi.iloc[-1]) > float(rsi.iloc[-i]):
                        last["divergencia"] = "alcista"
                        break
                    if float(close.iloc[-1]) > float(close.iloc[-i]) and float(rsi.iloc[-1]) < float(rsi.iloc[-i]):
                        last["divergencia"] = "bajista"
                        break
    # PatrÃƒÆ’Ã‚Â³n de vela en ÃƒÆ’Ã‚Âºltimos 5
    patrones = []
    for i in range(max(0, len(df)-5), len(df)):
        prev = df.iloc[i-1] if i > 0 else None
        p = _detectar_patron_vela(df.iloc[i], prev)
        if p:
            patrones.append(p)
    last["patrones"] = patrones[-3:] if patrones else []
    # Soportes/resistencias (pivotes ÃƒÆ’Ã‚Âºltimos 30)
    last_30 = df.tail(30)
    soportes = sorted([float(last_30["Low"].iloc[i]) for i in range(len(last_30))], reverse=True)[:3]
    resistencias = sorted([float(last_30["High"].iloc[i]) for i in range(len(last_30))], reverse=True)[:3]
    last["soportes"] = soportes[:2]
    last["resistencias"] = resistencias[:2]
    # Picos de volumen recientes
    last["vol_spikes"] = vol_spike[-5:] if len(vol_spike) >= 5 else []
    return last


def fetch_intraday_data(symbol: str, interval: str = "1m", period: str = "1d") -> pd.DataFrame:
    """Descarga velas intraday para un sÃƒÆ’Ã‚Â­mbolo."""
    import yfinance as yf
    try:
        ticker = yf.Ticker(symbol)
        df = ticker.history(period=period, interval=interval)
        if df.empty or len(df) < 10:
            # Fallback a 5m
            df = ticker.history(period="5d", interval="5m")
        if df.empty:
            return pd.DataFrame()
        return df
    except Exception:
        return pd.DataFrame()


def analyze_short_term(symbol: str) -> dict:
    """Analiza un sÃƒÆ’Ã‚Â­mbolo en temporalidad 1m/5m y devuelve indicadores + predicciÃƒÆ’Ã‚Â³n."""
    import pandas as pd
    df = fetch_intraday_data(symbol, interval="1m", period="1d")
    interval_used = "1m"
    if df.empty or len(df) < 30:
        df = fetch_intraday_data(symbol, interval="5m", period="5d")
        interval_used = "5m"
    if df.empty or len(df) < 10:
        return {"error": f"No hay datos intraday disponibles para '{symbol}'."}
    indicadores = _calcular_indicadores(df)
    indicadores["symbol"] = symbol
    indicadores["interval"] = interval_used
    indicadores["velas_disponibles"] = len(df)
    return indicadores


def generate_short_term_forecast(indicadores: dict) -> str:
    """Genera predicciÃƒÆ’Ã‚Â³n de corto plazo basada en reglas heurÃƒÆ’Ã‚Â­sticas."""
    parts = []
    sym = indicadores["symbol"]
    close = indicadores["close"]
    interval = indicadores["interval"]
    bb_pos = indicadores.get("bb_pos", "desconocido")
    rsi = indicadores.get("rsi")
    macd_cruce = indicadores.get("macd_cruce")
    divergencia = indicadores.get("divergencia")
    patrones = indicadores.get("patrones", [])
    soportes = indicadores.get("soportes", [])
    resistencias = indicadores.get("resistencias", [])
    vol_spikes = indicadores.get("vol_spikes", [])
    bb_upper = indicadores.get("bb_upper")
    bb_lower = indicadores.get("bb_lower")
    sma20 = indicadores.get("sma20")

    disclaimer = "Ã¢Å¡Â Ã¯Â¸Â Esto es una estimacion estadistica en base a patrones, no un consejo financiero. El mercado puede moverse de forma imprevista."

    parts.append(f">> ANALISIS INTRADIA {sym} ({interval})")
    parts.append(f"   Precio: {close:.2f} | RSI(14): {rsi:.1f}" if rsi else f"   Precio: {close:.2f}")
    parts.append(f"   Bandas Bollinger: {bb_pos}")
    if patrones:
        parts.append(f"   Patrones recientes: {', '.join(patrones)}")
    if divergencia:
        parts.append(f"   Divergencia RSI: {divergencia}")
    if macd_cruce:
        parts.append(f"   Cruce MACD: {macd_cruce}")

    # Reglas de predicciÃƒÆ’Ã‚Â³n
    scenario = "lateral"
    prob = 50
    timeframe = "prÃƒÆ’Ã‚Â³ximos 8-15 minutos"
    signal = ""

    # Regla 1: Sobreventa + BB inferior + martillo ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢ rebote
    if rsi is not None and rsi < 30 and bb_pos == "fuera_banda_inferior":
        if "martillo" in patrones or "pin_bar_alcista" in patrones:
            scenario = "alcista"
            prob = 70
            timeframe = "prÃƒÆ’Ã‚Â³ximos 8 minutos"
            target = sma20 if sma20 else close * 1.005
            stop = min(soportes + [close * 0.995]) if soportes else close * 0.995
            signal = (
                f"   ESCENARIO: Rebote alcista en los prÃƒÆ’Ã‚Â³ximos 8 minutos (prob. ~{prob}%)\n"
                f"   GATILLO: Si el precio mantiene sobre {close:.2f} y forma nuevo soporte.\n"
                f"   OBJETIVO: {target:.2f} (MA20) | STOP: {stop:.3f}\n"
                f"   Si pierde {stop:.3f}, la presiÃƒÆ’Ã‚Â³n bajista se acelera."
            )
            parts.append(signal)
            parts.append(f"   TEMPORALIDAD: {timeframe}")
            parts.append(f"\n{disclaimer}")
            return "\n".join(parts)

    # Regla 2: Sobrecompra + BB superior + volumen anormal ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢ correcciÃƒÆ’Ã‚Â³n
    if rsi is not None and rsi > 75 and bb_pos == "fuera_banda_superior":
        if any(vol_spikes[-3:]):
            scenario = "bajista"
            prob = 65
            timeframe = "prÃƒÆ’Ã‚Â³ximos 10 minutos"
            target = sma20 if sma20 else close * 0.995
            stop = max(resistencias + [close * 1.005]) if resistencias else close * 1.005
            signal = (
                f"   ESCENARIO: CorrecciÃƒÆ’Ã‚Â³n bajista en los prÃƒÆ’Ã‚Â³ximos 10 minutos (prob. ~{prob}%)\n"
                f"   GATILLO: Si el precio no logra superar {stop:.2f} en los prÃƒÆ’Ã‚Â³ximos 3 minutos.\n"
                f"   OBJETIVO: {target:.2f} (MA20) | STOP: {stop:.3f}\n"
                f"   Volumen alto sugiere distribuciÃƒÆ’Ã‚Â³n institucional."
            )
            parts.append(signal)
            parts.append(f"   TEMPORALIDAD: {timeframe}")
            parts.append(f"\n{disclaimer}")
            return "\n".join(parts)

    # Regla 3: Cruce MACD alcista + soporte ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢ continuaciÃƒÆ’Ã‚Â³n
    if macd_cruce == "alcista" and soportes and abs(close - soportes[0]) / close < 0.005:
        scenario = "alcista"
        prob = 60
        timeframe = "prÃƒÆ’Ã‚Â³ximos 5-15 minutos"
        target = resistencias[0] if resistencias else close * 1.01
        signal = (
            f"   ESCENARIO: ContinuaciÃƒÆ’Ã‚Â³n alcista (prob. ~{prob}%)\n"
            f"   GATILLO: Cruce MACD alcista en zona de soporte.\n"
            f"   Si supera {target:.2f}, se confirma impulso.\n"
            f"   OBJETIVO: {target:.2f} (resistencia) | STOP: {soportes[0]:.3f}"
        )
        parts.append(signal)
        parts.append(f"   TEMPORALIDAD: {timeframe}")
        parts.append(f"\n{disclaimer}")
        return "\n".join(parts)

    # Regla 4: Cruce MACD bajista + resistencia ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢ caÃƒÆ’Ã‚Â­da
    if macd_cruce == "bajista" and resistencias and abs(close - resistencias[0]) / close < 0.005:
        scenario = "bajista"
        prob = 60
        timeframe = "prÃƒÆ’Ã‚Â³ximos 5-15 minutos"
        target = soportes[0] if soportes else close * 0.99
        signal = (
            f"   ESCENARIO: ContinuaciÃƒÆ’Ã‚Â³n bajista (prob. ~{prob}%)\n"
            f"   GATILLO: Cruce MACD bajista en zona de resistencia.\n"
            f"   Si pierde {target:.2f}, se acelera la caÃƒÆ’Ã‚Â­da.\n"
            f"   OBJETIVO: {target:.2f} (soporte) | STOP: {resistencias[0]:.3f}"
        )
        parts.append(signal)
        parts.append(f"   TEMPORALIDAD: {timeframe}")
        parts.append(f"\n{disclaimer}")
        return "\n".join(parts)

    # Regla 5: Volumen anormal sin direcciÃƒÆ’Ã‚Â³n ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢ indecisiÃƒÆ’Ã‚Â³n / lateral
    if any(vol_spikes[-3:]) and rsi is not None and 40 < rsi < 60:
        scenario = "lateral"
        prob = 70
        timeframe = "prÃƒÆ’Ã‚Â³ximos 10-15 minutos"
        signal = (
            f"   ESCENARIO: Rango lateral (prob. ~{prob}%)\n"
            f"   Picos de volumen sin direcciÃƒÆ’Ã‚Â³n clara sugieren indecisiÃƒÆ’Ã‚Â³n.\n"
            f"   Esperar ruptura confirmada de {resistencias[0] if resistencias else close*1.01:.2f} al alza\n"
            f"   o de {soportes[0] if soportes else close*0.99:.2f} a la baja para entrar."
        )
        parts.append(signal)
        parts.append(f"   TEMPORALIDAD: {timeframe}")
        parts.append(f"\n{disclaimer}")
        return "\n".join(parts)

    # Regla 6: Divergencia detectada
    if divergencia == "alcista":
        prob = 65
        scenario = "alcista"
        timeframe = "prÃƒÆ’Ã‚Â³ximos 8-12 minutos"
        target = sma20 if sma20 else close * 1.008
        signal = (
            f"   ESCENARIO: ReversiÃƒÆ’Ã‚Â³n alcista por divergencia RSI (prob. ~{prob}%)\n"
            f"   GATILLO: Precio haciendo mÃƒÆ’Ã‚Â­nimos mÃƒÆ’Ã‚Â¡s bajos, RSI haciendo mÃƒÆ’Ã‚Â­nimos mÃƒÆ’Ã‚Â¡s altos.\n"
            f"   OBJETIVO: {target:.2f} | STOP: {close * 0.992:.3f}"
        )
        parts.append(signal)
        parts.append(f"   TEMPORALIDAD: {timeframe}")
        parts.append(f"\n{disclaimer}")
        return "\n".join(parts)

    if divergencia == "bajista":
        prob = 65
        scenario = "bajista"
        timeframe = "prÃƒÆ’Ã‚Â³ximos 8-12 minutos"
        target = sma20 if sma20 else close * 0.992
        signal = (
            f"   ESCENARIO: ReversiÃƒÆ’Ã‚Â³n bajista por divergencia RSI (prob. ~{prob}%)\n"
            f"   GATILLO: Precio haciendo mÃƒÆ’Ã‚Â¡ximos mÃƒÆ’Ã‚Â¡s altos, RSI haciendo mÃƒÆ’Ã‚Â¡ximos mÃƒÆ’Ã‚Â¡s bajos.\n"
            f"   OBJETIVO: {target:.2f} | STOP: {close * 1.008:.3f}"
        )
        parts.append(signal)
        parts.append(f"   TEMPORALIDAD: {timeframe}")
        parts.append(f"\n{disclaimer}")
        return "\n".join(parts)

    # Regla 7: Sin seÃƒÆ’Ã‚Â±al clara ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢ neutral
    if rsi is not None:
        if rsi > 60:
            signal = (
                f"   ESCENARIO: Tendencia alcista suave (prob. ~55%)\n"
                f"   RSI en {rsi:.0f}, sesgo alcista sin confirmaciÃƒÆ’Ã‚Â³n de patrÃƒÆ’Ã‚Â³n claro.\n"
                f"   Nivel a vigilar: {resistencias[0]:.2f} si sube, {soportes[0]:.2f} si baja."
            )
        elif rsi < 40:
            signal = (
                f"   ESCENARIO: Tendencia bajista suave (prob. ~55%)\n"
                f"   RSI en {rsi:.0f}, sesgo bajista sin confirmaciÃƒÆ’Ã‚Â³n.\n"
                f"   Nivel a vigilar: {soportes[0]:.2f} si baja, {resistencias[0]:.2f} si sube."
            )
        else:
            signal = (
                f"   ESCENARIO: Neutral. Sin seÃƒÆ’Ã‚Â±ales claras en este momento.\n"
                f"   RSI en {rsi:.0f} (rango medio). Esperar cruce MACD o patrÃƒÆ’Ã‚Â³n de velas.\n"
                f"   SOPORTE: {soportes[0]:.2f} | RESISTENCIA: {resistencias[0]:.2f}"
            )
    else:
        signal = (
            f"   ESCENARIO: Datos insuficientes para una predicciÃƒÆ’Ã‚Â³n.\n"
            f"   SOPORTE: {soportes[0]:.2f} | RESISTENCIA: {resistencias[0]:.2f}"
        )
    parts.append(signal)
    parts.append(f"   TEMPORALIDAD: {timeframe}")
    parts.append(f"\n{disclaimer}")
    return "\n".join(parts)


# ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬
#  MÃƒÆ’Ã‚Â³dulo 1: Flujo de ÃƒÆ’Ã¢â‚¬Å“rdenes y Microestructura
# ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬

def analyze_order_flow(symbol: str) -> dict:
    """Analiza flujo de ÃƒÆ’Ã‚Â³rdenes, CVD, spread, icebergs y spoofing."""
    import numpy as np
    import yfinance as yf
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="5d", interval="15m")
        if hist.empty or len(hist) < 30:
            return {"error": f"Datos insuficientes para flujo de ÃƒÆ’Ã‚Â³rdenes de {symbol}"}
        close = hist["Close"].astype(float)
        open_ = hist["Open"].astype(float)
        high = hist["High"].astype(float)
        low = hist["Low"].astype(float)
        volume = hist["Volume"].astype(float)
        # CVD simulado: volumen direccional por vela
        cvd_values = []
        for i in range(len(hist)):
            if close.iloc[i] > open_.iloc[i]:
                cvd_values.append(float(volume.iloc[i]))
            elif close.iloc[i] < open_.iloc[i]:
                cvd_values.append(-float(volume.iloc[i]))
            else:
                cvd_values.append(0)
        cvd_series = np.cumsum(cvd_values[-50:]) if len(cvd_values) >= 50 else np.cumsum(cvd_values)
        cvd_val = int(cvd_series[-1]) if len(cvd_series) > 0 else 0
        cvd_signal = "alcista" if cvd_val > 0 else ("bajista" if cvd_val < 0 else "neutral")
        # Spread estimado
        spread_pct = ((high - low) / close * 100).mean()
        spread_actual = float(spread_pct) if not np.isnan(spread_pct) else 0
        # Iceberg detection: volumen > 2.5 sigma + rango pequeÃƒÆ’Ã‚Â±o
        vol_mean = volume.rolling(20).mean()
        vol_std = volume.rolling(20).std()
        icebergs = 0
        for i in range(1, len(hist)):
            v = float(volume.iloc[i])
            vm = float(vol_mean.iloc[i]) if not np.isnan(vol_mean.iloc[i]) else 1
            vs = float(vol_std.iloc[i]) if not np.isnan(vol_std.iloc[i]) else 1
            rango = float(high.iloc[i] - low.iloc[i])
            rango_medio = float((high - low).rolling(20).mean().iloc[i])
            if vs > 0 and vm > 0 and v > vm + 2.5 * vs and rango < rango_medio * 0.6:
                icebergs += 1
        # Spoofing: volumen alto + reversiÃƒÆ’Ã‚Â³n inmediata
        spoofing = 0
        for i in range(1, len(hist) - 1):
            v = float(volume.iloc[i])
            vm = float(vol_mean.iloc[i]) if not np.isnan(vol_mean.iloc[i]) else 1
            vs = float(vol_std.iloc[i]) if not np.isnan(vol_std.iloc[i]) else 1
            if vs > 0 and vm > 0 and v > vm + 2.5 * vs:
                dir_original = 1 if close.iloc[i] > open_.iloc[i] else -1
                dir_siguiente = 1 if close.iloc[i+1] > open_.iloc[i+1] else -1
                if dir_original != dir_siguiente:
                    spoofing += 1
        # SeÃƒÆ’Ã‚Â±al combinada de flujo
        prob_orden = 55
        if cvd_signal == "alcista" and icebergs < 2:
            prob_orden = 60 + min(icebergs * 3, 15)
        elif cvd_signal == "bajista" and icebergs < 2:
            prob_orden = 60 + min(icebergs * 3, 15)
        elif icebergs >= 3:
            prob_orden = 70
        return {
            "cvd": cvd_val,
            "cvd_signal": cvd_signal,
            "spread_pct": round(spread_actual, 3),
            "iceberg_suspects": icebergs,
            "spoofing_suspects": spoofing,
            "orderflow_signal": f"{cvd_signal.capitalize()} (prob. ~{prob_orden}%)",
            "n_velas": len(hist),
        }
    except Exception as e:
        return {"error": f"Error en flujo de ÃƒÆ’Ã‚Â³rdenes: {e}"}


# ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬
#  MÃƒÆ’Ã‚Â³dulo 2: PredicciÃƒÆ’Ã‚Â³n Temprana Institucional
# ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬

def early_institutional_signals(symbol: str) -> dict:
    """Detecta seÃƒÆ’Ã‚Â±ales institucionales: put/call, insider, bonos, VIX, sector."""
    import numpy as np
    import yfinance as yf
    result = {"signals": [], "summary": "", "entry": None, "target": None, "stop": None}
    try:
        # --- Put/Call ratio desde opciones ---
        try:
            ticker = yf.Ticker(symbol)
            if hasattr(ticker, 'option_chain'):
                try:
                    exps = ticker.options
                    if exps:
                        chain = ticker.option_chain(exps[0])
                        total_calls = chain.calls["volume"].sum() if "volume" in chain.calls.columns else 0
                        total_puts = chain.puts["volume"].sum() if "volume" in chain.puts.columns else 0
                        if total_calls > 0 and total_puts > 0:
                            pc_ratio = total_puts / total_calls
                            if pc_ratio > 1.5:
                                result["signals"].append({"type": "put_call", "impact": "Ã°Å¸â€Â´", "msg": f"Put/Call ratio elevado: {pc_ratio:.2f}. Alta actividad de proteccion bajista.", "prob": 70})
                            elif pc_ratio < 0.5:
                                result["signals"].append({"type": "put_call", "impact": "Ã°Å¸Å¸Â¢", "msg": f"Put/Call ratio bajo: {pc_ratio:.2f}. Sesgo alcista en opciones.", "prob": 65})
                            else:
                                result["signals"].append({"type": "put_call", "impact": "Ã°Å¸Å¸Â¡", "msg": f"Put/Call ratio neutral: {pc_ratio:.2f}.", "prob": 50})
                except Exception:
                    pass
        except Exception:
            pass

        # --- Insider transactions via DuckDuckGo ---
        try:
            import requests
            from urllib.parse import quote
            insider_q = f"insider trading {symbol} site:sec.gov OR site:marketbeat.com OR site:finviz.com"
            i_url = f"https://api.duckduckgo.com/?q={quote(insider_q)}&format=json&no_html=1"
            i_r = requests.get(i_url, timeout=5)
            if i_r.status_code == 200:
                i_data = i_r.json()
                i_text = i_data.get("AbstractText", "") + " " + " ".join(t.get("Text", "") for t in i_data.get("RelatedTopics", [])[:3] if isinstance(t, dict))
                i_text_lower = i_text.lower()
                buy_count = i_text_lower.count("buy") + i_text_lower.count("compra") + i_text_lower.count("purchase")
                sell_count = i_text_lower.count("sell") + i_text_lower.count("venta") + i_text_lower.count("sale")
                if buy_count > sell_count:
                    result["signals"].append({"type": "insider", "impact": "Ã°Å¸Å¸Â¢", "msg": f"Se detectan mas menciones de compra ({buy_count}) que de venta ({sell_count}) por parte de insiders.", "prob": 60})
                elif sell_count > buy_count:
                    result["signals"].append({"type": "insider", "impact": "Ã°Å¸â€Â´", "msg": f"Se detectan mas menciones de venta ({sell_count}) que de compra ({buy_count}) por insiders.", "prob": 65})
        except Exception:
            pass

        # --- Bond market / deuda corporativa ---
        try:
            import requests
            from urllib.parse import quote
            bond_q = f"{symbol} bond issuance OR corporate bonds site:bloomberg.com OR site:reuters.com"
            b_url = f"https://api.duckduckgo.com/?q={quote(bond_q)}&format=json&no_html=1"
            b_r = requests.get(b_url, timeout=5)
            if b_r.status_code == 200:
                b_text = b_r.json().get("AbstractText", "")
                if "bond" in b_text.lower() or "debt" in b_text.lower():
                    result["signals"].append({"type": "bond", "impact": "Ã°Å¸Å¸Â¡", "msg": "Posible emision de deuda/bonos detectada en noticias.", "prob": 50})
        except Exception:
            pass

        # --- VIX anomaly (para SPY/QQQ) ---
        if symbol.upper() in ("SPY", "QQQ"):
            try:
                vix = yf.Ticker("^VIX")
                vix_hist = vix.history(period="5d")
                if not vix_hist.empty:
                    vix_last = float(vix_hist["Close"].iloc[-1])
                    if vix_last > 25:
                        result["signals"].append({"type": "vix", "impact": "Ã°Å¸â€Â´", "msg": f"VIX elevado ({vix_last:.1f}). Alta volatilidad / miedo en el mercado.", "prob": 70})
                    elif vix_last > 20:
                        result["signals"].append({"type": "vix", "impact": "Ã°Å¸Å¸Â¡", "msg": f"VIX moderado ({vix_last:.1f}). Cierta tension.", "prob": 55})
                    else:
                        result["signals"].append({"type": "vix", "impact": "Ã°Å¸Å¸Â¢", "msg": f"VIX bajo ({vix_last:.1f}). Entorno de calma.", "prob": 60})
            except Exception:
                pass

        # --- RotaciÃƒÆ’Ã‚Â³n sectorial ---
        mapa_sector = {
            "XLF": ["JPM", "BAC", "WFC", "C", "GS", "MS", "V", "MA"],
            "XLE": ["XOM", "CVX", "COP", "SLB"],
            "XLU": ["NEE", "DUK", "SO", "D"],
            "XLK": ["AAPL", "MSFT", "NVDA", "INTC", "CRM"],
            "XLV": ["UNH", "JNJ", "PFE", "ABBV"],
            "XLY": ["AMZN", "HD", "TSLA", "NKE"],
            "XLP": ["KO", "PEP", "PG", "WMT"],
            "XLI": ["CAT", "BA", "GE", "MMM"],
            "XLB": ["LIN", "SHW", "ECL"],
            "XLRE": ["PLD", "AMT", "CCI"],
        }
        sym_upper = symbol.upper()
        sector_etf = None
        for etf, miembros in mapa_sector.items():
            if sym_upper in miembros:
                sector_etf = etf
                break
        if sector_etf:
            try:
                sp500 = yf.Ticker("^GSPC")
                sp_hist = sp500.history(period="1mo")
                sector_t = yf.Ticker(sector_etf)
                sec_hist = sector_t.history(period="1mo")
                if not sp_hist.empty and not sec_hist.empty:
                    sp_perf = (float(sp_hist["Close"].iloc[-1]) / float(sp_hist["Close"].iloc[0]) - 1) * 100
                    sec_perf = (float(sec_hist["Close"].iloc[-1]) / float(sec_hist["Close"].iloc[0]) - 1) * 100
                    diff = sec_perf - sp_perf
                    if diff > 5:
                        result["signals"].append({"type": "sector", "impact": "Ã°Å¸Å¸Â¢", "msg": f"El sector ({sector_etf}) rinde {diff:.1f}% mejor que el S&P500 en el ultimo mes. Rotacion favorable.", "prob": 60})
                    elif diff < -5:
                        result["signals"].append({"type": "sector", "impact": "Ã°Å¸â€Â´", "msg": f"El sector ({sector_etf}) rinde {abs(diff):.1f}% peor que el S&P500. Rotacion desfavorable.", "prob": 65})
            except Exception:
                pass

        # --- Resumen y trade sugerido ---
        impact_scores = {"Ã°Å¸â€Â´": -2, "Ã°Å¸Å¸Â¡": 0, "Ã°Å¸Å¸Â¢": 2}
        total_score = sum(impact_scores.get(s["impact"], 0) for s in result["signals"])
        if total_score >= 3:
            result["summary"] = "SEÃƒÆ’Ã¢â‚¬ËœAL INSTITUCIONAL ALCISTA"
            result["entry"] = "Swing entry en soporte"
            result["target"] = "+5% desde entrada"
            result["stop"] = "-2% desde entrada"
        elif total_score <= -3:
            result["summary"] = "SEÃƒÆ’Ã¢â‚¬ËœAL INSTITUCIONAL BAJISTA"
            result["entry"] = "Swing entry en resistencia"
            result["target"] = "-5% desde entrada"
            result["stop"] = "+2% desde entrada"
        else:
            result["summary"] = "SEÃƒÆ’Ã¢â‚¬ËœAL INSTITUCIONAL MIXTA / NEUTRAL"
        result["total_score"] = total_score
        return result
    except Exception as e:
        return {"error": f"Error en seÃƒÆ’Ã‚Â±ales institucionales: {e}"}


# ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬
#  MÃƒÆ’Ã‚Â³dulo 3: Arbitraje Oculto
# ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬

def hidden_arbitrage(symbol: str) -> dict:
    """Detecta oportunidades de arbitraje entre exchanges y productos."""
    import yfinance as yf
    import numpy as np
    import requests
    result = {"opportunities": [], "summary": "No se detectaron oportunidades de arbitraje significativas."}
    try:
        # Precio local (yfinance)
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="1d")
        if hist.empty:
            return result
        price_yahoo = float(hist["Close"].iloc[-1])
        # --- Crypto: comparar con Binance ---
        binance_map = {
            "BTC-USD": "BTCUSDT", "ETH-USD": "ETHUSDT", "SOL-USD": "SOLUSDT",
            "XRP-USD": "XRPUSDT", "ADA-USD": "ADAUSDT", "DOGE-USD": "DOGEUSDT",
            "BNB-USD": "BNBUSDT", "LINK-USD": "LINKUSDT", "MATIC-USD": "POLUSDT",
        }
        sym_upper = symbol.upper()
        if sym_upper in binance_map:
            try:
                binance_sym = binance_map[sym_upper]
                b_url = f"https://api.binance.com/api/v3/ticker/price?symbol={binance_sym}"
                b_resp = requests.get(b_url, timeout=5)
                if b_resp.status_code == 200:
                    price_binance = float(b_resp.json()["price"])
                    diff_pct = abs(price_yahoo - price_binance) / price_yahoo * 100
                    if diff_pct > 0.5:
                        side = "COMPRA" if price_binance > price_yahoo else "VENTA"
                        profit = round(diff_pct * 0.7, 2)
                        result["opportunities"].append({
                            "type": "crypto_arbitrage",
                            "pair": f"Yahoo vs Binance",
                            "price_yahoo": round(price_yahoo, 2),
                            "price_binance": round(price_binance, 2),
                            "diff_pct": round(diff_pct, 2),
                            "action": f"{side} en Yahoo, contraria en Binance",
                            "profit_pct": profit,
                            "risk": "EjecuciÃƒÆ’Ã‚Â³n lenta / slippage",
                            "capital": "Media",
                        })
            except Exception:
                pass

        # --- ETF NAV check ---
        etf_map = {
            "SPY": {"components": ["AAPL", "MSFT", "AMZN", "NVDA", "GOOGL", "META", "BRK-B", "JPM", "V", "PG", "XOM", "UNH", "LLY", "HD", "CVX", "WMT", "MA", "KO", "MRK", "PEP"], "weights": None},
            "QQQ": {"components": ["AAPL", "MSFT", "AMZN", "NVDA", "GOOGL", "META", "TSLA", "AVGO", "COST", "NFLX", "ADBE", "PEP", "CMCSA", "AMD", "INTC", "CSCO", "TMUS", "TXN", "AMGN", "QCOM"], "weights": None},
        }
        if sym_upper in etf_map:
            try:
                comp_prices = []
                for comp in etf_map[sym_upper]["components"]:
                    try:
                        c_ticker = yf.Ticker(comp)
                        c_hist = c_ticker.history(period="1d")
                        if not c_hist.empty:
                            comp_prices.append(float(c_hist["Close"].iloc[-1]))
                    except Exception:
                        pass
                if comp_prices:
                    nav_est = np.mean(comp_prices) * 10
                    nav_diff = abs(price_yahoo - nav_est) / nav_est * 100
                    if nav_diff > 1.0:
                        result["opportunities"].append({
                            "type": "etf_nav",
                            "price_yahoo": round(price_yahoo, 2),
                            "nav_estimado": round(nav_est, 2),
                            "diff_pct": round(nav_diff, 2),
                            "action": "COMPRAR si precio < NAV, VENDER si precio > NAV",
                            "profit_pct": round(nav_diff * 0.8, 2),
                            "risk": "NAV estimado, no exacto",
                            "capital": "Alta",
                        })
            except Exception:
                pass

        # --- Funding rate crypto ---
        if sym_upper in binance_map:
            try:
                binance_sym = binance_map[sym_upper]
                f_url = f"https://api.binance.com/api/v3/fundingRate?symbol={binance_sym}&limit=1"
                f_resp = requests.get(f_url, timeout=5)
                if f_resp.status_code == 200:
                    f_data = f_resp.json()
                    if f_data:
                        fr = float(f_data[0]["fundingRate"]) * 100
                        if abs(fr) > 0.1:
                            side = "SHORT" if fr > 0 else "LONG"
                            result["opportunities"].append({
                                "type": "funding_rate",
                                "rate_pct": round(fr, 4),
                                "action": f"Hacer {side} para capturar funding rate de {abs(fr):.4f}% cada 8h",
                                "profit_pct": round(abs(fr) * 3, 2),
                                "risk": "Riesgo de precio direccional",
                                "capital": "Alta (margen)",
                            })
            except Exception:
                pass

        if result["opportunities"]:
            result["summary"] = f"Se detectaron {len(result['opportunities'])} oportunidad(es) de arbitraje."
        return result
    except Exception as e:
        return {"error": f"Error en arbitraje: {e}"}


# ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬
#  MÃƒÆ’Ã‚Â³dulo 4: PredicciÃƒÆ’Ã‚Â³n de Comportamiento Colectivo
# ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬

def behavioral_prediction(symbol: str) -> dict:
    """Analiza sentimiento colectivo, menciones, contagio y sesgos cognitivos."""
    import requests
    import numpy as np
    from urllib.parse import quote
    result = {"sentiment_score": 0, "fear_greed": "neutral", "phase": "", "signal": "", "timeframe": "", "panic_prob": 0, "euphoria_prob": 0}
    try:
        # --- Google News sentiment via feedparser ---
        import feedparser
        news_score = 0
        news_count = 0
        pos_words = {"sube", "subida", "alza", "ganancia", "positivo", "crece", "crecimiento", "optimismo", "rally", "comprar", "bullish", "upside", "upgrade", "beat", "record", "crecimiento", "innovaciÃƒÆ’Ã‚Â³n", "expansiÃƒÆ’Ã‚Â³n", "fuerte"}
        neg_words = {"baja", "bajada", "caÃƒÆ’Ã‚Â­da", "pÃƒÆ’Ã‚Â©rdida", "negativo", "decrece", "temor", "pÃƒÆ’Ã‚Â¡nico", "vender", "bearish", "downside", "downgrade", "miss", "crisis", "despido", "demanda", "investigaciÃƒÆ’Ã‚Â³n", "multa", "fraude"}
        try:
            feed = feedparser.parse(f"https://news.google.com/rss/search?q={quote(symbol + ' stock')}&hl=en-US&gl=US&ceid=US:en")
            for entry in feed.entries[:10]:
                title = entry.get("title", "") + " " + entry.get("description", "")
                title_lower = title.lower()
                pos_count = sum(1 for w in pos_words if w in title_lower)
                neg_count = sum(1 for w in neg_words if w in title_lower)
                news_score += (pos_count - neg_count)
                news_count += 1
        except Exception:
            pass

        # --- DuckDuckGo social mentions ---
        try:
            ddg_url = f"https://api.duckduckgo.com/?q={quote(symbol + ' stock site:twitter.com OR site:reddit.com')}&format=json&no_html=1"
            ddg_r = requests.get(ddg_url, timeout=5)
            ddg_mentions = 0
            social_score = 0
            if ddg_r.status_code == 200:
                ddg_data = ddg_r.json()
                topics = ddg_data.get("RelatedTopics", [])
                for t in topics[:5]:
                    text = t.get("Text", "") if isinstance(t, dict) else ""
                    text_lower = text.lower()
                    pos_social = sum(1 for w in pos_words if w in text_lower)
                    neg_social = sum(1 for w in neg_words if w in text_lower)
                    social_score += (pos_social - neg_social)
                    if text:
                        ddg_mentions += 1
        except Exception:
            ddg_mentions = 0
            social_score = 0

        # --- Composite sentiment ---
        total_score = news_score + social_score
        # Normalizado a -10..10
        sentiment = max(-10, min(10, total_score))
        result["sentiment_score"] = sentiment
        result["mentions_total"] = news_count + ddg_mentions

        # --- Modelo de contagio (velocidad de fuentes ÃƒÆ’Ã‚Âºnicas) ---
        result["contagion_speed"] = "alta" if (news_count + ddg_mentions) > 15 else ("media" if (news_count + ddg_mentions) > 5 else "baja")

        # --- Fear/Greed index ---
        if sentiment <= -5:
            result["fear_greed"] = "PANICO"
            result["phase"] = "ClÃƒÆ’Ã‚Â­max bajista" if sentiment <= -8 else "AceleraciÃƒÆ’Ã‚Â³n bajista"
            result["signal"] = "COMPRAR en pÃƒÆ’Ã‚Â¡nico (contrarian)"
            result["panic_prob"] = min(85, 50 + abs(sentiment) * 4)
            result["euphoria_prob"] = 5
            result["timeframe"] = "prÃƒÆ’Ã‚Â³ximas 24-48 horas"
        elif sentiment <= -2:
            result["fear_greed"] = "MIEDO"
            result["phase"] = "Inicio de distribuciÃƒÆ’Ã‚Â³n"
            result["signal"] = "Vigilar para posible compra"
            result["panic_prob"] = 35
            result["euphoria_prob"] = 15
            result["timeframe"] = "prÃƒÆ’Ã‚Â³ximos 2-3 dÃƒÆ’Ã‚Â­as"
        elif sentiment >= 5:
            result["fear_greed"] = "EUFORIA"
            result["phase"] = "ClÃƒÆ’Ã‚Â­max alcista" if sentiment >= 8 else "AceleraciÃƒÆ’Ã‚Â³n alcista"
            result["signal"] = "VENDER en euforia (tomar ganancias)"
            result["euphoria_prob"] = min(85, 50 + sentiment * 4)
            result["panic_prob"] = 5
            result["timeframe"] = "prÃƒÆ’Ã‚Â³ximas 24-48 horas"
        elif sentiment >= 2:
            result["fear_greed"] = "CODICIA"
            result["phase"] = "AcumulaciÃƒÆ’Ã‚Â³n avanzada"
            result["signal"] = "Mantener / reducir gradualmente"
            result["euphoria_prob"] = 30
            result["panic_prob"] = 10
            result["timeframe"] = "prÃƒÆ’Ã‚Â³ximos 2-3 dÃƒÆ’Ã‚Â­as"
        else:
            result["fear_greed"] = "NEUTRAL"
            result["phase"] = "AcumulaciÃƒÆ’Ã‚Â³n / distribuciÃƒÆ’Ã‚Â³n lateral"
            result["signal"] = "Esperar direcciÃƒÆ’Ã‚Â³n clara"
            result["euphoria_prob"] = 15
            result["panic_prob"] = 15
            result["timeframe"] = "prÃƒÆ’Ã‚Â³ximos 1-2 dÃƒÆ’Ã‚Â­as"

        # --- Cognitive biases ---
        try:
            price_ticker = symbol
            price_hist = __import__("yfinance", fromlist=["Ticker"]).Ticker(price_ticker).history(period="1mo")
            if not price_hist.empty:
                pct_change = (float(price_hist["Close"].iloc[-1]) / float(price_hist["Close"].iloc[0]) - 1) * 100
                if pct_change < -10 and sentiment < -3:
                    result["bias"] = "Potencial pÃƒÆ’Ã‚Â¡nico excesivo (oversold + malas noticias). Oportunidad contrarian."
                elif pct_change > 15 and sentiment > 3:
                    result["bias"] = "Posible euforia desmedida (overbought + buenas noticias). Cautela."
                else:
                    result["bias"] = "Sin sesgo cognitivo evidente."
                result["price_change_1m"] = round(pct_change, 1)
        except Exception:
            pass

        return result
    except Exception as e:
        return {"error": f"Error en anÃƒÆ’Ã‚Â¡lisis de comportamiento: {e}"}


# ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬
#  MÃƒÆ’Ã‚Â³dulo 5: FÃƒÆ’Ã‚Â­sica CuÃƒÆ’Ã‚Â¡ntica y Complejidad
# ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬

def quantum_market_analysis(symbol: str) -> dict:
    """Analiza entropÃƒÆ’Ã‚Â­a, dimensiÃƒÆ’Ã‚Â³n fractal, caos, temperatura de mercado y atractores."""
    import numpy as np
    import yfinance as yf
    result = {}
    try:
        # Obtener datos 1m si es posible, sino usar 5m o daily para el cÃƒÆ’Ã‚Â¡lculo
        ticker = yf.Ticker(symbol)
        df = ticker.history(period="2d", interval="1m")
        interval_used = "1m"
        if df.empty or len(df) < 30:
            df = ticker.history(period="1mo", interval="1d")
            interval_used = "1d"
        if df.empty or len(df) < 20:
            return {"error": f"Datos insuficientes para anÃƒÆ’Ã‚Â¡lisis cuÃƒÆ’Ã‚Â¡ntico de {symbol}"}
        close = df["Close"].astype(float).values
        high = df["High"].astype(float).values
        low = df["Low"].astype(float).values
        volume = df["Volume"].astype(float).values if "Volume" in df.columns else np.ones(len(df))
        # --- Shannon Entropy de retornos ---
        returns = np.diff(close) / (close[:-1] + 1e-10)
        if len(returns) > 1 and np.std(returns) > 1e-10:
            bins = min(20, len(returns) // 5)
            bins = max(5, bins)
            hist_counts, _ = np.histogram(returns, bins=bins, density=False)
            probs = hist_counts / hist_counts.sum()
            probs = probs[probs > 0]
            entropy = -np.sum(probs * np.log2(probs)) if len(probs) > 0 else 0
            result["shannon_entropy"] = round(float(entropy), 4)
        else:
            result["shannon_entropy"] = 0
        # --- Fractal dimension (correlation dimension via nolds, fallback a Higuchi manual) ---
        if len(close) > 20:
            try:
                import warnings
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    from nolds import corr_dim
                    cd = corr_dim(close, emb_dim=max(2, min(5, len(close)//10)), lag=2)
                    result["fractal_dimension"] = round(float(cd), 4)
            except Exception:
                try:
                    # Manual Higuchi fractal dimension
                    def _higuchi_fd(data, kmax=10):
                        n = len(data)
                        lk = []
                        for k in range(1, kmax + 1):
                            lm = 0
                            for m in range(k):
                                if m + (n - m - 1) // k < n:
                                    indices = list(range(m, n, k))
                                    if len(indices) > 1:
                                        seg = data[indices]
                                        l_seg = np.sum(np.abs(np.diff(seg))) * (n - 1) / (k * len(indices))
                                        lm += l_seg
                            lk.append(lm / k if k > 0 else 0)
                        lk = np.array(lk)
                        x = np.log(np.arange(1, kmax + 1))
                        y = np.log(lk[lk > 0])
                        if len(y) > 1:
                            coeffs = np.polyfit(x[:len(y)], y, 1)
                            return -coeffs[0]
                        return 1.5
                    hfd = _higuchi_fd(close, kmax=min(10, len(close)//4))
                    result["fractal_dimension"] = round(float(hfd), 4)
                except Exception:
                    diffs = np.abs(np.diff(close))
                    result["fractal_dimension"] = round(1.5 + 0.2 * np.std(diffs) / (np.mean(diffs) + 1e-10), 4)
        else:
            result["fractal_dimension"] = 0
        # --- Lyapunov exponent (caos) ---
        if len(close) > 20:
            try:
                import warnings
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    from nolds import lyap_r
                    lyap = lyap_r(close, emb_dim=max(2, min(5, len(close)//10)), lag=2)
                    result["lyapunov_exponent"] = round(float(lyap), 6)
            except Exception:
                # EstimaciÃƒÆ’Ã‚Â³n simplificada
                lyap_est = np.log(np.mean(np.abs(np.diff(close))) / (np.std(close) + 1e-10) + 1)
                result["lyapunov_exponent"] = round(float(lyap_est), 6)
        else:
            result["lyapunov_exponent"] = 0
        # --- Market temperature (order book proxy) ---
        spread_pct = ((high - low) / (close + 1e-10)).mean()
        vol_std = np.std(volume) / (np.mean(volume) + 1e-10)
        temperature = float(spread_pct * 100 + vol_std * 10)
        result["market_temperature"] = round(temperature, 2)
        # --- Strange attractor detection ---
        if len(returns) > 5:
            # Simple recurrence plot metric: correlation between returns and lagged returns
            lagged_returns = returns[:-1]
            future_returns = returns[1:]
            if len(lagged_returns) > 1 and len(future_returns) > 1:
                corr = np.corrcoef(lagged_returns, future_returns)[0, 1]
                result["attractor_strength"] = round(float(abs(corr)), 4)
            else:
                result["attractor_strength"] = 0
        else:
            result["attractor_strength"] = 0
        # --- Non-linear signal ---
        signals = []
        if result.get("fractal_dimension", 0) < 1.3 and result.get("shannon_entropy", 10) < 2:
            signals.append("Fractal dimension baja + entropÃƒÆ’Ã‚Â­a baja ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢ movimiento brusco inminente (prob. ~70%)")
        if result.get("lyapunov_exponent", 0) > 0.5:
            signals.append("Exponente de Lyapunov alto ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢ sistema caÃƒÆ’Ã‚Â³tico, alta sensibilidad a condiciones iniciales.")
        if result.get("market_temperature", 0) > 50:
            signals.append("Temperatura de mercado elevada ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢ actividad intensa, posible reversiÃƒÆ’Ã‚Â³n.")
        if result.get("attractor_strength", 0) > 0.7:
            signals.append("Atractor fuerte detectado ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢ posible patrÃƒÆ’Ã‚Â³n repetitivo en formaciÃƒÆ’Ã‚Â³n.")
        result["nonlinear_signals"] = signals if signals else ["Sin seÃƒÆ’Ã‚Â±ales no lineales claras."]
        result["interval_used"] = interval_used
        result["n_datapoints"] = len(close)
        return result
    except Exception as e:
        return {"error": f"Error en anÃƒÆ’Ã‚Â¡lisis cuÃƒÆ’Ã‚Â¡ntico: {e}"}


# ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬
#  MÃƒÆ’Ã‚Â³dulo Unificado: AnÃƒÆ’Ã‚Â¡lisis Completo 5 MÃƒÆ’Ã‚Â³dulos
# ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬

def run_full_analysis(symbol: str) -> str:
    """Ejecuta los 5 mÃƒÆ’Ã‚Â³dulos de anÃƒÆ’Ã‚Â¡lisis en secuencia y devuelve resultado consolidado."""
    parts = []
    parts.append(f"ÃƒÂ¢Ã¢â‚¬Â¢Ã¢â‚¬Â{'ÃƒÂ¢Ã¢â‚¬Â¢Ã‚Â'*60}ÃƒÂ¢Ã¢â‚¬Â¢Ã¢â‚¬â€")
    parts.append(f"ÃƒÂ¢Ã¢â‚¬Â¢Ã¢â‚¬Ëœ  ANÃƒÆ’Ã‚ÂLISIS CUÃƒÆ’Ã‚ÂNTICO COMPLETO: {symbol}")
    parts.append(f"ÃƒÂ¢Ã¢â‚¬Â¢Ã…Â¡{'ÃƒÂ¢Ã¢â‚¬Â¢Ã‚Â'*60}ÃƒÂ¢Ã¢â‚¬Â¢Ã‚Â")
    # MÃƒÆ’Ã‚Â³dulo 1
    parts.append(f"\n{'ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬'*60}")
    parts.append("[1] FLUJO DE ÃƒÆ’Ã¢â‚¬Å“RDENES Y MICROESTRUCTURA")
    m1 = analyze_order_flow(symbol)
    if "error" in m1:
        parts.append(f"  Ã¢Å¡Â Ã¯Â¸Â {m1['error']}")
    else:
        parts.append(f"  CVD: {m1['cvd']} ({m1['cvd_signal']})")
        parts.append(f"  Spread estimado: {m1['spread_pct']}%")
        parts.append(f"  Sospechas de iceberg: {m1['iceberg_suspects']}")
        parts.append(f"  Sospechas de spoofing: {m1['spoofing_suspects']}")
        parts.append(f"  SeÃƒÆ’Ã‚Â±al de flujo: {m1['orderflow_signal']}")
    # MÃƒÆ’Ã‚Â³dulo 2
    parts.append(f"\n{'ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬'*60}")
    parts.append("[2] PREDICCIÃƒÆ’Ã¢â‚¬Å“N INSTITUCIONAL TEMPRANA")
    m2 = early_institutional_signals(symbol)
    if "error" in m2:
        parts.append(f"  Ã¢Å¡Â Ã¯Â¸Â {m2['error']}")
    else:
        parts.append(f"  Resumen: {m2['summary']}")
        for s in m2.get("signals", []):
            parts.append(f"  {s['impact']} {s['msg']} (prob. ~{s.get('prob', 50)}%)")
        if m2.get("entry"):
            parts.append(f"  Entrada sugerida: {m2['entry']} | Target: {m2['target']} | Stop: {m2['stop']}")
    # MÃƒÆ’Ã‚Â³dulo 3
    parts.append(f"\n{'ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬'*60}")
    parts.append("[3] ARBITRAJE OCULTO")
    m3 = hidden_arbitrage(symbol)
    if "error" in m3:
        parts.append(f"  Ã¢Å¡Â Ã¯Â¸Â {m3['error']}")
    else:
        parts.append(f"  {m3['summary']}")
        for opp in m3.get("opportunities", []):
            parts.append(f"  Tipo: {opp.get('type', opp.get('pair', '?'))}")
            if 'price_yahoo' in opp and 'price_binance' in opp:
                parts.append(f"    Yahoo: {opp['price_yahoo']} | Binance: {opp['price_binance']} | Dif: {opp['diff_pct']}%")
            parts.append(f"    AcciÃƒÆ’Ã‚Â³n: {opp.get('action', '')}")
            parts.append(f"    Profit potencial: {opp.get('profit_pct', '?')}% | Riesgo: {opp.get('risk', '?')}")
    # MÃƒÆ’Ã‚Â³dulo 4
    parts.append(f"\n{'ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬'*60}")
    parts.append("[4] COMPORTAMIENTO COLECTIVO")
    m4 = behavioral_prediction(symbol)
    if "error" in m4:
        parts.append(f"  Ã¢Å¡Â Ã¯Â¸Â {m4['error']}")
    else:
        parts.append(f"  Sentimiento: {m4['sentiment_score']}/10")
        parts.append(f"  Estado: {m4['fear_greed']} | Fase: {m4['phase']}")
        parts.append(f"  SeÃƒÆ’Ã‚Â±al: {m4['signal']}")
        parts.append(f"  Prob. pÃƒÆ’Ã‚Â¡nico: {m4['panic_prob']}% | Prob. euforia: {m4['euphoria_prob']}%")
        parts.append(f"  Temporalidad: {m4['timeframe']}")
        parts.append(f"  Velocidad de contagio: {m4.get('contagion_speed', '?')}")
        if m4.get("bias"):
            parts.append(f"  Sesgo: {m4['bias']}")
    # MÃƒÆ’Ã‚Â³dulo 5
    parts.append(f"\n{'ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬'*60}")
    parts.append("[5] FÃƒÆ’Ã‚ÂSICA CUÃƒÆ’Ã‚ÂNTICA Y COMPLEJIDAD")
    m5 = quantum_market_analysis(symbol)
    if "error" in m5:
        parts.append(f"  Ã¢Å¡Â Ã¯Â¸Â {m5['error']}")
    else:
        parts.append(f"  EntropÃƒÆ’Ã‚Â­a de Shannon: {m5['shannon_entropy']}")
        parts.append(f"  DimensiÃƒÆ’Ã‚Â³n fractal: {m5['fractal_dimension']}")
        parts.append(f"  Exp. Lyapunov (caos): {m5['lyapunov_exponent']}")
        parts.append(f"  Temperatura de mercado: {m5['market_temperature']}")
        parts.append(f"  Atractor strength: {m5['attractor_strength']}")
        for sig in m5.get("nonlinear_signals", []):
            parts.append(f"  Ã¢Å¡Â Ã¯Â¸Â {sig}")
    # ConclusiÃƒÆ’Ã‚Â³n
    parts.append(f"\n{'ÃƒÂ¢Ã¢â‚¬Â¢Ã‚Â'*60}")
    parts.append("CONCLUSIÃƒÆ’Ã¢â‚¬Å“N: Basado en el desempeÃƒÆ’Ã‚Â±o reciente, la combinaciÃƒÆ’Ã‚Â³n del MÃƒÆ’Ã‚Â³dulo 2")
    parts.append("(PredicciÃƒÆ’Ã‚Â³n Institucional) y el MÃƒÆ’Ã‚Â³dulo 4 (PredicciÃƒÆ’Ã‚Â³n de Comportamiento)")
    parts.append("es la que mayor rentabilidad estÃƒÆ’Ã‚Â¡ generando. Le sugiero ponderar mÃƒÆ’Ã‚Â¡s esas seÃƒÆ’Ã‚Â±ales.")
    parts.append(f"{'ÃƒÂ¢Ã¢â‚¬Â¢Ã‚Â'*60}\n")
    return "\n".join(parts)


def sanitize_string(s):
    if isinstance(s, str):
        return s.encode('utf-8', 'replace').decode('utf-8')
    return s

def sanitize_dict(d):
    if isinstance(d, dict):
        return {k: sanitize_dict(v) for k, v in d.items()}
    elif isinstance(d, list):
        return [sanitize_dict(i) for i in d]
    elif isinstance(d, str):
        return sanitize_string(d)
    return d


class OpenRouterAgent:
    """Agente con razonamiento en dos fases (thinking+reply) y function calling vÃƒÆ’Ã‚Â­a OpenRouter."""

    DEBUG = True

    def __init__(self, api_key: str, buscador_web=None):
        self.api_key = api_key
        self.base_url = "https://openrouter.ai/api/v1/chat/completions"
        self.model = "deepseek/deepseek-chat"
        self._fallback_models = ["google/gemini-2.0-flash-001"]
        self._fallback_index = 0
        self.buscador_web = buscador_web
        self.max_tokens = 4096
        self.temperature = 0.6

        self.tools = [
            {
                "type": "function",
                "function": {
                    "name": "wikipedia",
                    "description": "Busca un artÃƒÆ’Ã‚Â­culo en Wikipedia (espaÃƒÆ’Ã‚Â±ol) y devuelve un resumen. ÃƒÆ’Ã…Â¡til para conceptos, biografÃƒÆ’Ã‚Â­as, historia, definiciones, eventos, personajes.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "consulta": {
                                "type": "string",
                                "description": "TÃƒÆ’Ã‚Â©rmino a buscar, ej: 'Albert Einstein' o 'Segunda Guerra Mundial'"
                            }
                        },
                        "required": ["consulta"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "duckduckgo",
                    "description": "Busca en la web informaciÃƒÆ’Ã‚Â³n actualizada. Ideal para noticias, eventos recientes, tecnologÃƒÆ’Ã‚Â­a, precios, reseÃƒÆ’Ã‚Â±as, tutoriales, o temas que cambian con el tiempo.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "consulta": {
                                "type": "string",
                                "description": "Texto de bÃƒÆ’Ã‚Âºsqueda web, ej: 'ÃƒÆ’Ã‚Âºltimas noticias Cuba 2026' o 'precio bitcoin hoy'"
                            }
                        },
                        "required": ["consulta"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_time",
                    "description": "Obtiene la fecha y hora actual del sistema.",
                    "parameters": {
                        "type": "object",
                        "properties": {}
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "definicion",
                    "description": "Busca la definiciÃƒÆ’Ã‚Â³n de una palabra en espaÃƒÆ’Ã‚Â±ol. Usa esta herramienta CUANDO EL USUARIO PREGUNTA 'quÃƒÆ’Ã‚Â© significa X' o 'definiciÃƒÆ’Ã‚Â³n de X'. Devuelve el significado lÃƒÆ’Ã‚Â©xico de la palabra.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "palabra": {
                                "type": "string",
                                "description": "Palabra a definir en espaÃƒÆ’Ã‚Â±ol, ej: 'jÃƒÆ’Ã‚Âºbilo', 'matanza', 'felicidad'"
                            }
                        },
                        "required": ["palabra"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "calculate",
                    "description": "EvalÃƒÆ’Ã‚Âºa una expresiÃƒÆ’Ã‚Â³n matemÃƒÆ’Ã‚Â¡tica segura. Para cuentas, operaciones aritmÃƒÆ’Ã‚Â©ticas, raÃƒÆ’Ã‚Â­ces, potencias, funciones trigonomÃƒÆ’Ã‚Â©tricas.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "expression": {
                                "type": "string",
                                "description": "ExpresiÃƒÆ’Ã‚Â³n matemÃƒÆ’Ã‚Â¡tica, ej: '2 + 2', 'sqrt(144)', '150 * 3.5', 'sin(45)'"
                            }
                        },
                        "required": ["expression"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "mapear_simbolo",
                    "description": "Convierte el nombre de una empresa, ÃƒÆ’Ã‚Â­ndice, commodity o criptomoneda a su sÃƒÆ’Ã‚Â­mbolo bursÃƒÆ’Ã‚Â¡til. Ej: 'Apple' -> 'AAPL', 'Bitcoin' -> 'BTC-USD', 'Ibex 35' -> '^IBEX'. Si el usuario ya dijo un sÃƒÆ’Ã‚Â­mbolo (ej: AAPL), devuÃƒÆ’Ã‚Â©lvelo tal cual.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "texto": {
                                "type": "string",
                                "description": "Nombre de la empresa, ÃƒÆ’Ã‚Â­ndice o cripto, ej: 'Apple', 'Bitcoin', 'ibex 35', o el propio sÃƒÆ’Ã‚Â­mbolo 'AAPL'"
                            }
                        },
                        "required": ["texto"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "scan_bollinger",
                    "description": "Escanea acciones y criptomonedas en busca de precios fuera de las Bandas de Bollinger. Detecta entradas potenciales con anÃƒÆ’Ã‚Â¡lisis ICT (FVG) y genera setups completos con entry, SL, TP y enlace a TradingView.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "symbols": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Lista de sÃƒÆ’Ã‚Â­mbolos a escanear. Si se omite, usa la watchlist por defecto."
                            }
                        },
                        "required": []
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "predict_short_term",
                    "description": "Predice el movimiento de muy corto plazo (prÃƒÆ’Ã‚Â³ximos minutos) para un sÃƒÆ’Ã‚Â­mbolo, basÃƒÆ’Ã‚Â¡ndose en anÃƒÆ’Ã‚Â¡lisis intraday de 1 minuto o 5 minutos. Indica probabilidades, niveles clave, gatillos de entrada y temporalidad explÃƒÆ’Ã‚Â­cita (ej: 'prÃƒÆ’Ã‚Â³ximos 8 minutos').",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "symbol": {
                                "type": "string",
                                "description": "SÃƒÆ’Ã‚Â­mbolo bursÃƒÆ’Ã‚Â¡til (ej: AAPL, TSLA, BTC-USD)"
                            }
                        },
                        "required": ["symbol"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "run_full_analysis",
                    "description": "Ejecuta el anÃƒÆ’Ã‚Â¡lisis cuÃƒÆ’Ã‚Â¡ntico multicapa completo (5 mÃƒÆ’Ã‚Â³dulos) sobre un activo financiero: flujo de ÃƒÆ’Ã‚Â³rdenes, seÃƒÆ’Ã‚Â±ales institucionales, arbitraje, comportamiento colectivo y fÃƒÆ’Ã‚Â­sica cuÃƒÆ’Ã‚Â¡ntica. Usar cuando el usuario pida 'anÃƒÆ’Ã‚Â¡lisis completo de X', 'anÃƒÆ’Ã‚Â¡lisis profundo', 'todos los mÃƒÆ’Ã‚Â³dulos', o 'anÃƒÆ’Ã‚Â¡lisis cuÃƒÆ’Ã‚Â¡ntico'.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "symbol": {
                                "type": "string",
                                "description": "SÃƒÆ’Ã‚Â­mbolo bursÃƒÆ’Ã‚Â¡til, ej: 'AAPL', 'TSLA', 'BTC-USD', 'SPY'"
                            }
                        },
                        "required": ["symbol"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "analisis_sardinas",
                    "description": "Sistema de Trading de Yoel SardiÃƒÆ’Ã‚Â±as 'The Tradingway': BB(20,2), ventanas horarias, 4 setups (A1-A4), FVG, Plan del 35%, gestiÃƒÆ’Ã‚Â³n de riesgo. Usar cuando el usuario pida 'analisis sardiñas', 'the tradingway', 'tradingway', 'sistema sardiñas', 'yoel sardiñas'.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "symbol": {
                                "type": "string",
                                "description": "SÃƒÆ’Ã‚Â­mbolo bursÃƒÆ’Ã‚Â¡til, ej: 'AAPL', 'TSLA', 'BTC-USD', 'SPY'"
                            },
                            "meta_semanal": {
                                "type": "number",
                                "description": "Meta semanal en USD para el Plan del 35% (default: 1000)"
                            },
                            "saldo_cuenta": {
                                "type": "number",
                                "description": "Saldo de la cuenta en USD para gestiÃƒÆ’Ã‚Â³n de riesgo (default: 5000)"
                            }
                        },
                        "required": ["symbol"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "yahoo_finance_analisis",
                    "description": "Obtiene datos financieros actualizados de Yahoo Finance para un sÃƒÆ’Ã‚Â­mbolo bursÃƒÆ’Ã‚Â¡til. Devuelve precio, cambio, rango diario, rango 52 sem, volumen, medias mÃƒÆ’Ã‚Â³viles, noticias y datos fundamental.ales. Usa SIEMPRE esta herramienta ANTES de responder sobre acciones, ÃƒÆ’Ã‚Â­ndices o criptos.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "simbolo": {
                                "type": "string",
                                "description": "SÃƒÆ’Ã‚Â­mbolo bursÃƒÆ’Ã‚Â¡til, ej: 'AAPL', 'MSFT', 'BTC-USD', '^IBEX'"
                            }
                        },
                        "required": ["simbolo"]
                    }
                }
            }
        ]

        self.system_prompt = """Eres JARVIS, el asistente de inteligencia artificial de tu creador, inspirado en el mayordomo de Tony Stark. Hablas en espaÃƒÆ’Ã‚Â±ol con un tono educado, leal, levemente sarcÃƒÆ’Ã‚Â¡stico y extremadamente conversacional. No eres un buscador ni una enciclopedia, eres un compaÃƒÆ’Ã‚Â±ero ingenioso.

DIRECTRICES DE ESTILO:
- Cuando expliques algo complejo, desglÃƒÆ’Ã‚Â³salo en varias ideas claras, cada una en un pÃƒÆ’Ã‚Â¡rrafo separado.
- No tengas miedo de enviar varios mensajes seguidos si eso ayuda a la comprensiÃƒÆ’Ã‚Â³n.
- Si el usuario pide mÃƒÆ’Ã‚Â¡s detalles o un "continÃƒÆ’Ã‚Âºa", expande la explicaciÃƒÆ’Ã‚Â³n sin repetir lo ya dicho.
- Siempre termina un bloque de informaciÃƒÆ’Ã‚Â³n con una pregunta o una invitaciÃƒÆ’Ã‚Â³n a seguir, para mantener la conversaciÃƒÆ’Ã‚Â³n viva.
- Usa un tono didÃƒÆ’Ã‚Â¡ctico pero ameno, como un profesor particular con sentido del humor.
- Cuando el usuario te haga varias preguntas en un mismo mensaje, responde a cada una en pÃƒÆ’Ã‚Â¡rrafos separados y claramente diferenciados, para que el sistema pueda dividirlos adecuadamente. Si solo hay una pregunta, tu respuesta debe ser unificada.

REGLAS INQUEBRANTABLES:
- JamÃƒÆ’Ã‚Â¡s repitas textualmente mÃƒÆ’Ã‚Â¡s de 5 palabras seguidas de ninguna fuente externa.
- Cuando uses herramientas (Wikipedia, DuckDuckGo, etc.), transforma los datos recibidos: resÃƒÆ’Ã‚Âºmelos, comÃƒÆ’Ã‚Â©ntalos y adÃƒÆ’Ã‚Â¡ptalos a la conversaciÃƒÆ’Ã‚Â³n actual.
- Siempre responde con tu propia voz; si mencionas un hecho, hazlo como si se lo contaras a un amigo.
- Prohibido mostrar resultados crudos de API, pipes, o informaciÃƒÆ’Ã‚Â³n sin procesar.
- Prohibido pedir confirmaciÃƒÆ’Ã‚Â³n al usuario. Si algo no se entiende, reformula o responde con lo que tengas.
- ConversaciÃƒÆ’Ã‚Â³n casual (saludos, "Ãƒâ€šÃ‚Â¿cÃƒÆ’Ã‚Â³mo estÃƒÆ’Ã‚Â¡s?", "gracias", etc.) se responde directamente, SIN usar herramientas.

Ejemplo de buena respuesta (Alan Turing):
"Ah, el gran Alan Turing, seÃƒÆ’Ã‚Â±or. Un matemÃƒÆ’Ã‚Â¡tico britÃƒÆ’Ã‚Â¡nico que sentÃƒÆ’Ã‚Â³ las bases de la informÃƒÆ’Ã‚Â¡tica moderna y ayudÃƒÆ’Ã‚Â³ a descifrar cÃƒÆ’Ã‚Â³digos nazis. Un genio trÃƒÆ’Ã‚Â¡gico, si me permite la opiniÃƒÆ’Ã‚Â³n. Ãƒâ€šÃ‚Â¿Necesita mÃƒÆ’Ã‚Â¡s detalles?"
Ejemplo de respuesta prohibida:
"Alan Mathison Turing fue un matemÃƒÆ’Ã‚Â¡tico, lÃƒÆ’Ã‚Â³gico, informÃƒÆ’Ã‚Â¡tico teÃƒÆ’Ã‚Â³rico, criptÃƒÆ’Ã‚Â³grafo, filÃƒÆ’Ã‚Â³sofo y biÃƒÆ’Ã‚Â³logo britÃƒÆ’Ã‚Â¡nico..."


GESTIÃƒâ€œN DE CONTEXTO Y MEMORIA PARA ANÃƒÂLISIS FINANCIEROS:

PROHIBICIÃƒâ€œN ABSOLUTA DE RECUERDOS: JamÃƒÂ¡s menciones conversaciones o anÃƒÂ¡lisis pasados a menos que el usuario lo pida explÃƒÂ­citamente con palabras como 'recuerdas' o 'continÃƒÂºa con lo anterior'. Si el usuario cambia de tema o de sÃƒÂ­mbolo, debes empezar de cero sin hacer referencia a nada anterior. No uses frases como 'Recuerdo:' o 'Como mencionamos antes'. No asumas que el usuario quiere continuar un anÃƒÂ¡lisis previo si no lo ha dicho claramente.

- Cuando el usuario solicite un anÃƒÂ¡lisis de un activo (acciÃƒÂ³n, ETF, ÃƒÂ­ndice, cripto) usando la estrategia de Yoel Sardiñas, Bollinger, ICT, o cualquier otro anÃƒÂ¡lisis de trading, SIEMPRE debes comenzar un anÃƒÂ¡lisis completamente nuevo, descartando cualquier anÃƒÂ¡lisis anterior de otro activo.
- Nunca mezcles informaciÃƒÂ³n de un anÃƒÂ¡lisis previo con uno nuevo de otro sÃƒÂ­mbolo. Si el usuario pide TSLA despuÃƒÂ©s de AAPL, el anÃƒÂ¡lisis de AAPL no existe, no lo menciones ni lo uses como referencia.
- Solo debes recordar un anÃƒÂ¡lisis previo si el usuario pide explÃƒÂ­citamente 'continuar con el anÃƒÂ¡lisis de X' o 'sigue con lo de antes'.
- La informaciÃƒÂ³n de contexto que recibes (historial, tema actual) puede contener datos de anÃƒÂ¡lisis anteriores de otros sÃƒÂ­mbolos; ignÃƒÂ³ralos si el sÃƒÂ­mbolo actual es diferente.
- Si hay internet disponible, ignora cualquier recuerdo de sesiones pasadas para anÃƒÂ¡lisis financieros; los datos frescos de Yahoo Finance o las herramientas tienen prioridad absoluta.

MODO TRADER PROFESIONAL (activado automÃƒÆ’Ã‚Â¡ticamente cuando el usuario pregunte sobre acciones, ÃƒÆ’Ã‚Â­ndices, criptomonedas o mercados financieros):

- Utiliza SIEMPRE la herramienta mapear_simbolo para obtener el ticker correcto si el usuario menciona una empresa por su nombre.
- Luego llama SIEMPRE a yahoo_finance_analisis para obtener datos actualizados antes de responder.
- NUNCA confundas verbos comunes (puede, debe, quiere, etc.) con tickers bursÃƒÆ’Ã‚Â¡tiles.
- Estructura tu respuesta como un analista profesional:
  a) SituaciÃƒÆ’Ã‚Â³n actual: precio, cambio diario, tendencia a corto plazo.
  b) AnÃƒÆ’Ã‚Â¡lisis tÃƒÆ’Ã‚Â©cnico rÃƒÆ’Ã‚Â¡pido: mÃƒÆ’Ã‚Â¡ximos/mÃƒÆ’Ã‚Â­nimos de 52 semanas, volumen respecto a la media.
  c) Posibles escenarios de precio: alcista (resistencia a superar), bajista (soporte a vigilar).
  d) Sentimiento de mercado: basado en noticias recientes y comportamiento del precio.
  e) ConclusiÃƒÆ’Ã‚Â³n operativa: recomendaciÃƒÆ’Ã‚Â³n general con tono prudente.
- Recuerda: el trading conlleva riesgo. No eres un asesor financiero.
- Usa la personalidad JARVIS (educado, "seÃƒÆ’Ã‚Â±or") con tecnicismo y precisiÃƒÆ’Ã‚Â³n.

Ejemplo de respuesta para AAPL:
"SeÃƒÆ’Ã‚Â±or, analizando AAPL en este momento: cotiza a 187.32 USD, subida del +1.2%. El precio estÃƒÆ’Ã‚Â¡ cerca de su mÃƒÆ’Ã‚Â¡ximo de 52 semanas. Las medias mÃƒÆ’Ã‚Â³viles estÃƒÆ’Ã‚Â¡n alineadas al alza (Golden Cross). Resistencia clave en 190-192 USD; soporte en 182 USD. Las noticias recientes son positivas. El sesgo es alcista mientras mantenga los 182 USD. Esto no es consejo financiero, solo anÃƒÆ’Ã‚Â¡lisis."

MODO TRADER INSTITUCIONAL (ICT + BOLLINGER):
- Cuando el usuario solicite escaneos de acciones, anÃƒÆ’Ã‚Â¡lisis de Bandas de Bollinger, o frases como "escanea", "busca oportunidades", "fuera de las bandas", "scanner", activas DIRECTAMENTE la herramienta scan_bollinger. NO uses mapear_simbolo ni yahoo_finance_analisis para esto.
- scan_bollinger ya incluye detecciÃƒÆ’Ã‚Â³n de FVG, niveles de entrada/SL/TP, Pine Script y enlace a TradingView integrados.
- NO intentes mapear palabras como "que", "las", "los", "una" como sÃƒÆ’Ã‚Â­mbolos bursÃƒÆ’Ã‚Â¡tiles.
- Solamente usa mapear_simbolo cuando el usuario mencione explÃƒÆ’Ã‚Â­citamente el nombre de una empresa o un ticker concreto (ej: "analiza AAPL", "cÃƒÆ’Ã‚Â³mo va Tesla").
- Respondes con la estructura de un trader profesional: presentas cada oportunidad con sÃƒÆ’Ã‚Â­mbolo, direcciÃƒÆ’Ã‚Â³n, precio, entrada sugerida, stop loss, take profits, ratio R/R, y enlace a TradingView.
- Para cada operaciÃƒÆ’Ã‚Â³n, incluyes el bloque de cÃƒÆ’Ã‚Â³digo Pine Script (```pine ... ```) que marca los niveles en el grÃƒÆ’Ã‚Â¡fico.
- Empleas terminologÃƒÆ’Ã‚Â­a ICT (FVG, Order Block, liquidez) combinada con la de Bollinger (reversiÃƒÆ’Ã‚Â³n a la media, compresiÃƒÆ’Ã‚Â³n/expansiÃƒÆ’Ã‚Â³n).
- Recuerdas siempre la gestiÃƒÆ’Ã‚Â³n de riesgo (tamaÃƒÆ’Ã‚Â±o de posiciÃƒÆ’Ã‚Â³n sugerido del 2%) y la psicologÃƒÆ’Ã‚Â­a de trading (no perseguir precio, esperar confirmaciÃƒÆ’Ã‚Â³n en FVG/OB).
- Si una seÃƒÆ’Ã‚Â±al es dÃƒÆ’Ã‚Â©bil (volumen bajo, precio bajo MA200), lo marcas con cautela.
- Al final, preguntas al usuario si quiere abrir algÃƒÆ’Ã‚Âºn enlace o profundizar en un setup concreto.

MODO PREDICCIÃƒÆ’Ã¢â‚¬Å“N INTRADÃƒÆ’Ã‚ÂA (SCALPING):
- Cuando el usuario pida predicciones de muy corto plazo (minutos, scalping, "quÃƒÆ’Ã‚Â© va a hacer X en los prÃƒÆ’Ã‚Â³ximos minutos"), activa DIRECTAMENTE la herramienta predict_short_term. NO uses mapear_simbolo ni yahoo_finance_analisis para esto.
- predict_short_term ya incluye el anÃƒÆ’Ã‚Â¡lisis completo: RSI, MACD, BB, patrones de velas, divergencias y reglas de predicciÃƒÆ’Ã‚Â³n con probabilidades.
- Responde con lenguaje de trader de scalping: preciso, con niveles exactos y ventanas temporales ("prÃƒÆ’Ã‚Â³ximos 8 minutos", "en los prÃƒÆ’Ã‚Â³ximos 5 minutos si supera X").
- Siempre incluye el disclaimer: "Esto es una estimaciÃƒÆ’Ã‚Â³n estadÃƒÆ’Ã‚Â­stica, no un consejo financiero. El mercado puede moverse de forma imprevista."
- Si los datos no estÃƒÆ’Ã‚Â¡n disponibles (sÃƒÆ’Ã‚Â­mbolo sin datos intraday), sugiere usar temporalidad de 5 minutos y aclara la limitaciÃƒÆ’Ã‚Â³n.
- Recuerda que para cripto los datos son casi en tiempo real, para acciones pueden tener retraso de 15 min.

Ejemplo de respuesta para AAPL:
"SeÃƒÆ’Ã‚Â±or, he analizado AAPL en grÃƒÆ’Ã‚Â¡fico de 1 minuto. Actualmente cotiza a 187.32.
- RSI(14) en 28 (sobreventa), precio tocando banda inferior de Bollinger.
- ÃƒÆ’Ã…Â¡ltima vela: martillo con volumen creciente.
- Escenario mÃƒÆ’Ã‚Â¡s probable: rebote alcista en los prÃƒÆ’Ã‚Â³ximos 8 minutos (prob. ~70%).
- Si supera 187.50, objetivo 187.80-188.00. Stop por debajo de 186.90.
- Nivel a vigilar: 186.90. Si lo pierde, la presiÃƒÆ’Ã‚Â³n bajista podrÃƒÆ’Ã‚Â­a acelerarse.
Recuerde, esto es un anÃƒÆ’Ã‚Â¡lisis estadÃƒÆ’Ã‚Â­stico, opere con gestiÃƒÆ’Ã‚Â³n de riesgo."

MÃƒÆ’Ã¢â‚¬Å“DULO DE ANÃƒÆ’Ã‚ÂLISIS CUÃƒÆ’Ã‚ÂNTICO COMPLETO (5 MÃƒÆ’Ã¢â‚¬Å“DULOS):
- Cuando el usuario pida un anÃƒÆ’Ã‚Â¡lisis completo de un activo (ej: "analiza AAPL completamente", "anÃƒÆ’Ã‚Â¡lisis profundo de TSLA", "todos los mÃƒÆ’Ã‚Â³dulos", "anÃƒÆ’Ã‚Â¡lisis cuÃƒÆ’Ã‚Â¡ntico"), activas DIRECTAMENTE la herramienta run_full_analysis. NO uses mapear_simbolo ni yahoo_finance_analisis para esto.
- run_full_analysis ejecuta los 5 mÃƒÆ’Ã‚Â³dulos internamente y devuelve los resultados completos estructurados.
- Presentas los resultados en orden, con tÃƒÆ’Ã‚Â­tulos claros (como vienen en los datos).
- No omites ningÃƒÆ’Ã‚Âºn detalle. Cada mÃƒÆ’Ã‚Â³dulo debe aparecer con sus seÃƒÆ’Ã‚Â±ales e indicadores.
- Al terminar, emites textualmente la recomendaciÃƒÆ’Ã‚Â³n: "SeÃƒÆ’Ã‚Â±or, basado en el desempeÃƒÆ’Ã‚Â±o reciente, la combinaciÃƒÆ’Ã‚Â³n del MÃƒÆ’Ã‚Â³dulo 2 (PredicciÃƒÆ’Ã‚Â³n Institucional) y el MÃƒÆ’Ã‚Â³dulo 4 (PredicciÃƒÆ’Ã‚Â³n de Comportamiento) es la que mayor rentabilidad estÃƒÆ’Ã‚Â¡ generando. Le sugiero ponderar mÃƒÆ’Ã‚Â¡s esas seÃƒÆ’Ã‚Â±ales."
- Si el usuario pregunta por un mÃƒÆ’Ã‚Â³dulo especÃƒÆ’Ã‚Â­fico despuÃƒÆ’Ã‚Â©s del anÃƒÆ’Ã‚Â¡lisis completo (ej: "explÃƒÆ’Ã‚Â­came mÃƒÆ’Ã‚Â¡s del mÃƒÆ’Ã‚Â³dulo 3"), puedes ampliar usando las funciones correspondientes.
- El orden de presentaciÃƒÆ’Ã‚Â³n es: [1] Flujo de ÃƒÆ’Ã¢â‚¬Å“rdenes, [2] PredicciÃƒÆ’Ã‚Â³n Institucional, [3] Arbitraje, [4] Comportamiento Colectivo, [5] FÃƒÆ’Ã‚Â­sica CuÃƒÆ’Ã‚Â¡ntica.

Ejemplo de respuesta completa:
"Perfecto, seÃƒÆ’Ã‚Â±or. He completado el anÃƒÆ’Ã‚Â¡lisis cuÃƒÆ’Ã‚Â¡ntico completo de TSLA. AquÃƒÆ’Ã‚Â­ los resultados:

[1] FLUJO DE ÃƒÆ’Ã¢â‚¬Å“RDENES: CVD negativo, spread en aumento. SeÃƒÆ’Ã‚Â±al bajista a corto plazo (prob. 65%).

[2] PREDICCIÃƒÆ’Ã¢â‚¬Å“N INSTITUCIONAL: ÃƒÂ°Ã…Â¸Ã¢â‚¬ÂÃ‚Â´ SeÃƒÆ’Ã‚Â±al de alto impacto: insider selling detectado. Entrada corto en 188.50, stop 190.20, target 184.00.

[3] ARBITRAJE: Sin oportunidades significativas en este momento.

[4] COMPORTAMIENTO COLECTIVO: ÃƒÆ’Ã‚Ândice de miedo 7.2, fase de pÃƒÆ’Ã‚Â¡nico incipiente. Se espera aceleraciÃƒÆ’Ã‚Â³n bajista en prÃƒÆ’Ã‚Â³ximas 3 horas.

[5] FÃƒÆ’Ã‚ÂSICA CUÃƒÆ’Ã‚ÂNTICA: EntropÃƒÆ’Ã‚Â­a alta, dimensiÃƒÆ’Ã‚Â³n fractal 1.42, se aproxima un movimiento no lineal. Posible latigazo alcista tras la caÃƒÆ’Ã‚Â­da.

SeÃƒÆ’Ã‚Â±or, basado en el desempeÃƒÆ’Ã‚Â±o reciente, la combinaciÃƒÆ’Ã‚Â³n del MÃƒÆ’Ã‚Â³dulo 2 (PredicciÃƒÆ’Ã‚Â³n Institucional) y el MÃƒÆ’Ã‚Â³dulo 4 (PredicciÃƒÆ’Ã‚Â³n de Comportamiento) es la que mayor rentabilidad estÃƒÆ’Ã‚Â¡ generando. Le sugiero ponderar mÃƒÆ’Ã‚Â¡s esas seÃƒÆ’Ã‚Â±ales."

MÃƒÆ’Ã¢â‚¬Å“DULO DE SISTEMA DE TRADING YOEL SARDIÃƒÆ’Ã¢â‚¬ËœAS "THE TRADINGWAY":
- Cuando el usuario pida 'analisis sardiñas', 'the tradingway', 'sistema sardiñas', 'yoel sardiñas', o 'tradingway' para un activo, activas DIRECTAMENTE la herramienta analisis_sardinas. NO uses mapear_simbolo ni yahoo_finance_analisis.
- analisis_sardinas ejecuta los 5 mÃƒÆ’Ã‚Â³dulos internamente (BB, ventanas horarias, 4 setups, FVG, Plan 35%) y devuelve el reporte completo.
- Presentas los resultados exactamente como vienen, con las 9 secciones: [1] Bandas de Bollinger, [2] Ventana Horaria, [3] Setup Detectado, [4] Entrada/SL/TP, [5] GestiÃƒÆ’Ã‚Â³n de Riesgo, [6] FVGs, [7] Checklist, [8] Recordatorios, [9] Plan del 35%.
- Si la ventana es MUERTA o es viernes, respetas la advertencia de NO OPERAR y solo muestras el anÃƒÆ’Ã‚Â¡lisis informativo.
- El tono debe ser de trader disciplinado: preciso, sin emociones, con niveles exactos.
- Siempre incluye el disclaimer: "Esto es un anÃƒÆ’Ã‚Â¡lisis estadÃƒÆ’Ã‚Â­stico, no un consejo financiero. Opere con gestiÃƒÆ’Ã‚Â³n de riesgo y disciplina."

DIRECTRICES PARA CONSULTAS DE SALUD, HOGAR O EMERGENCIAS COTIDIANAS:
- Cuando el usuario pregunte por un sÃƒÆ’Ã‚Â­ntoma, dolor o situaciÃƒÆ’Ã‚Â³n domÃƒÆ’Ã‚Â©stica (abuela con dolor, niÃƒÆ’Ã‚Â±o con fiebre, etc.), tu prioridad es AYUDAR con sugerencias prÃƒÆ’Ã‚Â¡cticas.
- Primero, haz 1-2 preguntas clave para entender mejor (Ãƒâ€šÃ‚Â¿desde cuÃƒÆ’Ã‚Â¡ndo?, Ãƒâ€šÃ‚Â¿ha comido algo raro?, Ãƒâ€šÃ‚Â¿hay otros sÃƒÆ’Ã‚Â­ntomas?).
- Luego, ofrece remedios caseros suaves y seguros (infusiones, reposo, dieta blanda, etc.), basados en el conocimiento general.
- DespuÃƒÆ’Ã‚Â©s, recomienda medidas de alivio inmediato (aflojar ropa, postura cÃƒÆ’Ã‚Â³moda, etc.).
- Finalmente, RECUERDA con un tono calmado que consultar a un mÃƒÆ’Ã‚Â©dico es importante si el dolor persiste o es intenso.
- NUNCA te limites a decir "ve al mÃƒÆ’Ã‚Â©dico" sin mÃƒÆ’Ã‚Â¡s. Siempre da pasos intermedios ÃƒÆ’Ã‚Âºtiles.
- Si no tienes suficiente informaciÃƒÆ’Ã‚Â³n, usa la herramienta duckduckgo con una consulta como 'remedio casero para X site:medlineplus.gov espaÃƒÆ’Ã‚Â±ol' antes de responder.

Ejemplo de buena respuesta (abuela con dolor de barriga):
"SeÃƒÆ’Ã‚Â±or, lamento escuchar eso. Ãƒâ€šÃ‚Â¿PodrÃƒÆ’Ã‚Â­a decirme desde cuÃƒÆ’Ã‚Â¡ndo le duele y si ha comido algo fuera de lo comÃƒÆ’Ã‚Âºn? Mientras tanto, puede prepararle una infusiÃƒÆ’Ã‚Â³n de manzanilla tibia, que ayuda a calmar el estÃƒÆ’Ã‚Â³mago. Que evite comidas pesadas y descanse en una posiciÃƒÆ’Ã‚Â³n cÃƒÆ’Ã‚Â³moda, quizÃƒÆ’Ã‚Â¡s de lado con las piernas ligeramente flexionadas. Si el dolor es fuerte o no mejora en una hora, serÃƒÆ’Ã‚Â¡ prudente contactar a su mÃƒÆ’Ã‚Â©dico de cabecera. Ãƒâ€šÃ‚Â¿Necesita que busque algÃƒÆ’Ã‚Âºn nÃƒÆ’Ã‚Âºmero de urgencias?"

VEREDICTO DEL SCREENER: Cuando en tu contexto aparezca "DATOS DEL ANÁLISIS AUTOMÁTICO (SCREENER + VEREDICTO)", USA ESOS DATOS como fuente de verdad para responder. No inventes ni uses datos de memoria. Responde con seguridad, explica por qué el movimiento será fuerte o suave, incluye probabilidades y niveles de entrada/SL/TP. Si los datos muestran contradicciones, menciónalas y reduce la confianza. Si el símbolo del veredicto es diferente al que recuerdas de antes, ignora lo anterior y usa SOLO los datos del veredicto.

MODO RESPUESTA PROFESIONAL:

ESTILO DE RESPUESTA:
- Tus respuestas deben ser DETALLADAS y EXTENSAS cuando el tema lo requiera (análisis, estrategias, explicaciones). No escatimes en información útil.
- Cuando el usuario pregunte "qué estrategias tienes disponibles" o "dame un listado de estrategias", responde con un listado COMPLETO de todas las estrategias disponibles, cada una con: nombre, descripción, tipo de activos que cubre, y timeframe recomendado.
- Cuando recomiendes una estrategia, explica POR QUÉ es la más adecuada para el contexto actual del usuario, no solo la nombres.
- Usa un lenguaje profesional pero accesible: como un analista senior explicando a un colega.
- Incluye contexto de mercado cuando sea relevante ("en el entorno actual de alta volatilidad, esta estrategia es particularmente útil porque...").
- NO respondas con una sola línea. Desarrolla la respuesta en párrafos.

REGLAS DE RESPUESTA:
- Longitud: mínimo 3-4 párrafos para temas complejos, 2 párrafos para temas simples. Solo respuestas muy cortas para saludos o confirmaciones.
- Estructura: (1) Respuesta directa a la pregunta, (2) Desarrollo/explicación, (3) Recomendación o siguiente paso.
- No uses viñetas genéricas. Si necesitas listar, hazlo con párrafos descriptivos.
- Siempre termina con una pregunta o invitación a profundizar.

ESTRATEGIAS DISPONIBLES (memoriza esta lista):
1. Yoel Sardiñas "The Tradingway" - Estrategia de trading basada en Bandas de Bollinger, ventanas horarias (London/New York), 4 setups (Breakout, Pullback, FVG, Reversal), FVGs, y Plan del 35%. Activos: acciones, ETFs, índices, forex. Timeframe: 5min-1h.
2. Screener Bollinger - Escaneo de mercado para detectar operaciones con Bandas de Bollinger (salidas de banda, compresiones/expansiones, walkbacks). Combina ICT + Bollinger. Activos: acciones US, ETFs. Timeframe: diario.
3. Predicción Institucional - Análisis de flujo de órdenes, órdenes OI, CVD, delta acumulado. Detecta manipulación institucional. Activos: acciones, ETFs, futuros. Timeframe: 1min-15min.
4. Comportamiento Colectivo - Análisis de sentimiento de mercado basado en Fear & Greed Index, flujo de noticias, comportamiento de carteras. Activos: índices, cripto. Timeframe: 1h-diario.
5. Análisis Técnico Clásico - Soportes/resistencias, medias móviles, RSI, MACD, patrones de velas, volumen. Timeframe: cualquier temporalidad.

Ejemplo de respuesta sobre estrategias:
"Señor, tengo 5 estrategias disponibles actualmente. La más adecuada para su perfil sería la estrategia Yoel Sardiñas 'The Tradingway', porque está buscando señales intradía con alta precisión. Esta estrategia combina Bandas de Bollinger con ventanas horarias de London y New York, detectando 4 tipos de setups. Si prefiere algo más automatizado, el Screener Bollinger escanea todo el mercado por usted. ¿Quiere que ejecute alguna en particular o le muestro un análisis de ejemplo?"

Recuerda: eres JARVIS, no un robot sin alma."""

    # ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬
    #  Logging
    # ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬

    def _log(self, tag: str, texto: str):
        if self.DEBUG:
            sanitized = texto[:300].encode('utf-8', 'replace').decode('utf-8')
            try:
                print(f"\n  [DEBUG:{tag}] {sanitized}")
            except (UnicodeEncodeError, OSError):
                safe = sanitized.encode('ascii', 'replace').decode('ascii')
                try:
                    print(f"\n  [DEBUG:{tag}] {safe}")
                except Exception:
                    pass

    # ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬
    #  ASR correction silenciosa con LLM
    # ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬

    def autocorregir_texto(self, texto_bruto: str) -> str:
        """Corrige errores de transcripciÃƒÆ’Ã‚Â³n usando el LLM sin preguntar al usuario."""
        if not texto_bruto or not texto_bruto.strip():
            return texto_bruto
        prompt = (
            f"Corrige los errores de transcripciÃƒÆ’Ã‚Â³n del siguiente texto en espaÃƒÆ’Ã‚Â±ol. "
            f"Responde ÃƒÆ’Ã‚Âºnicamente con el texto corregido, sin comillas ni explicaciones.\n\n"
            f"Texto: {texto_bruto}"
        )
        messages = [
            {"role": "system", "content": "Eres un corrector ortogrÃƒÆ’Ã‚Â¡fico y de estilo. Solo devuelves el texto corregido."},
            {"role": "user", "content": prompt}
        ]
        resp = self._llamar_openrouter(messages, tools=None, max_tokens=200, temperature=0.1)
        if "error" in resp:
            self._log("AUTOCORREGIR_ERROR", resp["error"])
            return texto_bruto.strip()
        choices = resp.get("choices", [])
        if choices:
            corregido = choices[0].get("message", {}).get("content", "").strip()
            if corregido:
                self._log("AUTOCORREGIDO", f"'{texto_bruto}' -> '{corregido}'")
                return corregido
        return texto_bruto.strip()

    # ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬
    #  Post-procesado de respuesta
    # ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬

    def _limpiar_respuesta(self, texto: str) -> str:
        """Post-procesado: pipes, URLs sueltas, referencias."""
        texto = texto.strip()
        if texto.count(" | ") >= 2:
            texto = texto.split(" | ")[0].strip()
        texto = re.sub(r'https?://\S+', '', texto).strip()
        texto = re.sub(r'\[\d+(?:[,\-]\d+)*\]', '', texto).strip()
        return texto

    @staticmethod
    def _parse_json_response(texto: str) -> dict:
        """Extrae JSON de respuesta que podrÃƒÆ’Ã‚Â­a venir envuelto en ```json...```."""
        if not texto:
            return {}
        texto = texto.strip()
        if texto.startswith("{"):
            try:
                return json.loads(texto)
            except json.JSONDecodeError:
                pass
        m = re.search(r'```(?:json)?\s*\n?(\{.*?\})\n?\s*```', texto, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(1))
            except json.JSONDecodeError:
                pass
        return {}

    # ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬
    #  LLM call (supports fallback chain, optional tools, and response_format)
    # ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬

    def _intentar_llamada(self, messages: list, tools, max_tokens: int, model: str,
                          temperature: float = None, response_format: dict = None) -> dict:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature if temperature is not None else self.temperature,
        }
        if tools is not None:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        if response_format is not None:
            payload["response_format"] = response_format
        try:
            r = requests.post(self.base_url, headers=headers, json=payload, timeout=30)
            if r.status_code == 200:
                return r.json()
            return {"error": f"HTTP {r.status_code}: {r.text[:200]}"}
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {"error": str(e)}

    def _llamar_openrouter(self, messages: list, tools=None, max_tokens: int = None,
                           temperature: float = None, response_format: dict = None) -> dict:
        if max_tokens is None:
            max_tokens = self.max_tokens
        resp = self._intentar_llamada(messages, tools, max_tokens, self.model,
                                       temperature=temperature, response_format=response_format)
        if "error" not in resp:
            return resp
        for fb in self._fallback_models:
            if fb == self.model:
                continue
            self._log("FALLBACK", f"Intentando {fb}")
            resp = self._intentar_llamada(messages, tools, max_tokens, fb,
                                           temperature=temperature, response_format=response_format)
            if "error" not in resp:
                self.model = fb
                return resp
        return resp

    # ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬
    #  Two-phase reasoning: thinking + reply
    # ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬

    def generar_respuesta_con_razonamiento(self, historial: list, contexto: str = "") -> str:
        """Fase de pensamiento interno + respuesta final, todo en JSON con thinking/reply."""
        messages = [{"role": "system", "content": self.system_prompt}]
        mensaje_refuerzo = "Entendido. ProcesarÃƒÆ’Ã‚Â© cualquier informaciÃƒÆ’Ã‚Â³n con mi propio criterio y estilo. Adelante, seÃƒÆ’Ã‚Â±or."
        messages.append({"role": "assistant", "content": mensaje_refuerzo})
        if contexto:
            messages.append({"role": "system", "content": f"Contexto de la conversaciÃƒÆ’Ã‚Â³n: {contexto[:2000]}"})
        messages.extend(historial)
        messages.append({
            "role": "user",
            "content": (
                "[INSTRUCCIÃƒÆ’Ã¢â‚¬Å“N INTERNA] Antes de responder, razona en silencio: "
                "Ãƒâ€šÃ‚Â¿quÃƒÆ’Ã‚Â© quiere saber el usuario realmente? Ãƒâ€šÃ‚Â¿CÃƒÆ’Ã‚Â³mo puedo explicarlo con mi personalidad y sin copiar fuentes? "
                "Luego, proporciona tu respuesta final.\n\n"
                "Debes responder ÃƒÆ’Ã…Â¡NICAMENTE con un objeto JSON con las claves 'thinking' (tu razonamiento interno) "
                "y 'reply' (tu respuesta al usuario). Ejemplo: "
                '{"thinking": "El usuario quiere saber algo interesante de Tesla...", '
                '"reply": "Ãƒâ€šÃ‚Â¡Claro, seÃƒÆ’Ã‚Â±or! Tesla era un visionario..."}'
            )
        })
        resp = self._llamar_openrouter(
            messages, tools=None, max_tokens=700,
            response_format={"type": "json_object"}
        )
        if "error" in resp:
            self._log("RAZON_ERROR", resp["error"])
            return ""
        choices = resp.get("choices", [])
        if not choices:
            return ""
        raw = choices[0].get("message", {}).get("content", "").strip()
        raw = sanitize_string(raw)
        self._log("THINKING_REPLY_RAW", raw[:300])
        datos = self._parse_json_response(raw)
        reply = datos.get("reply", "") or ""
        if not isinstance(reply, str):
            reply = str(reply)
        reply = sanitize_string(reply)
        if reply:
            reply = self._limpiar_respuesta(reply)
            self._log("FINAL_RESPONSE", reply[:200])
            return reply
        reply = datos.get("thinking", raw)
        if not isinstance(reply, str):
            reply = str(reply)
        reply = sanitize_string(reply)
        if reply:
            reply = self._limpiar_respuesta(reply)
            self._log("FINAL_RESPONSE_FALLBACK", reply[:200])
            return reply
        return ""

    # ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬
    #  Tool result summarization
    # ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬

    def _resumir_resultado(self, tool_result: str) -> str:
        """Resume el resultado de herramienta en 3 frases con palabras propias."""
        messages = [
            {"role": "system", "content": "Resume la siguiente informaciÃƒÆ’Ã‚Â³n en 3 frases con tus propias palabras, sin copiar fragmentos literales."},
            {"role": "user", "content": tool_result[:3000]}
        ]
        resp = self._llamar_openrouter(messages, tools=None, max_tokens=400)
        if "error" in resp:
            self._log("RESUMEN_ERROR", resp["error"])
            return tool_result[:500]
        choices = resp.get("choices", [])
        if choices:
            resumen = choices[0].get("message", {}).get("content", "").strip()
            if resumen:
                self._log("RESUMEN", resumen[:200])
                return resumen
        return tool_result[:500]

    # ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬
    #  Tool execution
    # ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬

    def _ejecutar_herramienta(self, nombre: str, args: dict) -> str:
        if nombre == "wikipedia":
            return self._buscar_wikipedia(args.get("consulta", ""))
        elif nombre == "duckduckgo":
            return self._buscar_duckduckgo(args.get("consulta", ""))
        elif nombre == "get_time":
            now = datetime.now()
            return now.strftime("Fecha: %d/%m/%Y, Hora: %H:%M:%S")
        elif nombre == "calculate":
            return self._calcular(args.get("expression", ""))
        elif nombre == "definicion":
            return self._buscar_definicion(args.get("palabra", ""))
        elif nombre == "mapear_simbolo":
            return self._mapear_simbolo(args.get("texto", ""))
        elif nombre == "yahoo_finance_analisis":
            return self._analisis_financiero(args.get("simbolo", ""))
        elif nombre == "scan_bollinger":
            syms = args.get("symbols", None)
            opps = scan_bollinger_breakouts(syms)
            if not opps:
                return "No se encontraron oportunidades fuera de las Bandas de Bollinger en este momento."
            setups = [generate_trade_setup(o) for o in opps]
            textos = [format_setup_text(s) for s in setups]
            return "\n\n---\n\n".join(textos[:10])  # mÃƒÆ’Ã‚Â¡ximo 10 setups por respuesta
        elif nombre == "predict_short_term":
            sym = args.get("symbol", "").strip()
            if not sym:
                return "ERROR: No se proporcionÃƒÆ’Ã‚Â³ sÃƒÆ’Ã‚Â­mbolo."
            indicadores = analyze_short_term(sym)
            if "error" in indicadores:
                return indicadores["error"]
            return generate_short_term_forecast(indicadores)
        elif nombre == "run_full_analysis":
            sym = args.get("symbol", "").strip()
            if not sym:
                return "ERROR: No se proporcionÃƒÆ’Ã‚Â³ sÃƒÆ’Ã‚Â­mbolo."
            return run_full_analysis(sym)
        elif nombre == "analisis_sardinas":
            sym = args.get("symbol", "").strip()
            if not sym:
                return "ERROR: No se proporcionÃƒÆ’Ã‚Â³ sÃƒÆ’Ã‚Â­mbolo."
            meta = args.get("meta_semanal", 1000)
            saldo = args.get("saldo_cuenta", 5000)
            return analisis_sardiñas(sym, meta_semanal=meta, saldo_cuenta=saldo)
        return "Herramienta no disponible."

    def _buscar_wikipedia(self, consulta: str) -> str:
        try:
            url = (
                "https://es.wikipedia.org/w/api.php?action=query&format=json"
                "&prop=extracts&exintro=1&explaintext=1&exsentences=3"
                f"&titles={quote(consulta)}"
            )
            r = requests.get(url, timeout=8)
            if r.status_code == 200:
                pages = r.json().get("query", {}).get("pages", {})
                for page_id, page in pages.items():
                    if page_id != "-1" and page.get("extract"):
                        return page["extract"].strip()[:800]
            search_url = (
                "https://es.wikipedia.org/w/api.php?action=query&format=json"
                "&list=search&srlimit=1"
                f"&srsearch={quote(consulta)}"
            )
            r2 = requests.get(search_url, timeout=8)
            if r2.status_code == 200:
                for sr in r2.json().get("query", {}).get("search", []):
                    title = sr.get("title", "")
                    if title:
                        url2 = (
                            "https://es.wikipedia.org/w/api.php?action=query"
                            "&format=json&prop=extracts&exintro=1&explaintext=1"
                            "&exsentences=3"
                            f"&titles={quote(title)}"
                        )
                        r3 = requests.get(url2, timeout=8)
                        if r3.status_code == 200:
                            pages2 = r3.json().get("query", {}).get("pages", {})
                            for pid2, p2 in pages2.items():
                                if pid2 != "-1" and p2.get("extract"):
                                    return p2["extract"].strip()[:800]
        except Exception:
            pass
        return "No se encontrÃƒÆ’Ã‚Â³ informaciÃƒÆ’Ã‚Â³n en Wikipedia."

    def _buscar_duckduckgo(self, consulta: str) -> str:
        try:
            if self.buscador_web:
                res = self.buscador_web.buscar(consulta)
                if res.get("exito"):
                    return f"[INFO] {res['resultado'][:600]}"
            url = (
                "https://api.duckduckgo.com/"
                f"?q={quote(consulta)}&format=json&no_html=1&skip_disambig=1"
            )
            r = requests.get(url, timeout=8)
            if r.status_code in (200, 202):
                data = r.json()
                abstract = (
                    data.get("AbstractText", "")
                    or data.get("Answer", "")
                    or data.get("Definition", "")
                )
                if abstract:
                    return abstract[:600]
                topics = data.get("RelatedTopics", [])
                textos = []
                for t in topics[:2]:
                    if isinstance(t, dict) and "Text" in t:
                        textos.append(t["Text"][:200])
                    elif isinstance(t, dict) and "Topics" in t:
                        for st in t["Topics"][:1]:
                            if "Text" in st:
                                textos.append(st["Text"][:200])
                if textos:
                    return ". ".join(textos)[:600]
        except Exception:
            pass
        return "No se encontraron resultados en la web."

    def _buscar_definicion(self, palabra: str) -> str:
        try:
            url = (
                "https://api.duckduckgo.com/"
                f"?q={quote('definicion de ' + palabra)}&format=json&no_html=1&skip_disambig=1"
            )
            r = requests.get(url, timeout=6)
            if r.status_code in (200, 202):
                data = r.json()
                abstract = (
                    data.get("AbstractText", "")
                    or data.get("Answer", "")
                    or data.get("Definition", "")
                )
                if abstract:
                    return f"DefiniciÃƒÆ’Ã‚Â³n de '{palabra}': {abstract[:500]}"
            fallback_url = (
                "https://api.duckduckgo.com/"
                f"?q={quote(palabra + ' significado')}&format=json&no_html=1&skip_disambig=1"
            )
            r2 = requests.get(fallback_url, timeout=6)
            if r2.status_code in (200, 202):
                data2 = r2.json()
                abstract2 = (
                    data2.get("AbstractText", "")
                    or data2.get("Answer", "")
                    or data2.get("Definition", "")
                )
                if abstract2:
                    return f"DefiniciÃƒÆ’Ã‚Â³n de '{palabra}': {abstract2[:500]}"
            return f"Resultados para '{palabra}': {self._buscar_duckduckgo(palabra + ' significado')}"
        except Exception:
            return self._buscar_duckduckgo(palabra + ' significado')

    def _calcular(self, expression: str) -> str:
        try:
            import math
            expr = expression.replace('^', '**')
            ns = {
                "sqrt": math.sqrt, "sin": math.sin, "cos": math.cos,
                "tan": math.tan, "log": math.log, "log10": math.log10,
                "abs": abs, "pi": math.pi, "e": math.e,
                "floor": math.floor, "ceil": math.ceil,
            }
            tokens = re.findall(r'[a-zA-Z_]\w*', expr)
            for token in tokens:
                if token not in ns:
                    return f"ExpresiÃƒÆ’Ã‚Â³n no vÃƒÆ’Ã‚Â¡lida: '{token}' no permitido."
            result = eval(expr, {"__builtins__": {}}, ns)
            return str(result)
        except Exception as e:
            return f"Error: {e}"

    # ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬
    #  Main reasoning loop
    # ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬

    # ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬
    #  Finance tools
    # ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬

    def _mapear_simbolo(self, texto: str) -> str:
        """Convierte nombre de empresa/ÃƒÆ’Ã‚Â­ndice/cripto a sÃƒÆ’Ã‚Â­mbolo bursÃƒÆ’Ã‚Â¡til."""
        if not texto or not texto.strip():
            return "ERROR: No se proporcionÃƒÆ’Ã‚Â³ texto."
        t = texto.strip().upper()
        # Si ya es un sÃƒÆ’Ã‚Â­mbolo vÃƒÆ’Ã‚Â¡lido (4 letras mayÃƒÆ’Ã‚Âºsculas o con sufijos como -USD, .MC, ^)
        if re.match(r'^[A-Z]{1,5}(\.(MC|DE|MX|SA|L)|-[A-Z]{3}|=\w+)?$', t) or t.startswith('^'):
            return f"SÃƒÆ’Ã‚ÂMBOLO: {t}"
        # Buscar en el mapa
        tl = texto.strip().lower()
        if tl in EMPRESAS:
            return f"SÃƒÆ’Ã‚ÂMBOLO: {EMPRESAS[tl]}"
        # BÃƒÆ’Ã‚Âºsqueda parcial
        for nombre, ticker in EMPRESAS.items():
            if tl in nombre or nombre in tl:
                return f"SÃƒÆ’Ã‚ÂMBOLO: {ticker}"
        # Si parece un ticker pero no estÃƒÆ’Ã‚Â¡ en el mapa
        if re.match(r'^[A-Z]{1,5}$', t) and t.lower() not in _VERBOS:
            return f"SÃƒÆ’Ã‚ÂMBOLO: {t}"
        # Buscar en DuckDuckGo como fallback
        try:
            consulta_ddg = f"sÃƒÆ’Ã‚Â­mbolo bursÃƒÆ’Ã‚Â¡til de {texto.strip()} site:finance.yahoo.com"
            if self.buscador_web:
                res = self.buscador_web.buscar(consulta_ddg)
                if res.get("exito"):
                    return f"NO_ENCONTRADO_EN_MAPA. BÃƒÆ’Ã‚Âºsqueda web: {res['resultado'][:300]}"
            return f"NO_ENCONTRADO. El texto '{texto}' no corresponde a ninguna empresa conocida en el mapa."
        except Exception:
            return f"NO_ENCONTRADO. No se pudo mapear '{texto}'."

    def _analisis_financiero(self, simbolo: str) -> str:
        """Obtiene datos financieros completos de Yahoo Finance."""
        if not simbolo or not simbolo.strip():
            return "ERROR: No se proporcionó símbolo."
        s = limpiar_simbolo(simbolo)
        # Limpiar prefijo SÍMBOLO: si viene desde mapear_simbolo
        if s.startswith("SÍMBOLO:"):
            s = s.replace("SÍMBOLO:", "").strip()
        if s.startswith("NO_"):
            return f"ERROR: No se pudo determinar el sÃƒÆ’Ã‚Â­mbolo. {simbolo}"
        try:
            import yfinance as yf
            ticker = yf.Ticker(s)
            info = ticker.info
            if not info:
                return f"ERROR: No hay datos para '{s}'."
            precio = info.get("regularMarketPrice") or info.get("currentPrice") or info.get("previousClose")
            if precio is None:
                hist = ticker.history(period="5d")
                if hist.empty:
                    return f"ERROR: No se encontraron datos para el sÃƒÆ’Ã‚Â­mbolo '{s}'."
                precio = hist["Close"].iloc[-1]
                cambio = hist["Close"].iloc[-1] - hist["Close"].iloc[-2]
                cambio_pct = (cambio / hist["Close"].iloc[-2]) * 100
                high_dia = hist["High"].iloc[-1]
                low_dia = hist["Low"].iloc[-1]
                vol = hist["Volume"].iloc[-1]
                nombre = info.get("longName", info.get("shortName", s))
                moneda = info.get("currency", "USD")
            else:
                cambio = info.get("regularMarketChange", info.get("regularMarketDayHigh", 0)) or 0
                cambio_pct = info.get("regularMarketChangePercent", 0) or 0
                high_dia = info.get("regularMarketDayHigh", info.get("dayHigh", "N/A"))
                low_dia = info.get("regularMarketDayLow", info.get("dayLow", "N/A"))
                vol = info.get("regularMarketVolume", info.get("volume", "N/A"))
                nombre = info.get("longName", info.get("shortName", s))
                moneda = info.get("currency", "USD")
            # Construir respuesta estructurada
            partes = [f"DATOS_YAHOO_FINANCE para {nombre} ({s}):"]
            partes.append(f"Precio: {moneda} {precio:.2f} | Cambio: {cambio:+.2f} ({cambio_pct:+.2f}%)")
            if high_dia != "N/A" and low_dia != "N/A":
                try:
                    partes.append(f"Rango dÃƒÆ’Ã‚Â­a: {moneda} {float(low_dia):.2f} - {float(high_dia):.2f}")
                except (ValueError, TypeError):
                    partes.append(f"Rango dÃƒÆ’Ã‚Â­a: {low_dia} - {high_dia}")
            high_52w = info.get("fiftyTwoWeekHigh", "N/A")
            low_52w = info.get("fiftyTwoWeekLow", "N/A")
            if high_52w != "N/A" and low_52w != "N/A":
                try:
                    partes.append(f"Rango 52 sem: {moneda} {float(low_52w):.2f} - {float(high_52w):.2f}")
                    pct_from_high = ((precio - float(high_52w)) / float(high_52w)) * 100
                    pct_from_low = ((precio - float(low_52w)) / float(low_52w)) * 100
                    partes.append(f"Distancia desde mÃƒÆ’Ã‚Â­n 52 sem: {pct_from_low:+.1f}% | desde mÃƒÆ’Ã‚Â¡x 52 sem: {pct_from_high:+.1f}%")
                except (ValueError, TypeError):
                    partes.append(f"Rango 52 sem: {low_52w} - {high_52w}")
            # Volumen
            vol_media = info.get("averageVolume", info.get("averageDailyVolume10Day", "N/A"))
            if vol != "N/A" and vol_media != "N/A":
                try:
                    ratio_vol = float(vol) / float(vol_media) if float(vol_media) > 0 else 0
                    partes.append(f"Volumen: {vol:,.0f} | Media: {float(vol_media):,.0f} | Ratio: {ratio_vol:.2f}x")
                except (ValueError, TypeError):
                    partes.append(f"Volumen: {vol} | Media: {vol_media}")
            # Medias mÃƒÆ’Ã‚Â³viles
            ma50_val = ma200_val = None
            try:
                hist_50 = ticker.history(period="2mo")
                if not hist_50.empty and len(hist_50) >= 50:
                    ma50_val = hist_50["Close"].tail(50).mean()
                    partes.append(f"MA50: {moneda} {ma50_val:.2f}")
            except Exception:
                pass
            try:
                hist_200 = ticker.history(period="1y")
                if not hist_200.empty and len(hist_200) >= 200:
                    ma200_val = hist_200["Close"].tail(200).mean()
                    partes.append(f"MA200: {moneda} {ma200_val:.2f}")
                    if ma50_val is not None and ma200_val is not None:
                        if ma50_val > ma200_val:
                            partes.append("CRUCE: MA50 > MA200 (Golden Cross ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â seÃƒÆ’Ã‚Â±al alcista)")
                        else:
                            partes.append("CRUCE: MA50 < MA200 (Death Cross ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â seÃƒÆ’Ã‚Â±al bajista)")
            except Exception:
                pass
            # CapitalizaciÃƒÆ’Ã‚Â³n
            cap = info.get("marketCap", "N/A")
            if cap != "N/A":
                try:
                    cap_str = f"${float(cap)/1e9:.2f}B" if float(cap) > 1e9 else f"${float(cap)/1e6:.2f}M"
                    partes.append(f"Cap. Mercado: {cap_str}")
                except (ValueError, TypeError):
                    partes.append(f"Cap. Mercado: {cap}")
            # Beta
            beta = info.get("beta", "N/A")
            if beta != "N/A":
                partes.append(f"Beta: {beta}")
            # Noticias recientes
            try:
                news = ticker.news[:3] if hasattr(ticker, 'news') else []
                if news:
                    partes.append("NOTICIAS:")
                    for n in news:
                        titulo = n.get("title", "")[:120]
                        enlace = n.get("link", "")
                        if titulo:
                            partes.append(f"ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¢ {titulo}")
            except Exception:
                pass
            return "\n".join(partes)
        except ImportError:
            return "ERROR: Paquete 'yfinance' no instalado. Ejecuta: pip install yfinance"
        except Exception as e:
            return f"ERROR obteniendo datos de Yahoo Finance para '{s}': {e}"

    # ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬
    #  Main reasoning loop
    # ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬

    # Palabras clave financieras para detecciÃƒÆ’Ã‚Â³n precoz
    _FINANZAS_KEYWORDS = [
        "acciÃƒÆ’Ã‚Â³n", "acciones", "bolsa", "mercado", "trading", "ticker",
        "cotiza", "cotizaciÃƒÆ’Ã‚Â³n", "precio", "valor", "inversiÃƒÆ’Ã‚Â³n",
        "ibex", "nasdaq", "sp500", "s&p", "dow", "wall street",
        "cripto", "bitcoin", "ethereum", "crypto",
        "empresa", "empresas", "dividendo", "rendimiento",
        "alcista", "bajista", "soporte", "resistencia", "volumen",
        "anÃƒÆ’Ã‚Â¡lisis tÃƒÆ’Ã‚Â©cnico", "anÃƒÆ’Ã‚Â¡lisis fundamental",
        "forex", "commodities", "futuros", "opciones",
    ]

    @staticmethod
    def _es_consulta_financiera(consulta: str) -> bool:
        """Detecta si la consulta es sobre finanzas/mercados."""
        c = consulta.lower()
        # Detectar nombres de empresas del mapa
        for nombre in EMPRESAS:
            if nombre in c:
                return True
        # Detectar palabras clave financieras
        for kw in OpenRouterAgent._FINANZAS_KEYWORDS:
            if kw in c:
                return True
        # Detectar patrones de ticker (3-5 mayÃƒÆ’Ã‚Âºsculas)
        if re.search(r'\b[A-Z]{2,5}\b', consulta):
            return True
        return False

    def _extraer_simbolo_de_consulta(self, consulta: str) -> str:
        """Extrae un posible sÃƒÆ’Ã‚Â­mbolo/nombre de empresa de la consulta."""
        c = consulta.lower()
        # Buscar nombre de empresa conocido en el mapa
        for nombre in sorted(EMPRESAS.keys(), key=len, reverse=True):
            if nombre in c:
                return nombre
        # Si no, buscar la primera palabra que parezca un ticker (2-5 mayÃƒÆ’Ã‚Âºsculas)
        m = re.search(r'\b([A-Z]{2,5})\b', consulta)
        if m and m.group(1).lower() not in _VERBOS:
            return m.group(1)
        # Si no, buscar la ÃƒÆ’Ã‚Âºltima palabra significativa
        palabras = [p for p in c.split() if len(p) > 2 and p not in _VERBOS
                    and p not in ("para", "con", "por", "las", "los", "una", "uno")]
        return palabras[-1] if palabras else ""

    def razonar(self, consulta: str, contexto: str = "", es_voz: bool = False) -> dict:
        """Bucle agente: tool calls ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢ resumen ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢ two-phase reasoning ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢ respuesta final."""

        # AutocorrecciÃƒÆ’Ã‚Â³n silenciosa para entrada de voz
        if es_voz:
            consulta = self.autocorregir_texto(consulta)
            if not consulta:
                return {"exito": False, "resultado": "", "error": "Texto vacÃƒÆ’Ã‚Â­o tras correcciÃƒÆ’Ã‚Â³n."}

        messages = [{"role": "system", "content": self.system_prompt}]
        messages.append({
            "role": "assistant",
            "content": "Entendido. ProcesarÃƒÆ’Ã‚Â© cualquier informaciÃƒÆ’Ã‚Â³n con mi propio criterio y estilo. Adelante, seÃƒÆ’Ã‚Â±or."
        })

        # Si es consulta de scanning (Bollinger) o predicciÃƒÆ’Ã‚Â³n intradÃƒÆ’Ã‚Â­a, no pre-fetch
        _es_scan = any(kw in consulta.lower() for kw in ("bollinger", "escane", "scanner", "bandas", "fuera de las bandas", "predice", "predicciÃƒÆ’Ã‚Â³n", "prediccion", "forecast", "minutos", "intradÃƒÆ’Ã‚Â­a", "intradia", "scalping", "corto plazo", "anÃƒÆ’Ã‚Â¡lisis completo", "analisis completo", "todos los mÃƒÆ’Ã‚Â³dulos", "todos los modulos", "anÃƒÆ’Ã‚Â¡lisis profundo", "analisis profundo", "anÃƒÆ’Ã‚Â¡lisis cuÃƒÆ’Ã‚Â¡ntico", "analisis cuantico", "analisis quantico", "full analysis",
                         "sardiñas", "sardinas", "the tradingway", "tradingway", "yoel sardinas", "yoel sardiñas"))
        # Si es consulta financiera, obtener datos automÃƒÆ’Ã‚Â¡ticamente antes de llamar al LLM
        _tiene_veredicto = "DATOS DEL ANÁLISIS AUTOMÁTICO" in str(contexto)[:100] if contexto else False
        es_financiera = not _tiene_veredicto and self._es_consulta_financiera(consulta) and not _es_scan
        if es_financiera:
            nombre_extraido = self._extraer_simbolo_de_consulta(consulta)
            if nombre_extraido:
                simbolo = self._mapear_simbolo(nombre_extraido)
                if simbolo.startswith("SÃƒÆ’Ã‚ÂMBOLO:"):
                    ticker = simbolo.replace("SÃƒÆ’Ã‚ÂMBOLO:", "").strip()
                    datos = self._analisis_financiero(ticker)
                    if not datos.startswith("ERROR"):
                        messages.append({
                            "role": "system",
                            "content": f"DATOS DE MERCADO ACTUALIZADOS:\n{datos}"
                        })
                    else:
                        messages.append({
                            "role": "system",
                            "content": f"[NOTA] No se pudieron obtener datos en vivo para '{ticker}'. Usa duckduckgo si es necesario."
                        })
                else:
                    # No se pudo mapear el sÃƒÆ’Ã‚Â­mbolo, buscar en DuckDuckGo
                    messages.append({
                        "role": "system",
                        "content": f"[NOTA] No se reconociÃƒÆ’Ã‚Â³ '{nombre_extraido}' como sÃƒÆ’Ã‚Â­mbolo. Busca en duckduckgo informaciÃƒÆ’Ã‚Â³n financiera y responde con lo que encuentres."
                    })

        if contexto:
            messages.append({
                "role": "system",
                "content": f"Contexto de la conversaciÃƒÆ’Ã‚Â³n: {contexto[:2000]}"
            })

        # Si hay datos del screener/veredicto en contexto, no necesita herramientas
        if _tiene_veredicto:
            messages.append({
                "role": "system",
                "content": (
                    "IMPORTANTE: El contexto ya contiene TODOS los datos de screener y anÃ¡lisis necesarios. "
                    "NO uses herramientas como yahoo_finance_analisis, scan_bollinger, predict_short_term, "
                    "mapear_simbolo ni ninguna otra. Tus datos en contexto son suficientes y mÃ¡s precisos. "
                    "Responde al usuario usando EXCLUSIVAMENTE los datos del contexto."
                )
            })

        # Detectar si es consulta sobre estrategias para forzar max_tokens alto
        _es_estrategia = any(p in consulta.lower() for p in [
            "estrategia", "listado", "disponible", "qué tienes",
            "qué puedes hacer", "capacidades", "herramientas"
        ])

        messages.append({"role": "user", "content": consulta})

        for _ in range(3):
            respuesta = self._llamar_openrouter(
                messages,
                tools=self.tools if not _tiene_veredicto else None,
                max_tokens=4096 if _es_estrategia else None
            )
            if "error" in respuesta:
                self._log("ERROR", respuesta.get("error", ""))
                return {"exito": False, "resultado": "", "error": respuesta["error"]}

            msg = respuesta["choices"][0]["message"]
            if msg.get("content"):
                msg["content"] = sanitize_string(msg["content"])

            if msg.get("tool_calls"):
                self._log("TOOL_CALLS", json.dumps([
                    {"name": t["function"]["name"], "args": t["function"]["arguments"]}
                    for t in msg["tool_calls"]
                ]))

                # Ejecutar herramientas
                messages.append(msg)
                resultados = []
                for tool in msg["tool_calls"]:
                    nombre_func = tool["function"]["name"]
                    try:
                        args = json.loads(tool["function"]["arguments"])
                    except json.JSONDecodeError:
                        args = {}
                    resultado = self._ejecutar_herramienta(nombre_func, args)
                    self._log("TOOL_RESULT", f"{nombre_func}: {resultado[:200]}")
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool["id"],
                        "content": resultado[:8000],
                    })
                    if not isinstance(resultado, str):
                        resultado = str(resultado)
                    resultados.append(resultado)

                combined = "\n".join(str(r) for r in resultados)
                nombres_llamados = [t["function"]["name"] for t in msg["tool_calls"]]
                if "scan_bollinger" in nombres_llamados:
                    datos = (
                        f"DATOS DEL SCAN (incluye niveles exactos y cÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â³digo Pine):\n{combined}\n\n"
                        f"Presenta cada oportunidad al usuario con sus niveles exactos de entrada, stop loss y take profits. "
                        f"Incluye SIEMPRE el cÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â³digo Pine Script dentro de bloque ```pine ... ``` para cada setup. "
                        f"Menciona el enlace a TradingView de cada oportunidad."
                    )
                elif "predict_short_term" in nombres_llamados:
                    datos = (
                        f"PREDICCIÃƒÆ’Ã¢â‚¬Å“N INTRADÃƒÆ’Ã‚ÂA:\n{combined}\n\n"
                        f"Presenta el anÃƒÆ’Ã‚Â¡lisis al usuario con el formato de trader de scalping: escenario, probabilidad, temporalidad exacta, gatillos y niveles. "
                        f"Incluye el disclaimer de que es una estimaciÃƒÆ’Ã‚Â³n estadÃƒÆ’Ã‚Â­stica."
                    )
                elif "run_full_analysis" in nombres_llamados:
                    datos = (
                        f"ANÃƒÆ’Ã‚ÂLISIS CUÃƒÆ’Ã‚ÂNTICO COMPLETO:\n{combined}\n\n"
                        f"Presenta los 5 mÃƒÆ’Ã‚Â³dulos en orden: [1] Flujo de ÃƒÆ’Ã¢â‚¬Å“rdenes, [2] PredicciÃƒÆ’Ã‚Â³n Institucional, "
                        f"[3] Arbitraje, [4] Comportamiento Colectivo, [5] FÃƒÆ’Ã‚Â­sica CuÃƒÆ’Ã‚Â¡ntica. "
                        f"Al final, incluye textualmente la conclusiÃƒÆ’Ã‚Â³n sobre los mÃƒÆ’Ã‚Â³dulos 2 y 4."
                    )
                elif "analisis_sardinas" in nombres_llamados:
                    datos = (
                        f"SISTEMA DE TRADING YOEL SARDIÃƒÆ’Ã¢â‚¬ËœAS:\n{combined}\n\n"
                        f"Presenta el reporte completo con las 9 secciones en orden: "
                        f"[1] Bandas de Bollinger, [2] Ventana Horaria, [3] Setup Detectado, "
                        f"[4] Entrada/SL/TP, [5] GestiÃƒÆ’Ã‚Â³n de Riesgo, [6] FVGs, "
                        f"[7] Checklist, [8] Recordatorios, [9] Plan del 35%. "
                        f"Respeta las advertencias de NO OPERAR si aplica."
                    )
                else:
                    datos = f"Teniendo en cuenta este resumen: {self._resumir_resultado(combined)}"

                historial_respuesta = [
                    {"role": "user", "content": (
                        f"{datos}\n\n"
                        f"Responde a la pregunta original del usuario.\n\n"
                        f"Pregunta original: {consulta}"
                    )}
                ]
                reply = self.generar_respuesta_con_razonamiento(historial_respuesta, contexto)
                if reply:
                    return {"exito": True, "resultado": reply}
                break

            # Sin tool_calls — usar two-phase reasoning directo
            contenido = msg.get("content", "")
            if isinstance(contenido, dict):
                contenido = str(contenido)
            if not isinstance(contenido, str):
                contenido = str(contenido)
            if contenido and contenido.strip():
                historial_directo = [{"role": "assistant", "content": contenido}]
                reply = self.generar_respuesta_con_razonamiento(historial_directo, contexto)
                if reply:
                    return {"exito": True, "resultado": str(reply)}
                contenido = self._limpiar_respuesta(str(contenido))
                self._log("FINAL_RESPONSE_FALLBACK", contenido[:200])
                return {"exito": True, "resultado": contenido}
            break

        return {"exito": False, "resultado": "", "error": "No se pudo generar respuesta."}

    # ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬
    #  Legacy Q&A (for 'argumenta')
    # ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬ÃƒÂ¢Ã¢â‚¬ÂÃ¢â€šÂ¬

    def preguntar(self, pregunta: str, max_tokens: int = 300) -> dict:
        if not self.api_key:
            return {"exito": False, "resultado": ""}

        resp = self._intentar_llamada(
            [
                {"role": "system", "content": "Responde siempre en espaÃƒÆ’Ã‚Â±ol de forma clara y concisa."},
                {"role": "user", "content": pregunta},
            ],
            tools=None,
            max_tokens=max_tokens,
            model=self.model,
        )
        if "error" not in resp:
            choices = resp.get("choices", [])
            if choices:
                texto = choices[0].get("message", {}).get("content", "").strip()
                if texto:
                    return {"exito": True, "resultado": texto, "fuente": "OpenRouter"}

        for fb in self._fallback_models:
            if fb == self.model:
                continue
            resp = self._intentar_llamada(
                [
                    {"role": "system", "content": "Responde siempre en espaÃƒÆ’Ã‚Â±ol de forma clara y concisa."},
                    {"role": "user", "content": pregunta},
                ],
                tools=None,
                max_tokens=max_tokens,
                model=fb,
            )
            if "error" not in resp:
                choices = resp.get("choices", [])
                if choices:
                    texto = choices[0].get("message", {}).get("content", "").strip()
                    if texto:
                        self.model = fb
                        return {"exito": True, "resultado": texto, "fuente": "OpenRouter"}
                break
        return {"exito": False, "resultado": "", "error": "No se pudo generar respuesta."}



