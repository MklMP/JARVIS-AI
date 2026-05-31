import json
import os
import yaml
import uvicorn
import asyncio
import threading
import pandas as pd
from fastapi import FastAPI, Request, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from jinja2 import Environment, FileSystemLoader
from typing import Dict, Optional
from datetime import datetime, timedelta

from core.engine import TradingEngine
from core.realtime import RealTimeEngine
from core.scanner import MarketScanner, ALL_SYMBOLS
from backtesting.data_provider import DataProvider
from utils.logger import setup_logger
from utils.indicators import add_all_indicators
from pattern_analyzer import analyze_market_longterm, PatternAnalyzer

app = FastAPI(title="JARVIS Trading System", version="3.1")
static_dir = os.path.join(os.path.dirname(__file__), 'static')
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

templates_dir = os.path.join(os.path.dirname(__file__), 'templates')
jinja_env = Environment(loader=FileSystemLoader(templates_dir), autoescape=True)

_SERVER_PORT: int = 8080

def render(name: str, **kwargs) -> str:
    tpl = jinja_env.get_template(name)
    return HTMLResponse(content=tpl.render(ws_port=_SERVER_PORT, **kwargs))

engine: Optional[TradingEngine] = None
rt_engine: Optional[RealTimeEngine] = None
scanner: Optional[MarketScanner] = None
data_provider = None
ws_clients: set = set()
logger = setup_logger("server")


def load_config():
    config_path = os.path.join(os.path.dirname(__file__), 'config', 'config.yaml')
    if os.path.exists(config_path):
        with open(config_path) as f:
            return yaml.safe_load(f)
    return {}


@app.on_event("startup")
async def startup():
    global engine, rt_engine, scanner, data_provider, _SERVER_PORT
    config = load_config()
    _SERVER_PORT = config.get('server', {}).get('port', 8080)
    engine = TradingEngine(config)
    rt_engine = RealTimeEngine(config)
    data_provider = DataProvider()
    rt_engine.start()
    scanner = MarketScanner()
    logger.info("=" * 50)
    logger.info("JARVIS TRADING SYSTEM - MULTI-TIMEFRAME")
    logger.info(f"  Compuestas: {len(engine.orchestrator.composites)}")
    logger.info(f"  Micros: {sum(len(c.micro_strategies) for c in engine.orchestrator.composites)}")
    logger.info(f"  Simbolos en escaner: {len(ALL_SYMBOLS)}")
    logger.info("=" * 50)


@app.on_event("shutdown")
async def shutdown():
    if rt_engine:
        rt_engine.stop()


# ===== WEBSOCKET =====
@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    ws_clients.add(ws)
    logger.info(f"WS cliente conectado ({len(ws_clients)} total)")
    try:
        while True:
            try:
                msg = await asyncio.wait_for(ws.receive_text(), timeout=1)
            except asyncio.TimeoutError:
                if rt_engine:
                    snap = rt_engine.get_snapshot()
                    await ws.send_json(snap)
                continue
            if msg == "ping":
                await ws.send_json({"pong": datetime.now().isoformat()})
    except WebSocketDisconnect:
        ws_clients.discard(ws)
        logger.info(f"WS desconectado ({len(ws_clients)} restantes)")


# ===== PAGINAS =====
@app.get("/", response_class=HTMLResponse)
async def dashboard():
    return render("dashboard.html")

@app.get("/analizar", response_class=HTMLResponse)
async def analizar_page():
    return render("analizar.html")

@app.get("/escaner", response_class=HTMLResponse)
async def escaner_page():
    return render("escaner.html")


# ===== API REST =====
@app.get("/api/analizar")
async def api_analizar(
    symbol: str = Query("AAPL"),
    timeframe: str = Query("1d"),
    period: str = Query("6mo")
):
    if data_provider is None:
        raise HTTPException(status_code=503, detail="No iniciado")
    df = data_provider.fetch(symbol, interval=timeframe, period=period, force=True)
    if df is None or len(df) < 20:
        return {'action': 'hold', 'confidence': 0, 'error': 'Datos insuficientes'}
    df = add_all_indicators(df)
    analysis = engine.orchestrator.analyze(df)
    micros = analysis.get('micro_signals', [])
    analysis['micro_summary'] = {
        'buy': sum(1 for m in micros if m['action'] == 'buy'),
        'sell': sum(1 for m in micros if m['action'] == 'sell'),
        'hold': sum(1 for m in micros if m['action'] == 'hold'),
        'total': len(micros)
    }
    return analysis

@app.get("/api/analizar/multi")
async def api_analizar_multi(symbol: str = Query("AAPL")):
    from core.scanner import MultiTimeframeAnalyzer
    mta = MultiTimeframeAnalyzer()
    result = mta.analyze(symbol)
    return result

@app.get("/api/status")
async def api_status():
    if rt_engine is None:
        raise HTTPException(status_code=503, detail="No iniciado")
    base = engine.get_status() if engine else {}
    base['realtime'] = rt_engine.get_snapshot()
    return base

@app.get("/api/estrategias")
async def api_estrategias():
    if engine is None:
        raise HTTPException(status_code=503, detail="No iniciado")
    composites = [
        {'name': c.name, 'group': c.group, 'micro_count': len(c.micro_strategies)}
        for c in engine.orchestrator.composites
    ]
    return {'composites': composites, 'composite_count': len(composites)}

@app.get("/api/analizar/timeframes")
async def api_analizar_tf_individual(symbol: str = Query("AAPL")):
    if data_provider is None:
        raise HTTPException(status_code=503, detail="No iniciado")
    tfs = [('1h', '1mo'), ('4h', '2mo'), ('1d', '6mo')]
    results = {}
    for tf, period in tfs:
        try:
            df = data_provider.fetch(symbol, interval=tf, period=period, force=True)
            if df is not None and len(df) > 20:
                df = add_all_indicators(df)
                analysis = engine.orchestrator.analyze(df)
                results[tf] = {
                    'action': analysis['action'],
                    'confidence': analysis['confidence'],
                    'net': analysis['net_score'],
                    'agreement': analysis['agreement'],
                    'composites': analysis['composites'],
                }
            else:
                results[tf] = {'action': 'hold', 'confidence': 0, 'error': 'datos insuficientes'}
        except Exception as e:
            results[tf] = {'action': 'error', 'error': str(e)}
    return {'symbol': symbol, 'timeframes': results}


# ===== GRAFICO / PREDICCION =====
@app.get("/api/grafico/datos")
async def api_grafico_datos(
    symbol: str = Query("AAPL"),
    timeframe: str = Query("1d"),
    period: str = Query("3mo")
):
    if data_provider is None:
        raise HTTPException(status_code=503, detail="No iniciado")
    try:
        df = data_provider.fetch(symbol, interval=timeframe, period=period, force=True)
        if df is None or len(df) < 20:
            return {"error": "Datos insuficientes", "symbol": symbol}
        df = add_all_indicators(df)

        from strategies.yoel_sardenas import predict_direction, compute_ote_zones
        pred = predict_direction(df)
        h, l, c = df['high'].values, df['low'].values, df['close'].values
        boost = min(pred.confluence_score // 3, 25) if pred.confluence_score > 30 else 0
        ote_zones_raw = compute_ote_zones(h, l, c, df, boost)
        pred_dir = pred.direction.upper() if pred.direction else None
        filtered = [z for z in ote_zones_raw
            if (pred_dir == 'UP' and z.direction == 'buy')
            or (pred_dir == 'DOWN' and z.direction == 'sell')]
        ote_zones = [{
            'direction': z.direction, 'entry_min': z.entry_min, 'entry_max': z.entry_max,
            'stop_loss': z.stop_loss, 'tp1': z.take_profit_1, 'tp2': z.take_profit_2,
            'tp3': z.take_profit_3, 'confidence': z.confidence,
        } for z in filtered]

        fvg_zones = []
        fvg_h, fvg_l = df['high'].values, df['low'].values
        for idx in range(3, len(df)):
            if fvg_h[idx-3] < fvg_l[idx]:
                fvg_zones.append({
                    'direction': 'buy', 'idx': idx,
                    'gap_top': round(float(fvg_l[idx]), 2),
                    'gap_bottom': round(float(fvg_h[idx-3]), 2),
                })
            elif fvg_l[idx-3] > fvg_h[idx]:
                fvg_zones.append({
                    'direction': 'sell', 'idx': idx,
                    'gap_top': round(float(fvg_l[idx-3]), 2),
                    'gap_bottom': round(float(fvg_h[idx]), 2),
                })

        candles = []
        for i in range(len(df)):
            row = df.iloc[i]
            candle = {
                't': int(row.name.timestamp()) if hasattr(row.name, 'timestamp') else i,
                'o': round(float(row['open']), 2), 'h': round(float(row['high']), 2),
                'l': round(float(row['low']), 2), 'c': round(float(row['close']), 2),
                'v': int(row['volume']),
            }
            for col, key in [('bb_high','bb_h'),('bb_mid','bb_m'),('bb_low','bb_l'),('bb_position','bb_p'),
                             ('ema_9','e9'),('ema_21','e21'),('ema_50','e50'),('rsi','rsi'),('volume_ratio','vr')]:
                if col in df.columns and pd.notna(row[col]):
                    candle[key] = round(float(row[col]), 2)
            candles.append(candle)

        return {
            'symbol': symbol, 'timeframe': timeframe,
            'candles': candles, 'ote_zones': ote_zones, 'fvg_zones': fvg_zones,
            'prediction': {
                'direction': pred.direction, 'confidence': pred.confidence,
                'confluence_score': pred.confluence_score,
                'target_1': pred.target_1, 'target_2': pred.target_2, 'target_3': pred.target_3,
                'stop_loss': pred.stop_loss, 'reason': pred.reason,
            },
            'latest': candles[-1] if candles else None,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ===== ESCANER MASIVO MULTI-TF =====
@app.get("/api/escanear/iniciar")
async def api_escanear_iniciar():
    if scanner is None:
        raise HTTPException(status_code=503, detail="Scanner no disponible")
    prog = scanner.get_progress()
    if prog['status'] == 'scanning':
        return {"status": "ya_en_curso", "simbolos": prog['total']}
    thread = threading.Thread(target=lambda: scanner.scan_all(), daemon=True)
    thread.start()
    return {"status": "iniciado", "simbolos": len(ALL_SYMBOLS)}

@app.get("/api/escanear/progreso")
async def api_escanear_progreso():
    if scanner is None:
        return {"status": "no_disponible"}
    return scanner.get_progress()

@app.get("/api/escanear/resultados")
async def api_escanear_resultados(
    min_conf: float = Query(0.0),
    max_results: int = Query(200),
    filtro_bb: str = Query('', pattern='^(outside|inside|)$'),
    filtro_fvg: str = Query('', pattern='^(bullish|bearish|any|)$'),
    sort_order: str = Query('desc', pattern='^(asc|desc)$'),
):
    if scanner is None:
        return {"resultados": []}
    items = scanner.get_results(min_conf=min_conf, max_results=max_results)
    if filtro_bb == 'outside':
        items = [i for i in items if i.get('bb_outside')]
    elif filtro_bb == 'inside':
        items = [i for i in items if not i.get('bb_outside') and i.get('bb_position', 0.5) != 0.5]
    if filtro_fvg == 'bullish':
        items = [i for i in items if i.get('fvg_bullish')]
    elif filtro_fvg == 'bearish':
        items = [i for i in items if i.get('fvg_bearish')]
    elif filtro_fvg == 'any':
        items = [i for i in items if i.get('fvg_bullish') or i.get('fvg_bearish')]
    reverse = sort_order == 'desc'
    buys = sorted([i for i in items if i['action'] == 'buy'], key=lambda x: x['confidence'], reverse=reverse)
    sells = sorted([i for i in items if i['action'] == 'sell'], key=lambda x: x['confidence'], reverse=reverse)
    holds = [i for i in items if i['action'] == 'hold']
    return {
        "resultados": items, "total": len(items),
        "comprar": buys[:30], "vender": sells[:30],
        "resumen": {"comprar": len(buys), "vender": len(sells), "hold": len(holds), "total": len(items),}
    }

@app.get("/api/escanear/cancelar")
async def api_escanear_cancelar():
    if scanner:
        scanner.cancel()
    return {"status": "cancelado"}

@app.get("/api/ping")
async def api_ping():
    return {
        "status": "ok", "time": datetime.now().isoformat(),
        "version": "3.1", "ws_clients": len(ws_clients),
        "symbols": len(ALL_SYMBOLS), "config": engine is not None
    }

@app.get("/api/simbolos/disponibles")
async def api_simbolos_disponibles():
    return {"total": len(ALL_SYMBOLS), "simbolos": ALL_SYMBOLS}


# ===== ANALISIS LARGO PLAZO =====
@app.get("/api/analisis/largo-plazo")
async def api_analisis_largo_plazo(symbol: str = Query("AAPL"), years: int = Query(3)):
    if data_provider is None:
        raise HTTPException(status_code=503, detail="No iniciado")
    end = datetime.now().strftime("%Y-%m-%d")
    start = (datetime.now() - timedelta(days=years * 365)).strftime("%Y-%m-%d")
    df = data_provider.fetch(symbol, interval='1d', start=start, end=end, force=True)
    if df is None or len(df) < 50:
        return {"error": "Datos insuficientes", "symbol": symbol}
    df = add_all_indicators(df)
    candles = []
    for _, row in df.iterrows():
        c = {"t": int(row.get('t', 0)), "o": row['open'], "h": row['high'],
             "l": row['low'], "c": row['close'], "v": int(row.get('volume', 0))}
        for k in ['bb_h', 'bb_m', 'bb_l', 'rsi', 'vr', 'e9', 'e21', 'e50']:
            if k in row and pd.notna(row[k]):
                c[k] = round(float(row[k]), 4)
        candles.append(c)
    try:
        result = analyze_market_longterm(symbol, candles)
        result['years'] = years
        result['total_candles'] = len(candles)
        return result
    except Exception as e:
        return {"error": str(e), "symbol": symbol}

@app.get("/api/analisis/patrones")
async def api_analisis_patrones(
    symbol: str = Query("AAPL"),
    timeframe: str = Query("1d"),
    period: str = Query("6mo")
):
    if data_provider is None:
        raise HTTPException(status_code=503, detail="No iniciado")
    df = data_provider.fetch(symbol, interval=timeframe, period=period, force=True)
    if df is None or len(df) < 20:
        return {"error": "Datos insuficientes"}
    df = add_all_indicators(df)
    candles = []
    for _, row in df.iterrows():
        c = {"t": int(row.get('t', 0)), "o": row['open'], "h": row['high'],
             "l": row['low'], "c": row['close'], "v": int(row.get('volume', 0))}
        for k in ['bb_h', 'bb_m', 'bb_l', 'rsi', 'vr', 'e9', 'e21', 'e50']:
            if k in row and pd.notna(row[k]):
                c[k] = round(float(row[k]), 4)
        candles.append(c)
    try:
        pa = PatternAnalyzer(symbol)
        result = pa.analyze(candles)
        result['learnings'] = pa.get_learnings()
        return result
    except Exception as e:
        return {"error": str(e)}


if __name__ == "__main__":
    config = load_config()
    host = config.get('server', {}).get('host', '0.0.0.0')
    port = config.get('server', {}).get('port', 8080)
    uvicorn.run("server:app", host=host, port=port, reload=True)
