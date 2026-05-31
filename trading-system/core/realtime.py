import time
import threading
import pandas as pd
from typing import Dict, Optional, List
from datetime import datetime, time as dtime
from collections import defaultdict
from backtesting.data_provider import DataProvider
from core.auto_learner import AutoLearner
from strategies.composite import CompositeOrchestrator
from strategies.micro_strategies import MicroSignal, SignalType
from utils.indicators import add_all_indicators
from utils.logger import setup_logger
from strategies.yoel_sardenas import predict_direction, compute_ote_zones


def is_market_open() -> bool:
    now = datetime.now()
    if now.weekday() >= 5:
        return False
    market_open = dtime(9, 30)
    market_close = dtime(16, 0)
    return market_open <= now.time() <= market_close


class LivePriceSimulator:
    def __init__(self):
        self.prices: Dict[str, dict] = {}
        self.last_fetch_time: Dict[str, float] = {}
        self.market_open = True

    def update_base_price(self, symbol: str, df):
        if df is None or len(df) < 2:
            return
        last = df.iloc[-1]
        prev = df.iloc[-2]
        close = float(last['close'])
        high = float(last['high'])
        low = float(last['low'])
        vol = float(last['volume'])
        spread = (high - low) * 0.1
        self.prices[symbol] = {
            'base': close,
            'high': high,
            'low': low,
            'open': float(last['open']),
            'prev_close': float(prev['close']),
            'spread': max(spread, 0.01),
            'volume': vol,
            'ts': time.time()
        }
        self.last_fetch_time[symbol] = time.time()

    def get_live_price(self, symbol: str) -> Optional[dict]:
        p = self.prices.get(symbol)
        if p is None:
            return None
        self.market_open = is_market_open()
        daily_change = (p['base'] - p['prev_close']) / p['prev_close'] * 100 if p['prev_close'] > 0 else 0
        return {
            'price': round(p['base'], 2),
            'change': round(daily_change, 2),
            'high': round(p['high'], 2),
            'low': round(p['low'], 2),
            'volume': int(p['volume']),
            'updated': datetime.now().isoformat(),
            'market_open': self.market_open,
        }


class RealTimeEngine:
    def __init__(self, config: dict):
        self.config = config
        self.logger = setup_logger("realtime")
        self.data_provider = DataProvider()
        self.orchestrator = CompositeOrchestrator()
        self.auto_learner = AutoLearner(config)
        self.simulator = LivePriceSimulator()
        self.watched = config.get('trading', {}).get('symbols', ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA'])
        self.timeframe = '1d'
        self.running = False
        self._fetch_thread = None
        self._last_analysis: Dict[str, dict] = {}
        self._latest_prices: Dict[str, dict] = {}
        self._history: Dict[str, list] = defaultdict(list)
        self._candles: Dict[str, list] = defaultdict(list)
        self._lock = threading.Lock()
        self._last_fetch_all = -99999  # triggers immediate first fetch
        self._fetch_interval = 120

    def start(self):
        self.running = True
        self._fetch_thread = threading.Thread(target=self._fetch_loop, daemon=True)
        self._fetch_thread.start()
        self.logger.info(f"R T iniciado: {len(self.watched)} simbolos, refresh cada {self._fetch_interval}s")

    def stop(self):
        self.running = False
        self.logger.info("R T detenido")

    def _fetch_loop(self):
        while self.running:
            try:
                now = time.time()
                if now - self._last_fetch_all >= self._fetch_interval:
                    for symbol in self.watched:
                        try:
                            df = self.data_provider.fetch(symbol, interval=self.timeframe, period='6mo', force=True)
                            if df is not None and len(df) > 20:
                                df = add_all_indicators(df)
                                analysis = self.orchestrator.analyze(df)
                                # Add direction prediction + OTE zones
                                try:
                                    pred = predict_direction(df)
                                    h, l, c = df['high'].values, df['low'].values, df['close'].values
                                    boost = min(pred.confluence_score // 3, 25) if pred.confluence_score > 30 else 0
                                    zones = compute_ote_zones(h, l, c, df, boost)
                                    analysis['prediction'] = {
                                        'direction': pred.direction.upper() if pred.direction else None, 'confidence': pred.confidence,
                                        'confluence_score': pred.confluence_score,
                                        'target_1': round(pred.target_1, 2) if pred.target_1 else None,
                                        'target_2': round(pred.target_2, 2) if pred.target_2 else None,
                                        'target_3': round(pred.target_3, 2) if pred.target_3 else None,
                                        'stop_loss': round(pred.stop_loss, 2) if pred.stop_loss else None,
                                        'reason': pred.reason,
                                    }
                                    analysis['ote_zones'] = [{
                                        'direction': z.direction, 'entry_min': round(z.entry_min, 2),
                                        'entry_max': round(z.entry_max, 2), 'stop_loss': round(z.stop_loss, 2),
                                        'tp1': round(z.take_profit_1, 2), 'tp2': round(z.take_profit_2, 2),
                                        'tp3': round(z.take_profit_3, 2), 'confidence': z.confidence,
                                        'confluence_score': z.confluence_score,
                                        'strength_label': z.strength_label,
                                        'hypothesis_arrow': z.hypothesis_arrow,
                                        'rr_ratio': z.rr_ratio,
                                    } for z in zones]
                                except Exception:
                                    pass
                                with self._lock:
                                    self._last_analysis[symbol] = analysis
                                    self.simulator.update_base_price(symbol, df)
                                    self._history[symbol].append({
                                        't': datetime.now().isoformat(),
                                        'a': analysis['action'],
                                        'c': analysis['confidence']
                                    })
                                    if len(self._history[symbol]) > 100:
                                        self._history[symbol] = self._history[symbol][-100:]
                                    # store last 30 candles for mini chart
                                    if df is not None and len(df) > 0:
                                        cdl = []
                                        for i in range(max(0, len(df)-30), len(df)):
                                            r = df.iloc[i]
                                            ts = int(r.name.timestamp()) if hasattr(r.name, 'timestamp') else None
                                            cdl.append({
                                                't': ts,
                                                'o': round(float(r['open']), 2),
                                                'h': round(float(r['high']), 2),
                                                'l': round(float(r['low']), 2),
                                                'c': round(float(r['close']), 2),
                                                'bb_h': round(float(r['bb_high']), 2) if 'bb_high' in df.columns and pd.notna(r['bb_high']) else None,
                                                'bb_m': round(float(r['bb_mid']), 2) if 'bb_mid' in df.columns and pd.notna(r['bb_mid']) else None,
                                                'bb_l': round(float(r['bb_low']), 2) if 'bb_low' in df.columns and pd.notna(r['bb_low']) else None,
                                            })
                                        self._candles[symbol] = cdl
                                if analysis['action'] != 'hold':
                                    self.logger.info(
                                        f"[{symbol}] {analysis['action'].upper()} "
                                        f"c={analysis['confidence']:.2f} "
                                        f"m={analysis.get('micro_count', 0)}"
                                    )
                        except Exception as e:
                            self.logger.error(f"Error fetching {symbol}: {e}")
                    self._last_fetch_all = time.time()
            except Exception as e:
                self.logger.error(f"Fetch loop error: {e}")
            time.sleep(1)

    def get_snapshot(self) -> Dict:
        with self._lock:
            market_open = self.simulator.market_open
            result = {'market_open': market_open}
            for symbol in self.watched:
                analysis = self._last_analysis.get(symbol)
                live = self.simulator.get_live_price(symbol)
                if analysis:
                    grp = dict(analysis.get('group_scores', {}))
                    entry = {
                        'action': analysis['action'],
                        'confidence': analysis['confidence'],
                        'score': analysis.get('net_score', 0),
                        'agreement': analysis.get('agreement', 0),
                        'micro_total': analysis.get('micro_count', 0),
                        'groups': grp,
                        'composites': [
                            {'n': c['name'], 'a': c['action'], 'c': c['confidence']}
                            for c in analysis.get('composites', [])
                        ],
                        'price': live,
                        'prediction': analysis.get('prediction'),
                        'ote_zones': analysis.get('ote_zones'),
                        'history': self._history.get(symbol, [])[-5:],
                        'candles': self._candles.get(symbol, [])
                    }
                else:
                    entry = {'action': 'waiting', 'confidence': 0, 'price': live}
                result[symbol] = entry
            return result

    def analyze_one(self, symbol: str, tf: str = None, period: str = None) -> Dict:
        tf = tf or self.timeframe
        pr = period or '6mo'
        df = self.data_provider.fetch(symbol, interval=tf, period=pr, force=True)
        if df is None or len(df) < 30:
            return {'action': 'hold', 'confidence': 0, 'error': 'Datos insuficientes'}
        df = add_all_indicators(df)
        analysis = self.orchestrator.analyze(df)
        with self._lock:
            self._last_analysis[symbol] = analysis
            self.simulator.update_base_price(symbol, df)
        return analysis
