import time
import threading
import concurrent.futures
import pandas as pd
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from collections import defaultdict
from backtesting.data_provider import DataProvider
from strategies.micro_strategies import ALL_MICRO_STRATEGIES, MicroSignal, SignalType
from utils.logger import setup_logger
from utils.indicators import add_all_indicators
from strategies.yoel_sardenas import predict_direction, compute_ote_zones

_logger = setup_logger("scanner")

ALL_SYMBOLS = sorted(set([
    'AAPL','MSFT','GOOGL','AMZN','NVDA','META','TSLA','BRK-B','UNH','JPM',
    'V','XOM','PG','MA','COST','HD','CVX','MRK','ABBV','LLY',
    'KO','PEP','BAC','CRM','WMT','AVGO','TMO','MCD','NFLX','ADBE',
    'BRK-B','JPM-B',
    'CSCO','PFE','ABT','CMCSA','ACN','DHR','NKE','LIN','TXN','DIS',
    'WFC','PM','QCOM','AMD','INTC','HON','IBM','UPS','BA','GE',
    'RTX','LOW','CAT','MS','SPGI','BLK','UNP','AMGN','PLD','DE',
    'GS','C','SCHW','ETN','SYK','BKNG','MDT','LMT','TMUS','CB',
    'VZ','MBLY','ISRG','BSX','FI','ADI','MO','CL','APD','GILD',
    'SO','DUK','NOC','MMC','NSC','GM','F','AIG','MET','PRU',
    'SBUX','YUM','CMG','CHTR','EA','TTWO','CCL','RCL','AAL','UAL',
    'DAL','LUV','FDX','ROK','EMR','ITW','MMM','DE','CMI',
    'JCI','TT','KMB','CLX','PG','EL','MDLZ','K','GIS','CPB',
    'ADP','CTAS','MAR','MELI','PYPL','ABNB','DDOG','CRWD','WDAY','ZS',
    'MU','NOW','SNAP','PLTR','SQ','SHOP','UBER','LYFT','RIVN','LCID',
    'NIO','XPEV','JD','BABA','BIDU','TCOM','NTES','WYNN','LVS','MGM',
    'BAX','BDX','BSX','DHR','EW','HOLX','IDXX','ILMN','PODD',
    'COO','RMD','STE','SYK','TFX','WST','ZBH','LH','DGX',
    'APO','ARES','AXON','BRO','CH','CBOE','COIN','CPAY','DASH','DKNG',
    'EFX','ENPH','EXPD','EXR','FDS','FSLR','FTNT','GPN','HUBB','IP',
    'JBHT','KEY','KMX','LVS','MDB','MRNA','NDAQ','NTRS','OKTA',
    'PODD','POOL','QRVO','RMD','SEDG','SIRI','SWKS','TER','TROW',
    'TXT','UDR','ULTA','USB','VTRS','WAB','WDC','WRK',
    'WYNN','XEL','XRX','YUMC','ZBRA','ZG','ZION','ZM','ZS','ZTS',
]))


class MultiTimeframeAnalyzer:
    def __init__(self):
        self.data = DataProvider()

    def analyze(self, symbol: str) -> Dict:
        # Scanner uses 2h fast + 1d for speed (instead of 1h+4h+1d)
        tfs = [('4h', '2mo', 0.3), ('1d', '6mo', 0.7)]
        all_results = []
        total_weight = 0

        for tf, period, weight in tfs:
            try:
                df = self.data.fetch(symbol, interval=tf, period=period)
                if df is not None and len(df) > 20:
                    df = add_all_indicators(df)
                    signals = self._run_micros(df)
                    buy_conf = sum(s.confidence * weight for s in signals if s.action == SignalType.BUY)
                    sell_conf = sum(s.confidence * weight for s in signals if s.action == SignalType.SELL)
                    micro_count = len(signals)
                    net = (buy_conf - sell_conf) / max(micro_count, 1)
                    all_results.append({
                        'tf': tf, 'net': net, 'weight': weight,
                        'micros': micro_count, 'buy': sum(1 for s in signals if s.action == SignalType.BUY),
                        'sell': sum(1 for s in signals if s.action == SignalType.SELL),
                        'holds': sum(1 for s in signals if s.action == SignalType.HOLD),
                        'signals': signals,
                    })
                    total_weight += weight
            except Exception as e:
                _logger.error(f"{symbol}/{tf}: {e}")

        if not all_results:
            return self._empty_result(symbol)

        combined_net = sum(r['net'] * r['weight'] for r in all_results) / total_weight if total_weight > 0 else 0
        all_signals = []
        for r in all_results:
            all_signals.extend(r['signals'])

        total_buy = sum(1 for s in all_signals if s.action == SignalType.BUY)
        total_sell = sum(1 for s in all_signals if s.action == SignalType.SELL)
        total = len(all_signals)

        if combined_net > 0.02:
            action = 'buy'
            confidence = min(abs(combined_net) * 3, 0.95)
        elif combined_net < -0.02:
            action = 'sell'
            confidence = min(abs(combined_net) * 3, 0.95)
        else:
            action = 'hold'
            confidence = 0.0

        group_scores = {}
        for s in all_signals:
            g = s.group
            multiplier = 1 if s.action == SignalType.BUY else -1 if s.action == SignalType.SELL else 0
            group_scores[g] = group_scores.get(g, 0) + multiplier * s.confidence

        # Direction prediction + OTE zones (on daily TF)
        prediction = None
        ote_zones = None
        bb_outside = False
        bb_position = 0.5
        fvg_bullish = False
        fvg_bearish = False
        try:
            df_daily = self.data.fetch(symbol, interval='1d', period='6mo')
            if df_daily is not None and len(df_daily) > 20:
                df_daily = add_all_indicators(df_daily)
                # BB filter
                if 'bb_position' in df_daily.columns:
                    bp = float(df_daily['bb_position'].iloc[-1])
                    bb_position = round(bp, 3)
                    bb_outside = bp < 0.0 or bp > 1.0
                # FVG filter — check last 5 candles, most recent wins
                if len(df_daily) >= 5:
                    dh, dl = df_daily['high'].values, df_daily['low'].values
                    fvg_bullish = False
                    fvg_bearish = False
                    for i in range(min(5, len(df_daily)-1), 2, -1):
                        if dh[i-3] < dl[i]:
                            fvg_bullish = True
                            break
                        if dl[i-3] > dh[i]:
                            fvg_bearish = True
                            break
                pred = predict_direction(df_daily)
                h, l, c = df_daily['high'].values, df_daily['low'].values, df_daily['close'].values
                boost = min(pred.confluence_score // 3, 25) if pred.confluence_score > 30 else 0
                zones = compute_ote_zones(h, l, c, df_daily, boost)
                prediction = {
                    'direction': pred.direction,
                    'confidence': pred.confidence,
                    'confluence_score': pred.confluence_score,
                    'target_1': round(pred.target_1, 2) if pred.target_1 else None,
                    'target_2': round(pred.target_2, 2) if pred.target_2 else None,
                    'target_3': round(pred.target_3, 2) if pred.target_3 else None,
                    'stop_loss': round(pred.stop_loss, 2) if pred.stop_loss else None,
                    'reason': pred.reason,
                }
                # Only show OTE zones matching predicted direction
                pred_dir = pred.direction.upper() if pred.direction else None
                filtered_zones = []
                for z in zones:
                    z_dir = z.direction.lower()
                    if pred_dir == 'UP' and z_dir == 'buy':
                        filtered_zones.append(z)
                    elif pred_dir == 'DOWN' and z_dir == 'sell':
                        filtered_zones.append(z)
                ote_zones = [{
                    'direction': z.direction, 'entry_min': round(z.entry_min, 2), 'entry_max': round(z.entry_max, 2),
                    'stop_loss': round(z.stop_loss, 2), 'tp1': round(z.take_profit_1, 2),
                    'tp2': round(z.take_profit_2, 2), 'tp3': round(z.take_profit_3, 2),
                    'confidence': z.confidence, 'confluence_score': z.confluence_score,
                    'strength_label': z.strength_label, 'hypothesis_arrow': z.hypothesis_arrow,
                    'has_trend_filter': z.has_trend_filter, 'has_liquidity_sweep': z.has_liquidity_sweep,
                    'has_cisd': z.has_cisd, 'has_volume_confirm': z.has_volume_confirm,
                    'rr_ratio': z.rr_ratio, 'atr_entry': z.atr_entry,
                } for z in filtered_zones]
        except Exception:
            pass

        return {
            'symbol': symbol,
            'action': action,
            'confidence': round(confidence, 4),
            'net_score': round(combined_net, 4),
            'timeframes': [
                {'tf': r['tf'], 'net': round(r['net'], 3), 'buy': r['buy'], 'sell': r['sell']}
                for r in all_results
            ],
            'micro_total': total,
            'micro_buy': total_buy,
            'micro_sell': total_sell,
            'group_scores': {k: round(v, 3) for k, v in sorted(group_scores.items(), key=lambda x: abs(x[1]), reverse=True)},
            'prediction': prediction,
            'ote_zones': ote_zones,
            'bb_outside': bb_outside,
            'bb_position': bb_position,
            'fvg_bullish': fvg_bullish,
            'fvg_bearish': fvg_bearish,
        }

    def _run_micros(self, df) -> List[MicroSignal]:
        results = []
        for m in ALL_MICRO_STRATEGIES:
            try:
                s = m.analyze(df)
                results.append(s)
            except Exception:
                results.append(MicroSignal(m.name, m.group, SignalType.HOLD, 0.0))
        return results

    def _empty_result(self, symbol):
        return {
            'symbol': symbol, 'action': 'hold', 'confidence': 0.0,
            'net_score': 0, 'timeframes': [],
            'micro_total': 0, 'micro_buy': 0, 'micro_sell': 0,
            'group_scores': {},
            'bb_outside': False, 'bb_position': 0.5,
            'fvg_bullish': False, 'fvg_bearish': False,
        }


class MarketScanner:
    def __init__(self, workers: int = 8):
        self.analyzer = MultiTimeframeAnalyzer()
        self.results: Dict[str, dict] = {}
        self._progress = {'current': 0, 'total': 0, 'pct': 0.0, 'status': 'idle', 'current_symbol': ''}
        self._lock = threading.Lock()
        self._cancel = False
        self._workers = workers

    def scan_all(self, symbols: List[str] = None):
        targets = symbols or ALL_SYMBOLS
        with self._lock:
            if self._progress['status'] == 'scanning':
                _logger.warning("Scan ya en ejecucion, ignorando")
                return
        self._cancel = False
        total = len(targets)
        with self._lock:
            self._progress = {'current': 0, 'total': total, 'pct': 0.0, 'status': 'scanning', 'current_symbol': ''}
        _logger.info(f"Escaneando {total} simbolos ({self._workers} workers)...")
        self.results = {}

        def scan_one(symbol: str) -> tuple:
            if self._cancel:
                return symbol, None
            try:
                with self._lock:
                    self._progress['current_symbol'] = symbol
                result = self.analyzer.analyze(symbol)
                return symbol, result
            except Exception as e:
                _logger.error(f"Error escaneando {symbol}: {e}")
                return symbol, None

        done_count = 0
        with concurrent.futures.ThreadPoolExecutor(max_workers=self._workers) as executor:
            futures = {executor.submit(scan_one, sym): sym for sym in targets}
            for future in concurrent.futures.as_completed(futures):
                if self._cancel:
                    break
                sym, result = future.result()
                if result is not None:
                    with self._lock:
                        self.results[sym] = result
                done_count += 1
                with self._lock:
                    self._progress['current'] = done_count
                    self._progress['pct'] = round(done_count / total * 100, 1)

                if done_count % 25 == 0 or done_count == total:
                    with self._lock:
                        buys = sum(1 for r in self.results.values() if r.get('action') == 'buy')
                        sells = sum(1 for r in self.results.values() if r.get('action') == 'sell')
                    _logger.info(f"  {done_count}/{total} ({self._progress['pct']}%) | B:{buys} S:{sells}")

        with self._lock:
            self._progress['status'] = 'complete'
            buys = sum(1 for r in self.results.values() if r.get('action') == 'buy')
            sells = sum(1 for r in self.results.values() if r.get('action') == 'sell')
            holds = sum(1 for r in self.results.values() if r.get('action') == 'hold')
            _logger.info(f"COMPLETO: {len(self.results)} | B:{buys} S:{sells} H:{holds}")

    def cancel(self):
        self._cancel = True
        with self._lock:
            self._progress['status'] = 'cancelled'

    def get_progress(self) -> Dict:
        with self._lock:
            return dict(self._progress)

    def get_results(self, min_conf: float = 0.0, max_results: int = 100) -> List[Dict]:
        with self._lock:
            items = []
            for sym, data in self.results.items():
                if data.get('confidence', 0) >= min_conf:
                    items.append({'symbol': sym, **data})
            items.sort(key=lambda x: x.get('confidence', 0), reverse=True)
            return items[:max_results]
