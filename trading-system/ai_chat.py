import re, math
from typing import Dict, List, Optional, Tuple

GROUP_NAMES = {
    "ict": "ICT / Smart Money", "momentum": "Momento + RSI",
    "trend": "Tendencia", "volatility": "Volatilidad (BB+ATR)",
    "volume": "Volumen Inteligente", "mean_reversion": "Reversion (VWAP)",
    "price_action": "Price Action", "structure": "S/R y Estructura",
    "yoel": "Yoel Sardinas (OTE+BB)", "webull": "Webull Quant"
}

GROUP_DESCRIPTIONS = {
    "ict": "Evalua FVG, Order Blocks, BOS, CHoCH, Liquidez, Power of Three y sesiones.",
    "momentum": "Divergencias RSI, cruces MACD y aceleracion del momentum.",
    "trend": "Alineacion de EMAs (9/21/50) y fuerza de tendencia con ADX.",
    "volatility": "Expansion de volatilidad y squeezes de Bollinger Bands con direccion.",
    "volume": "Confirmacion de volumen, OBV y volumen de apertura de NY.",
    "mean_reversion": "Posicion del precio respecto a VWAP.",
    "price_action": "Patrones de velas, comparacion intradia y lectura de vela diaria.",
    "structure": "Soportes/resistencias dinamicos, maximos/minimos crecientes.",
    "yoel": "Squeeze de Bollinger, zonas OTE con Fibonacci, tendencia EMA, volumen+PA y RSI+BB.",
    "webull": "Senales cuantitativas de momentum, estructura tecnica y riesgo/sentimiento."
}

EDUCATION = {
    "ote": (
        "<b>OTE (Optimal Trade Entry)</b> - Zona de entrada optima basada en retrocesos de Fibonacci. "
        "Para COMPRAS se busca entre 50%-78.6% del movimiento bajista previo (min 0.5x ATR). "
        "Para VENTAS se busca entre 23.6%-50% del movimiento alcista previo. "
        "La zona OTE ofrece la mejor relacion riesgo:reward."
    ),
    "fvg": (
        "<b>FVG (Fair Value Gap)</b> - Desequilibrio de precios entre 3 velas consecutivas "
        "cuando la vela del medio no solapa completamente con las vecinas. "
        "Indica zonas de liquidez pendiente que el precio tiende a rellenar."
    ),
    "bb": (
        "<b>Bollinger Bands</b> - Bandas de volatilidad alrededor de una media movil (20 periodos). "
        "El precio tiende a rebotar entre las bandas. Sobre compra cerca de banda superior, "
        "sobre venta cerca de inferior. Squeeze precede a movimientos fuertes."
    ),
    "rsi": (
        "<b>RSI (Relative Strength Index)</b> - Oscilador 0-100 que mide velocidad de cambios. "
        ">70 = sobrecompra (posible venta), <30 = sobreventa (posible compra). "
        "Divergencias entre RSI y precio son senales fuertes de reversion."
    ),
    "ict": (
        "<b>ICT / Smart Money Concepts</b> - Metodologia que analiza la manipulacion institucional. "
        "Conceptos clave: FVG (desequilibrios), Order Blocks, BOS/CHoCH, "
        "Liquidity Sweeps, Power of Three y sesiones de mercado."
    ),
    "composite": (
        "<b>Estrategia Compuesta</b> - Grupo de micro-estrategias que votan en conjunto. "
        "Cada composite agrupa 2-10 micros del mismo enfoque (ICT, Momentum, etc.). "
        "La senal final se determina por mayoria ponderada segun la confianza de cada micro."
    ),
    "micro": (
        "<b>Micro-Estrategia</b> - Estrategia individual que analiza un aspecto concreto "
        "(ej: FVG detecta desequilibrios, RSI Flash busca cruces rapidos). "
        "Cada micro vota COMPRA, VENTA o ESPERA con confianza 0-100%."
    ),
}


class TradingAssistant:
    def __init__(self, rt_engine=None, scanner=None, data_provider=None):
        self.rt_engine = rt_engine
        self.scanner = scanner
        self.data_provider = data_provider

    def _ctx(self, symbol: str) -> dict:
        ctx = {"symbol": symbol, "price": None, "action": "hold", "confidence": 0, "score": 0,
               "groups": {}, "composites": [], "prediction": {}, "ote_zones": [],
               "micro_total": 0, "candles": [], "scanner_result": None}
        snapshot = None
        if self.rt_engine:
            try:
                snapshot = self.rt_engine.get_snapshot()
            except Exception:
                snapshot = {}
        if snapshot and symbol in snapshot:
            d = snapshot[symbol]
            ctx.update({
                "symbol": symbol,
                "price": d.get("price"),
                "action": d.get("action", "hold"),
                "confidence": d.get("confidence", 0),
                "score": d.get("score", 0),
                "groups": d.get("groups", {}),
                "composites": d.get("composites", []),
                "prediction": d.get("prediction", {}),
                "ote_zones": d.get("ote_zones", []),
                "micro_total": d.get("micro_total", 0),
                "candles": d.get("candles", []),
            })
        if self.scanner:
            try:
                results = self.scanner.get_results(min_conf=0, max_results=500)
                for r in results:
                    if r.get("symbol") == symbol:
                        ctx["scanner_result"] = r
                        break
            except Exception:
                pass
        return ctx

    def chat(self, symbol: str, question: str, history: List[dict] = None) -> dict:
        ctx = self._ctx(symbol)
        q = question.strip()
        q_lower = q.lower()
        qtype = self._classify(q_lower, ctx)
        if qtype == "whatif":
            answer = self._answer_whatif(ctx, q)
        elif qtype == "strategy":
            answer = self._answer_strategy(ctx, q)
        elif qtype == "market":
            answer = self._answer_market(ctx, q)
        elif qtype == "risk":
            answer = self._answer_risk(ctx, q)
        elif qtype == "education":
            answer = self._answer_education(ctx, q)
        elif qtype == "compare":
            answer = self._answer_compare(ctx, q)
        else:
            answer = self._answer_general(ctx, q)
        quick = self._quick_questions(ctx, qtype)
        return {"type": qtype, "message": answer, "quick_questions": quick[:5]}

    def _classify(self, q: str, ctx: dict) -> str:
        whatif_words = ["si entro", "si pongo", "si muevo", "si cambio", "que tal si",
                        "what if", "si uso", "si arriesgo", "si en vez", "en lugar de",
                        "si meto", "si compro a", "si vendo a", "si el stop", "si el sl",
                        "diferente entrada", "alternativo", "otro precio", "y si"]
        strategy_words = ["por que", "por que", "explica", "explain", "que significa",
                          "cual es el motivo", "cual es la razon", "fundamento",
                          "en que se basa", "como funciona", "senal", "signal",
                          "composite", "micro", "porque"]
        market_words = ["tendencia", "trend", "fuerza", "volumen", "volume", "momentum",
                        "bb", "bollinger", "rsi", "soporte", "resistencia",
                        "direccion", "esta fuerte", "esta debil", "esta debil",
                        "mercado", "volatilidad", "fvg", "ob", "order block",
                        "estructura", "structure"]
        risk_words = ["riesgo", "risk", "posicion", "posicion", "size", "tamano",
                      "capital", "cuanto arriesgo", "que porcentaje", "porcentaje",
                      "money management", "gestion", "gestion", "sl", "stop loss",
                      "take profit", "tp", "r:r", "rr", "reward"]
        education_words = ["que es", "que es", "que son", "que son",
                           "definicion", "definime", "explicame",
                           "que significa", "que significa", "diferencia entre",
                           "aprender", "educacion", "educacion"]
        compare_words = ["compara", "comparado", "vs", "versus", "mejor que",
                         "peor que", "diferencia con", "cual es mejor"]

        for w in education_words:
            if w in q:
                return "education"
        for w in whatif_words:
            if w in q:
                if re.search(r'\d+\.?\d*', q):
                    return "whatif"
        for w in compare_words:
            if w in q:
                return "compare"
        for w in risk_words:
            if w in q:
                return "risk"
        for w in strategy_words:
            if w in q:
                return "strategy"
        for w in market_words:
            if w in q:
                return "market"
        return "general"

    def _numbers(self, q: str) -> List[float]:
        return [float(x) for x in re.findall(r'\d+\.?\d*', q)]

    def _is_bullish(self, ctx: dict) -> bool:
        return ctx.get("action") == "buy"

    def _ote_str(self, ctx: dict) -> str:
        zones = ctx.get("ote_zones", [])
        if not zones:
            return ""
        z = zones[0]
        d = z.get("direction", "buy")
        rr = z.get("rr_ratio", 0)
        score = z.get("confluence_score", 0)
        strength = z.get("strength_label", "")
        return (f"<b>Zona OTE {d.upper()}</b> - {strength} ({score}/100)<br>"
                f"Entrada: ${z.get('entry_min',0):.2f}-${z.get('entry_max',0):.2f}<br>"
                f"SL: ${z.get('stop_loss',0):.2f} | TP1: ${z.get('tp1',0):.2f}<br>"
                f"R:R {rr:.1f}:1")

    def _comp_summary(self, ctx: dict) -> str:
        comps = ctx.get("composites", [])
        if not comps:
            return "Sin datos de composites."
        buy = sum(1 for c in comps if c.get("a") == "buy")
        sell = sum(1 for c in comps if c.get("a") == "sell")
        total = len(comps)
        lines = [f"<b>{buy}/{total}</b> alcistas, <b>{sell}/{total}</b> bajistas:"]
        for c in comps[:5]:
            n = c.get("n", "?")
            a = c.get("a", "hold")
            conf = c.get("c", 0)
            icon = "+" if a == "buy" else ("-" if a == "sell" else "o")
            lines.append(f"  {icon} {n} ({a.upper()}, {conf:.0%} confianza)")
        return "<br>".join(lines)

    def _bb_info(self, ctx: dict) -> str:
        candles = ctx.get("candles", [])
        if not candles:
            return "Sin datos de velas."
        last = candles[-1]
        bb_h, bb_m, bb_l = last.get("bb_h"), last.get("bb_m"), last.get("bb_l")
        if bb_h is None or bb_l is None:
            return "BB no disponible."
        pos = (last["c"] - bb_l) / (bb_h - bb_l)
        band = "superior" if pos > 0.8 else ("inferior" if pos < 0.2 else "media")
        return (f"Precio ${last['c']:.2f}, BB {band} (posicion {pos:.1%}). "
                f"Banda sup: ${bb_h:.2f}, media: ${bb_m:.2f}, inf: ${bb_l:.2f}.")

    def _pred_info(self, ctx: dict) -> str:
        p = ctx.get("prediction", {})
        if not p or not p.get("direction"):
            return ""
        d = p["direction"]
        conf = p.get("confidence", 0) * 100
        score = p.get("confluence_score", 0)
        reason = p.get("reason", "")
        label = {"up": "ALCISTA", "down": "BAJISTA", "sideways": "LATERAL"}.get(d, d.upper())
        out = f"Prediccion Yoel: <b>{label}</b> ({conf:.0f}% confianza, score {score}/100)"
        if reason:
            out += f" - {reason}"
        t1, t2, t3 = p.get("target_1"), p.get("target_2"), p.get("target_3")
        sl = p.get("stop_loss")
        targets = []
        if t1: targets.append(f"TP1 ${t1:.2f}")
        if t2: targets.append(f"TP2 ${t2:.2f}")
        if t3: targets.append(f"TP3 ${t3:.2f}")
        if targets:
            out += "<br>Objetivos: " + ", ".join(targets)
        if sl:
            out += f" | SL: ${sl:.2f}"
        return out

    def _group_scores_str(self, ctx: dict) -> Tuple[List[str], List[str]]:
        grp = ctx.get("groups", {})
        bull, bear = [], []
        for k, v in sorted(grp.items(), key=lambda x: abs(x[1]), reverse=True):
            name = GROUP_NAMES.get(k, k)
            if v > 0.01:
                bull.append(f"{name} (+{v:.1f})")
            elif v < -0.01:
                bear.append(f"{name} ({v:.1f})")
        return bull, bear

    def _answer_strategy(self, ctx: dict, q: str) -> str:
        sym = ctx["symbol"]
        act = ctx.get("action", "hold")
        conf = ctx.get("confidence", 0)
        score = ctx.get("score", 0)
        micro = ctx.get("micro_total", 0)
        comps = ctx.get("composites", [])
        bull_grp, bear_grp = self._group_scores_str(ctx)
        bb_info = self._bb_info(ctx)
        pred = self._pred_info(ctx)
        for key, name in GROUP_NAMES.items():
            if key in q.lower() or name.lower() in q.lower():
                desc = GROUP_DESCRIPTIONS.get(key, "")
                grp_score = ctx.get("groups", {}).get(key, 0)
                dir_str = "alcista (+)" if grp_score > 0 else ("bajista (-)" if grp_score < 0 else "neutral")
                return (
                    f"<b>{name}</b> - {desc}<br><br>"
                    f"Senal actual: <b>{dir_str}</b> (score {grp_score:+.1f}).<br>"
                    f"Incluye micro-estrategias en este enfoque."
                )
        if act == "buy":
            lines = [
                f"<b>{sym}: Senal de COMPRA</b> con {conf:.0%} de confianza.<br>",
                f"<b>Confluencia:</b> {self._comp_summary(ctx)}<br>",
            ]
            if bull_grp:
                lines.append(f"<b>Impulsores alcistas:</b><br>" + "<br>".join(f"  [+] {g}" for g in bull_grp[:3]))
            if bear_grp:
                lines.append(f"<b>En contra:</b><br>" + "<br>".join(f"  [!] {g}" for g in bear_grp[:2]))
            if bb_info:
                lines.append(f"<b>BB:</b> {bb_info}")
            if pred:
                lines.append(f"<b>Prediccion:</b> {pred}")
            if micro:
                lines.append(f"<br>De <b>{micro}</b> micro-senales en total.")
        elif act == "sell":
            lines = [
                f"<b>{sym}: Senal de VENTA</b> con {conf:.0%} de confianza.<br>",
                f"<b>Confluencia:</b> {self._comp_summary(ctx)}<br>",
            ]
            if bear_grp:
                lines.append(f"<b>Presion bajista:</b><br>" + "<br>".join(f"  [-] {g}" for g in bear_grp[:3]))
            if bull_grp:
                lines.append(f"<b>En contra:</b><br>" + "<br>".join(f"  [!] {g}" for g in bull_grp[:2]))
            if bb_info:
                lines.append(f"<b>BB:</b> {bb_info}")
            if pred:
                lines.append(f"<b>Prediccion:</b> {pred}")
        else:
            lines = [
                f"<b>{sym}: Sin senal clara</b> (score {score:.2f}).<br>",
                "Las estrategias estan divididas o con baja conviccion."
            ]
            if bull_grp:
                lines.append(f"<b>Alcistas:</b> " + ", ".join(bull_grp[:2]))
            if bear_grp:
                lines.append(f"<b>Bajistas:</b> " + ", ".join(bear_grp[:2]))
            lines.append("<br>[*] Sugerencia: espera a que se forme una senal mas definida o cambia de timeframe.")
        return "<br>".join(lines)

    def _answer_whatif(self, ctx: dict, q: str) -> str:
        nums = self._numbers(q)
        sym = ctx["symbol"]
        price_data = ctx.get("price", {})
        current_price = price_data.get("price") if price_data else None
        if not current_price:
            candles = ctx.get("candles", [])
            if candles:
                current_price = candles[-1]["c"]
        if not current_price:
            return "No tengo datos de precio para analizar este escenario."
        zones = ctx.get("ote_zones", [])
        zone = zones[0] if zones else None
        entry_match = re.search(r'(?:entr[oa](?:\s+a)?|compro(?:\s+a)?|vendo(?:\s+a)?|a\s+precio\s+de|price\s+of|entry\s+at)\s+(\d+\.?\d*)', q, re.I)
        sl_match = re.search(r'(?:stop|sl|stop loss)\s+(?:en\s+|a\s+|de\s+|at\s+)?(\d+\.?\d*)', q, re.I)
        tp_match = re.search(r'(?:tp|take profit|take-profit)\s+(?:en\s+|a\s+|de\s+)?(\d+\.?\d*)', q, re.I)
        risk_match = re.search(r'(?:riesgo|risk|arriesgo)\s+(?:de\s+)?(\d+\.?\d*)\s*%?', q, re.I)
        entry = float(entry_match.group(1)) if entry_match else None
        sl_input = float(sl_match.group(1)) if sl_match else None
        tp_input = float(tp_match.group(1)) if tp_match else None
        risk_pct = float(risk_match.group(1)) if risk_match else None
        # Fallback: if entry not matched but there are numbers, use first price-like number
        if not entry and len(nums) > 0:
            for n in nums:
                if (tp_input is None or n != tp_input) and (sl_input is None or n != sl_input) and (risk_pct is None or n != risk_pct):
                    entry = n
                    break
        if not entry:
            if zone:
                entry = (zone.get("entry_min", 0) + zone.get("entry_max", 0)) / 2
            else:
                entry = current_price
        is_buy = self._is_bullish(ctx)
        if zone:
            is_buy = zone.get("direction") == "buy"
        if not sl_input:
            if zone and zone.get("stop_loss"):
                sl_input = zone["stop_loss"]
            else:
                sl_input = entry * 0.95 if is_buy else entry * 1.05
        risk_per_share = abs(entry - sl_input)
        if risk_per_share < 0.01:
            return "La distancia entre entrada y SL es practicamente cero. Revisa los valores."
        asking_rr = any(w in q for w in ["r:r", "rr", "reward", "relacion", "relacion", "ratio"])
        if not tp_input and zone:
            tp_input = zone.get("tp1")
        if not tp_input:
            pred = ctx.get("prediction", {})
            tp_input = pred.get("target_1")
        if not tp_input:
            tp_input = entry * 1.05 if is_buy else entry * 0.95
        reward_per_share = abs(tp_input - entry) if tp_input else 0
        rr = reward_per_share / risk_per_share if risk_per_share > 0 else 0
        capital = 10000
        risk_pct_used = risk_pct if risk_pct else 1.0
        risk_amount = capital * risk_pct_used / 100
        shares = int(risk_amount / risk_per_share) if risk_per_share > 0 else 0
        actual_risk = shares * risk_per_share
        lines = [
            f"<b>Analisis del escenario - {sym}</b><br>",
            f"<b>Entrada:</b> ${entry:.2f}",
            f"<b>Stop Loss:</b> ${sl_input:.2f}",
        ]
        if tp_input:
            lines.append(f"<b>TP:</b> ${tp_input:.2f}")
        if risk_pct:
            lines.append(f"<b>Riesgo:</b> {risk_pct}% del capital")
        lines.append("<br>--- <b>Resultados</b> ---")
        lines.append(f"<b>Riesgo por accion:</b> ${risk_per_share:.2f} ({risk_per_share/entry*100:.1f}% del precio)")
        if reward_per_share > 0:
            lines.append(f"<b>Recompensa por accion:</b> ${reward_per_share:.2f} ({reward_per_share/entry*100:.1f}%)")
            label = "[OK]" if rr >= 2 else ("[--]" if rr >= 1 else "[NO]")
            lines.append(f"{label} <b>R:R:</b> {rr:.2f}:1")
            if rr < 1:
                lines.append("[!] Relacion riesgo:reward negativa. No recomendado.")
            elif rr < 2:
                lines.append("[i] R:R aceptable, busca al menos 2:1 en lo ideal.")
            else:
                lines.append("[OK] Excelente relacion riesgo:reward!")
        if risk_pct:
            lines.append(f"<br><b>Si tu capital es ${capital:.0f}:</b>")
            lines.append(f"  {risk_pct_used}% = ${risk_amount:.0f} de riesgo maximo")
            lines.append(f"  Puedes tomar <b>{shares} acciones</b>")
            lines.append(f"  Perdida maxima: <b>${actual_risk:.0f}</b>")
        if zone:
            z_entry = (zone.get("entry_min", 0) + zone.get("entry_max", 0)) / 2
            z_sl = zone.get("stop_loss", 0)
            z_rr = zone.get("rr_ratio", 0)
            z_score = zone.get("confluence_score", 0)
            lines.append(f"<br>--- <b>Comparativa vs OTE</b> ---")
            lines.append(f"OTE sugiere entrada en ${z_entry:.2f}, SL ${z_sl:.2f}, R:R {z_rr:.1f}:1 (confianza {z_score}/100).")
            if abs(entry - z_entry) / entry > 0.02:
                lines.append(f"[!] Tu entrada esta a {abs(entry-z_entry)/entry*100:.1f}% del OTE.")
                if is_buy and entry > z_entry:
                    lines.append("Comprando mas CARO que la zona OTE - reduces potencial.")
                elif not is_buy and entry < z_entry:
                    lines.append("Vendiendo mas BARATO que la zona OTE - reduces potencial.")
        return "<br>".join(lines)

    def _answer_market(self, ctx: dict, q: str) -> str:
        sym = ctx["symbol"]
        price_data = ctx.get("price", {})
        price = price_data.get("price") if price_data else None
        change = price_data.get("change") if price_data else None
        candles = ctx.get("candles", [])
        grp = ctx.get("groups", {})
        bb_info = self._bb_info(ctx)
        pred = self._pred_info(ctx)
        lines = [f"<b>Analisis de mercado - {sym}</b>"]
        if price is not None:
            chg_str = f"{change:+.2f}%" if change is not None else ""
            lines.append(f"Precio: <b>${price:.2f}</b> {chg_str}")
        if bb_info:
            lines.append(f"<b>BB:</b> {bb_info}")
        if any(w in q for w in ["volumen", "volume"]):
            if candles and len(candles) > 0:
                vol_ratio = candles[-1].get("volume_ratio") if len(candles) > 0 else None
                if vol_ratio:
                    vol_str = f"Volumen: ratio {vol_ratio:.1f}x " + ("(elevado [+])" if vol_ratio > 1.5 else "(normal)")
                    lines.append(vol_str)
                elif price_data and price_data.get("volume"):
                    lines.append(f"Volumen: {price_data['volume']:,}")
        if any(w in q for w in ["tendencia", "trend", "fuerza"]):
            trend_score = grp.get("trend", 0)
            if trend_score:
                dir_str = "alcista [+]" if trend_score > 0 else "bajista [-]"
                lines.append(f"<b>Tendencia:</b> Senal {dir_str} (score {trend_score:+.1f})")
        if any(w in q for w in ["soporte", "resistencia", "structure", "estructura"]):
            struct_score = grp.get("structure", 0)
            if struct_score:
                lines.append(f"<b>S/R:</b> Score {struct_score:+.1f} " +
                            ("(soportes sosteniendo)" if struct_score > 0 else "(resistencias presionando)"))
        if any(w in q for w in ["fvg"]):
            scanner_r = ctx.get("scanner_result", {})
            fvg_bull = scanner_r.get("fvg_bullish", False)
            fvg_bear = scanner_r.get("fvg_bearish", False)
            if fvg_bull:
                lines.append("[+] <b>FVG alcista</b> detectado - posible relleno al alza.")
            if fvg_bear:
                lines.append("[-] <b>FVG bajista</b> detectado - posible relleno a la baja.")
        if pred:
            lines.append(f"<b>Prediccion Yoel:</b> {pred}")
        lines.append("<br>--- <b>Resumen</b> ---")
        bull_g, bear_g = self._group_scores_str(ctx)
        if bull_g:
            lines.append("[+] " + " | ".join(bull_g[:2]))
        if bear_g:
            lines.append("[-] " + " | ".join(bear_g[:2]))
        return "<br>".join(lines)

    def _answer_risk(self, ctx: dict, q: str) -> str:
        sym = ctx["symbol"]
        nums = self._numbers(q)
        price_data = ctx.get("price", {})
        current_price = price_data.get("price") if price_data else None
        if not current_price:
            candles = ctx.get("candles", [])
            if candles:
                current_price = candles[-1]["c"]
        if not current_price:
            return "No tengo precio para calcular riesgo."
        zones = ctx.get("ote_zones", [])
        zone = zones[0] if zones else None
        cap = 10000
        risk_pct = 1.0
        for n in nums:
            if 100 <= n <= 1000000:
                cap = n
        risk_match = re.search(r'(\d+\.?\d*)\s*%', q)
        if risk_match:
            risk_pct = float(risk_match.group(1))
        sl = None
        if zone and zone.get("stop_loss"):
            sl = zone["stop_loss"]
        sl_match = re.search(r'(?:stop|sl)\s+(?:en|a|de)?\s*(\d+\.?\d*)', q, re.I)
        if sl_match:
            sl = float(sl_match.group(1))
        if not sl:
            sl = current_price * 0.95
        entry = current_price
        is_buy = self._is_bullish(ctx) or (zone and zone.get("direction") == "buy")
        risk_per_share = abs(entry - sl)
        if risk_per_share < 0.01:
            return "El stop loss esta demasiado cerca de la entrada."
        risk_amount = cap * risk_pct / 100
        shares = int(risk_amount / risk_per_share) if risk_per_share > 0 else 0
        actual_risk = shares * risk_per_share
        tp = zone.get("tp1") if zone else None
        if not tp:
            tp = ctx.get("prediction", {}).get("target_1")
        reward_per_share = abs(tp - entry) if tp else 0
        rr = reward_per_share / risk_per_share if risk_per_share > 0 else 0
        lines = [
            f"<b>Gestion de Riesgo - {sym}</b><br>",
            f"Precio actual: <b>${entry:.2f}</b>",
            f"Stop Loss: <b>${sl:.2f}</b>",
            f"Riesgo por accion: <b>${risk_per_share:.2f}</b> ({risk_per_share/entry*100:.1f}%)<br>",
            f"Capital: <b>${cap:.0f}</b>",
            f"Riesgo por trade: <b>{risk_pct}%</b> = ${risk_amount:.0f}<br>",
        ]
        if risk_per_share > 0:
            lines.append(f"<b>Tamano de posicion:</b> <b>{shares} acciones</b>")
            lines.append(f"Inversion total: <b>${shares * entry:.0f}</b>")
            lines.append(f"Perdida maxima: <b>${actual_risk:.0f}</b> ({actual_risk/cap*100:.1f}% del capital)")
        if tp:
            lines.append(f"<br><b>TP sugerido:</b> ${tp:.2f} -> beneficio ${reward_per_share:.2f}/accion")
            rr_label = "[OK]" if rr >= 2 else ("[--]" if rr >= 1 else "[NO]")
            lines.append(f"<b>R:R:</b> {rr:.2f}:1 {rr_label}")
        lines.append("<br>--- <b>Recomendaciones</b> ---")
        if rr < 1.5:
            lines.append("[!] R:R baja. Considera ajustar SL o buscar mejor entrada.")
        else:
            lines.append("[OK] R:R saludable.")
        if actual_risk / cap > 0.03:
            lines.append("[!] Riesgo >3% del capital. Reduce tamano.")
        elif actual_risk / cap < 0.005:
            lines.append("[i] Riesgo conservador (<0.5%). Bien gestionado.")
        if zone:
            lines.append(f"<br>[*] OTE sugiere R:R {zone.get('rr_ratio',0):.1f}:1 con score {zone.get('confluence_score',0)}/100.")
        return "<br>".join(lines)

    def _answer_education(self, ctx: dict, q: str) -> str:
        q_lower = q.lower()
        for key, text in EDUCATION.items():
            if key in q_lower or key.replace("_", " ") in q_lower:
                return f"{text}<br><br>[*] Preguntame tambien sobre OTE, FVG, BB, RSI, ICT, composites o micro-estrategias."
        if any(w in q_lower for w in ["composite", "compuesta"]):
            key = "composite"
        elif any(w in q_lower for w in ["micro"]):
            key = "micro"
        elif any(w in q_lower for w in ["ote"]):
            key = "ote"
        elif any(w in q_lower for w in ["fvg", "fair value"]):
            key = "fvg"
        elif any(w in q_lower for w in ["bollinger", "bb "]):
            key = "bb"
        elif any(w in q_lower for w in ["rsi"]):
            key = "rsi"
        elif any(w in q_lower for w in ["ict", "smart money"]):
            key = "ict"
        else:
            return ("Puedo explicarte conceptos: <b>OTE</b>, <b>FVG</b>, "
                    "<b>Bollinger Bands</b>, <b>RSI</b>, <b>ICT/Smart Money</b>, "
                    "<b>Estrategias Compuestas</b> y <b>Micro-Estrategias</b>.<br><br>"
                    "Sobre que concepto quieres aprender?")
        text = EDUCATION.get(key, "")
        return f"{text}<br><br>[*] Quieres saber mas? Preguntame sobre otro concepto."

    def _answer_compare(self, ctx: dict, q: str) -> str:
        sym = ctx["symbol"]
        act = ctx.get("action", "hold")
        conf = ctx.get("confidence", 0)
        comps = ctx.get("composites", [])
        grp = ctx.get("groups", {})
        all_symbols = []
        if self.scanner:
            try:
                results = self.scanner.get_results(min_conf=0, max_results=500)
                all_symbols = results
            except Exception:
                pass
        other_sym = None
        for r in all_symbols:
            s = r.get("symbol", "")
            if s != sym and s.upper() in q.upper():
                other_sym = s
                break
        lines = [f"<b>Comparativa - {sym}</b>"]
        if other_sym:
            other_data = None
            for r in all_symbols:
                if r.get("symbol") == other_sym:
                    other_data = r
                    break
            if other_data:
                o_act = other_data.get("action", "")
                o_conf = other_data.get("confidence", 0)
                lines.append(f"<b>{sym}:</b> {act.upper()} {conf:.0%}")
                lines.append(f"<b>{other_sym}:</b> {o_act.upper()} {o_conf:.0%}")
                o_score = other_data.get("net_score", 0)
                t_score = ctx.get("score", 0)
                if t_score > o_score:
                    lines.append(f"[+] {sym} tiene mejor score ({t_score:.2f} vs {o_score:.2f})")
                elif t_score < o_score:
                    lines.append(f"[-] {other_sym} tiene mejor score ({o_score:.2f} vs {t_score:.2f})")
                else:
                    lines.append("[i] Scores similares.")
            else:
                lines.append(f"No tengo datos completos de {other_sym}.")
        else:
            lines.append(f"Senal actual: <b>{act.upper()}</b> con {conf:.0%} de confianza.")
            bull_g, bear_g = self._group_scores_str(ctx)
            if bull_g or bear_g:
                lines.append("<br><b>Fuerzas a favor:</b>")
                for g in bull_g[:3]:
                    lines.append(f"  [+] {g}")
                lines.append("<br><b>Fuerzas en contra:</b>")
                for g in bear_g[:3]:
                    lines.append(f"  [-] {g}")
            if conf > 0.6:
                lines.append("<br>[+] Senal fuerte - buena conviccion direccional.")
            elif conf > 0.3:
                lines.append("[-] Senal moderada - espera confirmacion adicional.")
            else:
                lines.append("[!] Senal debil - riesgo de falsa ruptura.")
        return "<br>".join(lines)

    def _answer_general(self, ctx: dict, q: str) -> str:
        sym = ctx["symbol"]
        act = ctx.get("action", "hold")
        conf = ctx.get("confidence", 0)
        ote = self._ote_str(ctx)
        pred = self._pred_info(ctx)
        bull_g, bear_g = self._group_scores_str(ctx)
        lines = [
            f"<b>Asistente de Trading - {sym}</b><br>",
        ]
        if any(w in q.lower() for w in ["hola", "buenas", "hey"]):
            lines.append(f"Hola! Estoy aqui para ayudarte con {sym}.")
            lines.append(f"La senal actual es <b>{act.upper()}</b> con {conf:.0%} de confianza.")
        elif any(w in q.lower() for w in ["que hago", "que hacer", "trade", "operar"]):
            if act == "buy":
                lines.append(f"La senal indica <b>COMPRA</b> con {conf:.0%} de confianza. "
                            "Si coincides, busca entrada en zona OTE.")
            elif act == "sell":
                lines.append(f"La senal indica <b>VENTA</b> con {conf:.0%} de confianza. "
                            "Si coincides, busca entrada en zona OTE bajista.")
            else:
                lines.append("No hay senal clara. Mejor esperar.")
            if ote:
                lines.append(f"<br>{ote}")
            if bull_g or bear_g:
                lines.append("<br><b>Resumen de fuerzas:</b>")
                if bull_g:
                    lines.append("[+] " + " | ".join(bull_g[:3]))
                if bear_g:
                    lines.append("[-] " + " | ".join(bear_g[:3]))
        elif "gracias" in q.lower():
            lines.append("De nada! Estoy para ayudarte. Puedes preguntar:")
            lines.append(f"  \"Por que {sym} da {act.upper()}?\"")
            lines.append("  \"Que tal si entro a otro precio?\"")
            lines.append("  \"Como esta el mercado?\"")
            lines.append("  \"Que posicion tomar?\"")
        else:
            lines.append(f"Senal actual: <b>{act.upper()}</b> con {conf:.0%} de confianza.<br>")
            if bull_g or bear_g:
                lines.append("<b>Resumen:</b>")
                if bull_g:
                    lines.append("[+] " + " | ".join(bull_g[:3]))
                if bear_g:
                    lines.append("[-] " + " | ".join(bear_g[:3]))
            if pred:
                lines.append(f"<br>{pred}")
            if ote:
                lines.append(f"<br>{ote}")
            lines.append(f"<br>[*] Preguntame: que hacer?, por que esta senal?, "
                        "que tal si cambio el entry?, como gestionar riesgo?, "
                        "o conceptos OTE, FVG, BB, RSI, etc.")
        return "<br>".join(lines)

    def _quick_questions(self, ctx: dict, last_type: str) -> List[str]:
        sym = ctx["symbol"]
        act = ctx.get("action", "hold")
        base = [
            f"Por que {sym} da {act.upper()}?",
            "Que tal si entro a diferente precio?",
            f"Como esta el mercado de {sym}?",
            "Que posicion tomar?",
            "Que riesgo tiene este trade?",
            "Explicame que es OTE",
            "Como gestionar el riesgo?",
        ]
        zones = ctx.get("ote_zones", [])
        if zones:
            z = zones[0]
            base.insert(2, f"Que tal si entro en ${z.get('entry_min',0):.2f} con SL en ${z.get('stop_loss',0):.2f}?")
        return base
