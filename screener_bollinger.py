"""
Screener de múltiples filtros en cascada para entradas con Bollinger Bands.
Parte de 50-100 acciones y aplica filtros secuenciales para dejar solo las mejores.
"""

import yfinance as yf
import pandas as pd
import numpy as np
import requests
from datetime import datetime, timedelta
import re
import warnings
warnings.filterwarnings("ignore", category=FutureWarning)

# ── Watchlist principal (SP500 + ETFs + Cripto) ──
WATCHLIST = [
    # Tech (Magnificent 7 + grandes tech)
    "AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "META", "NVDA",
    "ADBE", "INTC", "AMD", "CRM", "ORCL", "IBM", "CSCO", "QCOM", "TXN", "AVGO",
    "NOW", "SHOP", "SPOT", "DDOG", "PANW", "FTNT", "ANET", "MRVL", "WDAY",
    "NET", "PLTR", "SNAP", "ZM", "COIN", "ABNB", "UBER", "SQ", "PYPL",
    "MU", "NXPI", "MCHP", "KLAC", "LRCX", "AMAT", "ADI", "STM", "SNPS",
    "CDNS", "ROP", "ADSK", "TEAM", "HUBS", "RNG", "TWLO",
    # Financieras
    "JPM", "V", "MA", "GS", "MS", "BAC", "WFC", "C", "AXP", "BLK",
    "SCHW", "TROW", "MCO", "SPGI", "ICE", "CME", "COF", "DFS", "SYF",
    "USB", "PNC", "TFC", "BK", "STT", "NTRS", "KEY", "FITB", "HBAN",
    "ALL", "CB", "MET", "PRU", "MMC", "AON", "AJG", "BRO", "ERIE",
    # Consumo
    "WMT", "KO", "PEP", "MCD", "NKE", "HD", "LOW", "COST", "SBUX", "DIS",
    "PG", "CL", "EL", "KMB", "CHD", "CLX", "SJM", "CAG", "CPB", "K",
    "AMZN", "TGT", "DG", "DLTR", "ROST", "TJX", "BBY", "AMZN",
    "DHI", "LEN", "NVR", "PHM", "LOW", "HD", "MHK", "MAS",
    "GM", "F", "TSLA", "RIVN", "LCID",
    # Salud
    "JNJ", "PFE", "MRK", "ABBV", "UNH", "LLY", "TMO", "BMY", "AMGN", "CVS",
    "GILD", "VRTX", "REGN", "BIIB", "MRNA", "DHR", "ZTS", "ISRG", "SYK", "BSX",
    "MDT", "ABT", "EW", "ILMN", "DXCM", "IDXX", "HOLX", "TFX", "COO",
    "HUM", "CNC", "CI", "ELV", "MOH", "DVA",
    # Industrial
    "CAT", "GE", "HON", "MMM", "UPS", "LMT", "RTX", "DE", "EMR",
    "BA", "GD", "NOC", "LHX", "TXT", "AXON",
    "UNP", "CSX", "NSC", "FDX", "JBHT", "ODFL",
    "WM", "RSG",
    "CARR", "IR", "DOV", "SWK", "TT", "OTIS",
    "AME", "ETN", "ROK", "GWW", "FAST", "MSM", "ITW", "CMI", "PCAR",
    # Energía
    "XOM", "CVX", "COP", "EOG", "OXY", "SLB", "HAL", "BKR",
    "NEE", "DUK", "SO", "D", "AEP", "EXC", "XEL",
    # ETFs
    "SPY", "QQQ", "IWM", "DIA", "XLF", "XLK", "XLV", "XLE", "XLI", "XLP",
    "XLU", "XLB", "XLRE", "XLC", "XLY", "XBI", "IBB", "SMH", "SOXX",
    "ARKK", "ARKW", "TAN", "ICLN", "VWO", "EEM", "EFA", "TLT", "HYG",
    "GDX", "GLD", "SLV", "USO", "DBC",
    # Cripto
    "BTC-USD", "ETH-USD", "SOL-USD", "DOGE-USD", "ADA-USD",
    "XRP-USD", "AVAX-USD", "DOT-USD", "POL-USD", "LINK-USD",
    "UNI-USD", "ATOM-USD", "LTC-USD", "BCH-USD", "ETC-USD",
]


def limpiar_simbolo(s: str) -> str:
    """Limpia un símbolo quitando $ y espacios."""
    return s.replace('$', '').strip().upper()


def _get_data(symbol: str, period: str = "60d"):
    """Descarga datos de yfinance, devuelve DataFrame o None."""
    try:
        symbol = limpiar_simbolo(symbol)
        tk = yf.Ticker(symbol)
        df = tk.history(period=period)
        if df.empty or len(df) < 50:
            return None
        df.dropna(inplace=True)
        return df
    except Exception:
        return None


def _bb_breakout(df: pd.DataFrame, period=20, std_dev=2.0):
    """Determina si el precio está fuera de Bollinger. Retorna dict o None."""
    if df is None or len(df) < period:
        return None
    close = df["Close"].astype(float)
    sma = close.rolling(period).mean()
    std = close.rolling(period).std()
    upper = sma + std_dev * std
    lower = sma - std_dev * std
    last = float(close.iloc[-1])
    last_sma = float(sma.iloc[-1])
    last_up = float(upper.iloc[-1])
    last_lo = float(lower.iloc[-1])
    if pd.isna(last_up) or pd.isna(last_lo):
        return None
    if last > last_up:
        return {"banda": "superior", "direccion": "venta", "precio": last,
                "sma": last_sma, "upper": last_up, "lower": last_lo}
    if last < last_lo:
        return {"banda": "inferior", "direccion": "compra", "precio": last,
                "sma": last_sma, "upper": last_up, "lower": last_lo}
    return None


def filtrar_fuera_bollinger(symbols: list = None, progress_callback=None):
    """
    Paso 1: encuentra símbolos con precio fuera de BB(20,2).
    Retorna (fuera_list, dentro_list).
    """
    if symbols is None:
        symbols = WATCHLIST
    fuera = []
    dentro = []
    total = len(symbols)
    for i, sym in enumerate(symbols):
        if progress_callback:
            progress_callback(i + 1, total, sym)
        df = _get_data(sym)
        bb = _bb_breakout(df)
        if bb:
            bb["symbol"] = sym
            fuera.append(bb)
        else:
            dentro.append(sym)
    return fuera, dentro


def aplicar_filtros_seguros(symbols_data: list, progress_callback=None):
    """
    Paso 2: aplica filtros de confirmación a los símbolos fuera de BB.
    Retorna (aprobados, descartados_con_motivo).
    """
    aprobados = []
    descartados = []
    total = len(symbols_data)
    for i, item in enumerate(symbols_data):
        sym = item["symbol"]
        if progress_callback:
            progress_callback(i + 1, total, sym)
        motivo = []
        score = 0
        df = _get_data(sym, period="120d")
        if df is None or len(df) < 50:
            descartados.append(f"{sym} — datos insuficientes")
            continue
        close = df["Close"].astype(float)
        high = df["High"].astype(float)
        low = df["Low"].astype(float)
        volume = df["Volume"].astype(float)
        direccion = item["direccion"]  # "compra" o "venta"

        # 1. Volumen de confirmación
        vol_avg = volume.tail(20).mean()
        vol_ratio = volume.iloc[-1] / vol_avg if vol_avg > 0 else 0
        if vol_ratio < 1.5:
            motivo.append(f"volumen bajo ({vol_ratio:.1f}x)")
        else:
            score += 2

        # 2. Tendencia alineada (SMA50)
        sma50 = close.rolling(50).mean()
        pendiente = sma50.diff().tail(5).mean() if len(sma50) > 5 else 0
        if direccion == "compra" and pendiente > 0:
            score += 2
        elif direccion == "venta" and pendiente < 0:
            score += 2
        else:
            motivo.append(f"tendencia SMA50 no alineada (pend={pendiente:.2f})")

        # 3. RSI extremo pero no sobre-extendido
        delta = close.diff()
        gain = delta.clip(lower=0).rolling(14).mean()
        loss = (-delta.clip(upper=0)).rolling(14).mean()
        rs = gain / (loss + 1e-10)
        rsi = 100 - (100 / (1 + rs))
        rsi_val = float(rsi.iloc[-1]) if not rsi.empty and not pd.isna(rsi.iloc[-1]) else 50
        if direccion == "compra" and 60 <= rsi_val <= 85:
            score += 2
        elif direccion == "venta" and 15 <= rsi_val <= 40:
            score += 2
        else:
            if direccion == "compra":
                motivo.append(f"RSI fuera de rango ({rsi_val:.0f}, esperado 60-85)")
            else:
                motivo.append(f"RSI fuera de rango ({rsi_val:.0f}, esperado 15-40)")

        # 4. ATR razonable
        atr = (high - low).rolling(14).mean()
        atr_actual = float(atr.iloc[-1]) if not atr.empty else 0
        atr_media = float(atr.tail(50).mean()) if len(atr) > 50 else 0
        if atr_media > 0 and atr_actual <= atr_media * 2:
            score += 2
        else:
            motivo.append(f"ATR elevado ({atr_actual:.2f} vs media {atr_media:.2f})")

        # 5. Distancia a soporte/resistencia
        if direccion == "compra":
            nivel_opuesto = float(low.tail(20).min())  # soporte
            distancia_nivel = (item["precio"] - nivel_opuesto) / (item["precio"] + 1e-10) * 100
        else:
            nivel_opuesto = float(high.tail(20).max())  # resistencia
            distancia_nivel = (nivel_opuesto - item["precio"]) / (item["precio"] + 1e-10) * 100
        sl_estimado = atr_actual / (item["precio"] + 1e-10) * 100 if atr_actual > 0 else 2
        if distancia_nivel > sl_estimado * 1.5:
            score += 2
        else:
            motivo.append(f"nivel cercano ({distancia_nivel:.1f}%, SL est: {sl_estimado:.1f}%)")

        # 6. Filtro de noticias (earnings check)
        tiene_noticias = _check_earnings(sym)
        warning_noticias = ""
        if tiene_noticias:
            warning_noticias = " earnings reciente"
            motivo.append(f"earnings reciente")

        if motivo and score < 4:
            descartados.append(f"{sym} — {', '.join(motivo[:2])}")
            continue

        # Clasificar fuera de BB
        clasif = clasificar_fuera_bb(df, item)

        aprobados.append({
            "symbol": sym,
            "precio": round(item["precio"], 2),
            "banda": item["banda"],
            "direccion": direccion,
            "vol_ratio": round(vol_ratio, 2),
            "rsi": round(rsi_val, 1),
            "atr": round(atr_actual, 4),
            "score": score,
            "motivos": motivo,
            "warning_noticias": warning_noticias,
            "nivel_opuesto": round(nivel_opuesto, 2),
            "distancia_nivel_pct": round(distancia_nivel, 2),
            "prediccion": clasif["prediccion"],
            "score_continuacion": clasif["score_continuacion"],
            "razones_bb": clasif["razones"],
            "velas_fuera_bb": clasif["velas_fuera_bb"],
        })
    return aprobados, descartados


def _check_earnings(symbol: str) -> bool:
    """Verifica si hay noticias de earnings recientes (últimos 7 días)."""
    try:
        tk = yf.Ticker(symbol)
        earnings = tk.earnings_dates
        if earnings is None or earnings.empty:
            return False
        recent = earnings.head(3)
        for idx in recent.index:
            if hasattr(idx, 'tz_localize'):
                dt = idx
            else:
                dt = pd.Timestamp(idx)
            if dt.tz is None:
                dt = dt.tz_localize('UTC')
            now = datetime.now(pd.Timestamp.utcnow().tz if hasattr(pd.Timestamp.utcnow(), 'tz') else None)
            if abs((dt - datetime.now(pd.Timestamp.utcnow().tz if hasattr(pd.Timestamp.utcnow(), 'tz') else None)).days) < 7:
                return True
        return False
    except Exception:
        return False


def _check_earnings_ddg(symbol: str) -> bool:
    """Fallback: busca noticias de earnings vía DuckDuckGo."""
    try:
        from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            results = list(ddgs.text(f"{symbol} earnings report", max_results=3))
            for r in results:
                title = r.get("title", "") + " " + r.get("body", "")
                if re.search(r'\b(earnings|results|quarter|Q[1-4]|ganancias|resultados)\b', title, re.I):
                    return True
        return False
    except Exception:
        return False


def clasificar_fuera_bb(df, item):
    """
    Clasifica si un activo fuera de BB(20,2) tiene probabilidad de
    continuación o reversión, basado en volumen, RSI, velas, ATR y niveles.

    Retorna dict con:
      - prediccion: "continuacion" | "reversion" | "incierto"
      - score_continuacion: int (positivo = continuación, negativo = reversión)
      - razones: lista de strings explicativos
    """
    close = df["Close"].astype(float)
    high = df["High"].astype(float)
    low = df["Low"].astype(float)
    volume = df["Volume"].astype(float)
    direccion = item["direccion"]
    banda = item["banda"]
    upper = item["upper"]
    lower = item["lower"]

    score = 0
    razones = []

    # Calcular BB para análisis retrospectivo
    period = 20
    sma = close.rolling(period).mean()
    std = close.rolling(period).std()
    bb_upper = sma + 2.0 * std
    bb_lower = sma - 2.0 * std

    # ── 1. Volumen relativo ──
    vol_avg = volume.tail(20).mean()
    vol_ratio = volume.iloc[-1] / vol_avg if vol_avg > 0 else 0
    if vol_ratio > 2.0:
        score += 2
        razones.append(f"volumen alto ({vol_ratio:.1f}x media)")
    elif vol_ratio < 1.0:
        score -= 1
        razones.append(f"volumen bajo ({vol_ratio:.1f}x media)")

    # ── 2. Velas de reversión ──
    # Buscar martillo, doji, envolvente en las últimas 3 velas
    ultimas = df.tail(3)
    tiene_reversion = False
    for _, row in ultimas.iterrows():
        o, h, l, c_ = row["Open"], row["High"], row["Low"], row["Close"]
        cuerpo = abs(c_ - o)
        sombra_sup = h - max(o, c_)
        sombra_inf = min(o, c_) - l
        if cuerpo > 0:
            # Martillo: sombra inferior >= 2x cuerpo, sombra superior pequeña
            if sombra_inf >= 2 * cuerpo and sombra_sup <= 0.3 * cuerpo:
                tiene_reversion = True
                razones.append("vela martillo detectada")
            # Doji: cuerpo muy pequeño
            if cuerpo / (h - l + 1e-10) < 0.1 and (h - l) > 0:
                tiene_reversion = True
                razones.append("vela doji detectada")
    if tiene_reversion:
        score -= 2
    else:
        score += 1
        razones.append("sin velas de reversión obvias")

    # ── 3. Precio fuera de banda por múltiples velas ──
    velas_fuera = 0
    for _, row in df.tail(10).iterrows():
        c = float(row["Close"])
        if banda == "superior" and c > bb_upper.iloc[-1]:
            velas_fuera += 1
        elif banda == "inferior" and c < bb_lower.iloc[-1]:
            velas_fuera += 1
    if velas_fuera >= 3:
        score += 2
        razones.append(f"precio fuera de BB por {velas_fuera} velas")
    elif velas_fuera == 1:
        score -= 1
        razones.append("precio recién salió de BB (1 vela)")

    # ── 4. Proximidad a niveles clave ──
    if direccion == "compra":
        nivel_soporte = float(low.tail(30).min())
        distancia = (item["precio"] - nivel_soporte) / (item["precio"] + 1e-10) * 100
        if distancia < 2.0:
            score -= 2
            razones.append(f"cerca de soporte ({distancia:.1f}%)")
        elif distancia > 5.0:
            score += 1
            razones.append(f"lejos de soporte ({distancia:.1f}%)")
    else:
        nivel_resistencia = float(high.tail(30).max())
        distancia = (nivel_resistencia - item["precio"]) / (item["precio"] + 1e-10) * 100
        if distancia < 2.0:
            score -= 2
            razones.append(f"cerca de resistencia ({distancia:.1f}%)")
        elif distancia > 5.0:
            score += 1
            razones.append(f"lejos de resistencia ({distancia:.1f}%)")

    # ── 5. ATR expandiéndose ──
    atr = (high - low).rolling(14).mean()
    atr_actual = float(atr.iloc[-1]) if not atr.empty else 0
    atr_anterior = float(atr.iloc[-3]) if len(atr) > 3 else atr_actual
    if atr_anterior > 0 and atr_actual > atr_anterior * 1.1:
        score += 1
        razones.append(f"ATR expandiéndose ({atr_actual:.4f} vs {atr_anterior:.4f})")
    elif atr_anterior > 0 and atr_actual < atr_anterior * 0.9:
        score -= 1
        razones.append(f"ATR contrayéndose")

    # ── 6. Contexto de noticias ──
    if _check_earnings(item["symbol"]):
        score += 1
        razones.append("catalizador (earnings reciente)")

    # Clasificación final
    if score >= 3:
        prediccion = "continuacion"
    elif score <= -3:
        prediccion = "reversion"
    else:
        prediccion = "incierto"

    return {
        "prediccion": prediccion,
        "score_continuacion": score,
        "razones": razones,
        "velas_fuera_bb": velas_fuera,
        "vol_ratio": round(vol_ratio, 2),
    }


def screener_completo(lista_simbolos=None, progress_callback=None):
    """
    Función principal: ejecuta filtro BB + filtros seguros.
    progress_callback(fase, actual, total, mensaje) donde fase es 'bb' o 'filtros'.
    """
    if lista_simbolos is None:
        lista_simbolos = WATCHLIST
    total_original = len(lista_simbolos)

    # Paso 1: filtrar fuera de BB
    def _bb_progress(a, t, s):
        if progress_callback:
            progress_callback("bb", a, t, f"Escaneando {s}...")
    fuera, dentro = filtrar_fuera_bollinger(lista_simbolos, progress_callback=_bb_progress)

    # Paso 2: filtros seguros
    def _filtro_progress(a, t, s):
        if progress_callback:
            progress_callback("filtros", a, t, f"Filtrando {s}...")
    aprobados, descartados = aplicar_filtros_seguros(fuera, progress_callback=_filtro_progress)
    aprobados.sort(key=lambda x: x["score"], reverse=True)

    return {
        "total_escaneadas": total_original,
        "fuera_bollinger": len(fuera),
        "pasaron_filtros": len(aprobados),
        "mejores": aprobados[:10],
        "descartadas": descartados[:30],
        "detalle": aprobados,
    }
