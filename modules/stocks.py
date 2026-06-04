import yfinance as yf
from finvizfinance.quote import finvizfinance
from tradingview_ta import TA_Handler, Interval
from .base import ModuleBase
from utils.emoji import GRAFICO

# Mapa de nombres de empresa -> sÃ­mbolo
EMPRESAS = {
    "apple": "AAPL",
    "microsoft": "MSFT",
    "google": "GOOGL",
    "alphabet": "GOOGL",
    "amazon": "AMZN",
    "tesla": "TSLA",
    "meta": "META",
    "facebook": "META",
    "netflix": "NFLX",
    "nvidia": "NVDA",
    "intel": "INTC",
    "amd": "AMD",
    "ibm": "IBM",
    "oracle": "ORCL",
    "cisco": "CSCO",
    "dell": "DELL",
    "hp": "HPQ",
    "hewlett packard": "HPQ",
    "samsung": "SSNLF",
    "sony": "SONY",
    "panasonic": "PCRFY",
    "twitter": "TWTR",
    "x": "TWTR",
    "snap": "SNAP",
    "snapchat": "SNAP",
    "uber": "UBER",
    "lyft": "LYFT",
    "airbnb": "ABNB",
    "spotify": "SPOT",
    "paypal": "PYPL",
    "square": "SQ",
    "block": "SQ",
    "visa": "V",
    "mastercard": "MA",
    "american express": "AXP",
    "disney": "DIS",
    "walt disney": "DIS",
    "netflix": "NFLX",
    "coca cola": "KO",
    "coca-cola": "KO",
    "pepsi": "PEP",
    "pepsico": "PEP",
    "mcdonalds": "MCD",
    "mcdonald's": "MCD",
    "starbucks": "SBUX",
    "nike": "NKE",
    "adidas": "ADDYY",
    "mercedes": "MBG.DE",
    "mercedes benz": "MBG.DE",
    "bmw": "BMW.DE",
    "volkswagen": "VOW3.DE",
    "vw": "VOW3.DE",
    "porsche": "P911.DE",
    "siemens": "SIE.DE",
    "sap": "SAP.DE",
    "telefonica": "TEF",
    "bbva": "BBVA",
    "santander": "SAN",
    "banco santander": "SAN",
    "repsol": "REP.MC",
    "iberdrola": "IBE.MC",
    "inditex": "ITX.MC",
    "zara": "ITX.MC",
    "mercadolibre": "MELI",
    "mercado libre": "MELI",
    "globant": "GLOB",
    "despegar": "DESP",
    "bitcoin": "BTC-USD",
    "btc": "BTC-USD",
    "ethereum": "ETH-USD",
    "eth": "ETH-USD",
    "dogecoin": "DOGE-USD",
    "doge": "DOGE-USD",
    "cardano": "ADA-USD",
    "ada": "ADA-USD",
    "solana": "SOL-USD",
    "sol": "SOL-USD",
    "ripple": "XRP-USD",
    "xrp": "XRP-USD",
    "binance": "BNB-USD",
    "bnb": "BNB-USD",
    "polygon": "MATIC-USD",
    "matic": "MATIC-USD",
    "chainlink": "LINK-USD",
    "link": "LINK-USD",
}


class StocksModule(ModuleBase):
    """MÃ³dulo de bolsa/mercado de valores - yfinance."""

    def execute(self, command: str, **kwargs) -> str:
        parts = command.lower().split()
        simbolo = kwargs.get("simbolo", "")

        if not simbolo:
            # Buscar DESPUÃS de la palabra clave bolsa/stock/mercado
            idx = None
            for i, p in enumerate(parts):
                if p in ("bolsa", "stock", "accion", "acciones", "mercado",
                         "cotizaciÃ³n", "cotizacion"):
                    idx = i
                    break
            if idx is not None:
                for j in range(idx + 1, len(parts)):
                    if parts[j] not in ("de", "del", "la", "el", "en", "como", "va",
                                        "esta", "esta", "valores", "valor"):
                        simbolo = parts[j].upper()
                        break
            else:
                # Sin palabra clave: buscar nombre de empresa conocido
                entrada = " ".join(parts)
                encontrado = False
                for nombre, ticker in EMPRESAS.items():
                    if nombre in entrada:
                        simbolo = ticker
                        encontrado = True
                        break
                if not encontrado:
                    for p in parts:
                        if p not in ("cotizar", "buscar", "dame", "quiero",
                                     "de", "del", "la", "el", "en", "como",
                                     "va", "estÃ¡", "esta", "cÃ³mo", "precio",
                                     "valor", "cotizacion", "cotizaciÃ³n"):
                            simbolo = p.upper()
                            break

        # Mapear nombre de empresa a sÃ­mbolo
        if simbolo:
            simbolo_lower = simbolo.lower()
            if simbolo_lower in EMPRESAS:
                simbolo = EMPRESAS[simbolo_lower]
            else:
                # TambiÃ©n buscar coincidencias parciales
                for nombre, ticker in EMPRESAS.items():
                    if simbolo_lower in nombre or nombre in simbolo_lower:
                        simbolo = ticker
                        break

        if not simbolo:
            return self.help()

        return self._cotizar(simbolo)

    def _cotizar(self, simbolo: str) -> str:
        try:
            ticker = yf.Ticker(simbolo)
            info = ticker.info

            if not info or not info.get("regularMarketPrice"):
                hist = ticker.history(period="1d")
                if hist.empty:
                    return f"No encontré el símbolo '{simbolo}'. Ejemplos válidos: AAPL, MSFT, GOOGL, TSLA, AMZN."
                precio_actual = hist["Close"].iloc[-1]
                cambio = hist["Close"].iloc[-1] - hist["Open"].iloc[0]
                cambio_pct = (cambio / hist["Open"].iloc[0]) * 100
                nombre = info.get("longName", info.get("shortName", simbolo))
                moneda = info.get("currency", "USD")
            else:
                precio_actual = info["regularMarketPrice"]
                cambio = info.get("regularMarketChange", 0)
                cambio_pct = info.get("regularMarketChangePercent", 0)
                nombre = info.get("longName", info.get("shortName", simbolo))
                moneda = info.get("currency", "USD")

            flecha = chr(9650) if cambio >= 0 else chr(9660)
            signo = "+" if cambio >= 0 else ""

            # ---- TradingView: indicadores técnicos ----
            rsi = None
            recomendacion_tv = "N/A"
            ma_rec = ""
            osc_rec = ""
            try:
                exchange = "NASDAQ"
                if simbolo.endswith(".DE"): exchange = "XETRA"
                elif simbolo.endswith(".MC"): exchange = "MCE"
                elif simbolo.endswith(".MX"): exchange = "MEX"
                elif simbolo.endswith(".SA"): exchange = "BMFBOVESPA"
                elif simbolo.endswith(("-USD", "-BTC")): exchange = "BITSTAMP"

                ta = TA_Handler(
                    symbol=simbolo,
                    screener="america",
                    exchange=exchange,
                    interval=Interval.INTERVAL_1_DAY
                )
                analysis = ta.get_analysis()
                rsi = analysis.indicators.get("RSI")
                ma_rec = analysis.moving_averages.get("RECOMMENDATION", "")
                osc_rec = analysis.oscillators.get("RECOMMENDATION", "")
                recomendacion_tv = analysis.summary.get("RECOMMENDATION", "N/A")
            except Exception:
                pass

            # ---- Análisis y recomendación ----
            recomendacion = "NEUTRAL"
            razones = []
            color_rec = chr(9679)  # black circle

            if rsi is not None:
                if rsi > 70:
                    recomendacion = "SOBRECOMPRA / POSIBLE VENTA"
                    color_rec = chr(9679)  # filled
                    razones.append(f"RSI en {rsi:.1f} (sobrecompra, podria corregir)")
                elif rsi < 30:
                    recomendacion = "SOBREVENTA / POSIBLE COMPRA"
                    color_rec = chr(9679)
                    razones.append(f"RSI en {rsi:.1f} (sobreventa, podria rebotar)")
                else:
                    razones.append(f"RSI en {rsi:.1f} (rango neutral, sin senial clara)")

            if info.get("fiftyTwoWeekHigh") and precio_actual:
                pct_high = (precio_actual / info["fiftyTwoWeekHigh"]) * 100
                if pct_high > 95:
                    razones.append(f"Cerca del maximo 52 sem ({pct_high:.0f}%) - posible resistencia")
                elif pct_high < 60:
                    razones.append(f"Lejos del maximo 52 sem ({pct_high:.0f}%) - posible soporte")

            if abs(cambio_pct) > 3:
                razones.append(f"Movimiento fuerte: {signo}{cambio_pct:.2f}% en el dia")

            if recomendacion_tv == "BUY":
                razones.append("TradingView recomienda COMPRA")
            elif recomendacion_tv == "SELL":
                razones.append("TradingView recomienda VENTA")

            # ---- Construir respuesta ----
            resultado = (
                f"  {chr(128200)}  {nombre} ({simbolo})\n"
                f"  {'='*25}\n"
                f"  Precio: {moneda} {precio_actual:.2f} {flecha} {signo}{cambio:.2f} ({signo}{cambio_pct:.2f}%)\n"
            )

            if info.get("marketCap"):
                cap = info["marketCap"]
                cap_str = f"${cap/1e9:.2f}B" if cap > 1e9 else f"${cap/1e6:.2f}M"
                resultado += f"  Cap. Mercado: {cap_str}\n"
            if info.get("fiftyTwoWeekHigh"):
                resultado += f"  Max 52 sem: {moneda} {info['fiftyTwoWeekHigh']:.2f}\n"
            if info.get("fiftyTwoWeekLow"):
                resultado += f"  Min 52 sem: {moneda} {info['fiftyTwoWeekLow']:.2f}\n"
            if info.get("volume"):
                resultado += f"  Volumen: {info['volume']:,}\n"
            if info.get("averageVolume"):
                resultado += f"  Vol. Promedio: {info['averageVolume']:,}\n"

            # ---- Fundamentos ----
            try:
                fv = finvizfinance(simbolo)
                fund = fv.ticker_fundament()
                if fund:
                    parts = []
                    for k in ("P/E", "Forward P/E", "EPS (ttm)", "PEG", "Debt/Eq", "ROI", "Beta"):
                        v = fund.get(k)
                        if v:
                            parts.append(f"{k}: {v}")
                    if parts:
                        resultado += f"  Fundamentos: {' | '.join(parts[:5])}\n"
            except Exception:
                pass

            # ---- TradingView ----
            if rsi is not None:
                resultado += f"  RSI: {rsi:.1f} | MA: {ma_rec} | Osc: {osc_rec} | TV: {recomendacion_tv}\n"

            # ---- Analisis y recomendacion ----
            resultado += f"\n  {chr(128200)} ANALISIS:\n"
            for r in razones:
                resultado += f"    {chr(8226)} {r}\n"

            resultado += f"\n  {color_rec} RECOMENDACION: {recomendacion}\n"

            return resultado

        except ImportError as e:
            return f"Paquete faltante: {e}. Ejecuta: pip install yfinance finvizfinance tradingview-ta"
        except Exception as e:
            return f"Error obteniendo cotizacion: {e}"

    def help(self) -> str:
        return (
            "Uso: bolsa <sÃ­mbolo>\n"
            "Ej:  bolsa AAPL     (Apple)\n"
            "     bolsa MSFT     (Microsoft)\n"
            "     bolsa GOOGL    (Google)\n"
            "     bolsa TSLA     (Tesla)\n"
            "     bolsa AMZN     (Amazon)\n"
            "     bolsa BTC-USD  (Bitcoin)\n"
            "     bolsa MELI     (Mercado Libre)\n\n"
            "SÃ­mbolos internacionales: <SIMBOLO>.MX (MÃ©xico), <SIMBOLO>.SA (Brasil)\n"
            "Ej: bolsa WALMEX.MX"
        )

