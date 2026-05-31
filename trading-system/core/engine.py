from typing import Dict, Optional
from datetime import datetime
from strategies.composite import CompositeOrchestrator
from core.auto_learner import AutoLearner
from core.portfolio import Portfolio, Position, Trade
from utils.logger import setup_logger


class TradingEngine:
    def __init__(self, config: dict):
        self.config = config
        self.logger = setup_logger("trading_engine")
        self.orchestrator = CompositeOrchestrator()
        self.auto_learner = AutoLearner(config)
        self.portfolio = Portfolio(
            initial_capital=config.get('backtest', {}).get('initial_capital', 100000)
        )
        self.running = False
        self.last_analysis = {}

    def analyze_market(self, symbol: str, df) -> Dict:
        self.logger.info(f"Analizando {symbol} con {len(df)} velas y {len(self.orchestrator.composites)} estrategias compuestas")
        analysis = self.orchestrator.analyze(df)
        self.last_analysis[symbol] = analysis

        action = analysis['action']
        conf = analysis['confidence']

        if action != 'hold':
            self.logger.info(
                f"  => {symbol}: {action.upper()} (confianza: {conf:.1%}) | "
                f"Compuestas: {analysis['buy_count']}UP {analysis['sell_count']}DOWN | "
                f"Micro-estrategias: {analysis['micro_count']}"
            )
            for g, s in analysis.get('group_scores', {}).items():
                d = "BULL" if s > 0 else "BEAR" if s < 0 else "NEUT"
                self.logger.info(f"    {d:5s} {g}: {s:+.3f}")

        return analysis

    def execute_signal(self, symbol: str, signal: Dict, df) -> None:
        action = signal.get('action', 'hold')
        confidence = signal.get('confidence', 0)
        min_conf = self.config.get('trading', {}).get('min_confidence', 0.3) if self.config else 0.3
        if action == 'hold' or confidence < min_conf:
            return
        price = float(df['close'].iloc[-1])
        atr_val = float(df['atr'].iloc[-1]) if df is not None and 'atr' in df.columns else price * 0.02
        if action == 'buy' and symbol not in self.portfolio.positions:
            if not self.portfolio.can_open_position(self.config.get('trading', {}).get('max_positions', 5)):
                return
            size_pct = self.config.get('trading', {}).get('position_size_pct', 0.02) if self.config else 0.02
            cash_alloc = self.portfolio.cash * size_pct * min(confidence / 0.5, 1.0)
            qty = max(1, int(cash_alloc / price))
            if qty > 0:
                pos = Position(
                    symbol=symbol, quantity=qty, entry_price=price, current_price=price,
                    stop_loss=round(price - atr_val * 1.5, 2), take_profit=round(price + atr_val * 3.0, 2),
                    side='buy', entry_time=datetime.now()
                )
                self.portfolio.open_position(pos)
        elif action == 'sell' and symbol in self.portfolio.positions:
            self.portfolio.close_position(symbol, price)

    def get_status(self) -> Dict:
        analysis_info = {}
        for symbol, analysis in self.last_analysis.items():
            analysis_info[symbol] = {
                'action': analysis.get('action', 'hold'),
                'confidence': analysis.get('confidence', 0),
                'composites': analysis.get('composites', []),
                'group_scores': analysis.get('group_scores', {}),
            }

        return {
            'total_equity': round(self.portfolio.total_equity, 2),
            'cash': round(self.portfolio.cash, 2),
            'open_positions': self.portfolio.position_count,
            'total_pnl': round(self.portfolio.get_total_pnl(), 2),
            'total_pnl_pct': round(self.portfolio.get_total_pnl_pct(), 2),
            'win_rate': round(self.portfolio.get_win_rate() * 100, 1),
            'total_trades': len(self.portfolio.trades),
            'composite_strategies': len(self.orchestrator.composites),
            'micro_strategies': sum(len(c.micro_strategies) for c in self.orchestrator.composites),
            'analysis': analysis_info,
            'positions': [
                {
                    'symbol': p.symbol,
                    'quantity': p.quantity,
                    'entry': p.entry_price,
                    'current': p.current_price,
                    'pnl': round(p.pnl, 2),
                    'pnl_pct': round(p.pnl_pct * 100, 2),
                    'stop_loss': p.stop_loss,
                    'take_profit': p.take_profit
                }
                for p in self.portfolio.positions.values()
            ]
        }
