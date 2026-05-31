import pandas as pd
import numpy as np
from typing import Dict, List, Optional
from datetime import datetime
from core.engine import TradingEngine
from core.portfolio import Position
from backtesting.metrics import MetricsCalculator
from backtesting.data_provider import DataProvider
from utils.logger import setup_logger
from utils.indicators import add_all_indicators


class BacktestEngine:
    def __init__(self, config: dict):
        self.config = config
        self.logger = setup_logger("backtest_engine")
        self.metrics = MetricsCalculator()
        self.data_provider = DataProvider()

    def run(
        self,
        symbol: str,
        start: str = None,
        end: str = None,
        initial_capital: float = 100000,
        commission_pct: float = 0.001,
        slippage_pct: float = 0.001
    ) -> Dict:
        bc = self.config.get('backtest', {})
        start = start or bc.get('default_start', '2023-01-01')
        end = end or bc.get('default_end', '2024-01-01')
        initial_capital = initial_capital or bc.get('initial_capital', 100000)
        commission_pct = commission_pct or bc.get('commission_pct', 0.001)
        slippage_pct = slippage_pct or bc.get('slippage_pct', 0.001)

        df = self.data_provider.fetch(symbol, interval='1d', start=start, end=end)
        if df is None or len(df) < 50:
            self.logger.error(f"Insufficient data for {symbol}")
            return {'error': 'Insufficient data'}

        df = add_all_indicators(df)
        df = df.dropna().reset_index(drop=True)

        engine = TradingEngine(self.config)
        engine.portfolio.initial_capital = initial_capital
        engine.portfolio.cash = initial_capital

        self.logger.info(f"Running backtest for {symbol}: {start} -> {end} ({len(df)} bars)")

        for i in range(50, len(df)):
            window = df.iloc[:i + 1].copy()
            current_bar = df.iloc[i]

            signal = engine.analyze_market(symbol, window)
            engine.execute_signal(symbol, signal, window)

            engine.portfolio.update_prices({symbol: float(current_bar['close'])})
            engine.portfolio.check_stops({symbol: float(current_bar['close'])})
            engine.portfolio.record_equity()

        results = self.metrics.calculate(
            engine.portfolio.trades,
            engine.portfolio.equity_curve,
            initial_capital
        )
        results['symbol'] = symbol
        results['start'] = start
        results['end'] = end
        results['total_bars'] = len(df)
        results['equity_curve'] = engine.portfolio.equity_curve

        self._print_results(results)
        return results

    def run_multi(self, symbols: List[str], **kwargs) -> Dict[str, Dict]:
        results = {}
        for symbol in symbols:
            results[symbol] = self.run(symbol, **kwargs)
        return results

    def _print_results(self, results: Dict):
        self.logger.info("=" * 60)
        self.logger.info(f"BACKTEST RESULTS: {results.get('symbol', 'N/A')}")
        self.logger.info("=" * 60)
        self.logger.info(f"Period: {results.get('start')} -> {results.get('end')}")
        self.logger.info(f"Total Return: {results.get('total_return_pct', 0):.2f}%")
        self.logger.info(f"Win Rate: {results.get('win_rate', 0):.2f}%")
        self.logger.info(f"Total Trades: {results.get('total_trades', 0)}")
        self.logger.info(f"Profit Factor: {results.get('profit_factor', 0):.2f}")
        self.logger.info(f"Sharpe Ratio: {results.get('sharpe_ratio', 0):.2f}")
        self.logger.info(f"Max Drawdown: {results.get('max_drawdown_pct', 0):.2f}%")
        self.logger.info(f"Final Equity: ${results.get('final_equity', 0):.2f}")
        self.logger.info("=" * 60)
