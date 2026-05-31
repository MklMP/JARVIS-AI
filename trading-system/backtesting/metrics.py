import numpy as np
import pandas as pd
from typing import List, Dict
from core.portfolio import Trade


class MetricsCalculator:
    @staticmethod
    def calculate(trades: List[Trade], equity_curve: List[tuple], initial_capital: float) -> Dict:
        if not trades:
            return {}

        equity_values = [e for _, e in equity_curve]
        dates = [d for d, _ in equity_curve]

        pnls = [t.pnl for t in trades]
        winning_trades = [t for t in trades if t.pnl > 0]
        losing_trades = [t for t in trades if t.pnl <= 0]

        total_pnl = sum(pnls)
        total_return_pct = (total_pnl / initial_capital) * 100

        win_rate = len(winning_trades) / len(trades) if trades else 0

        avg_win = np.mean([t.pnl for t in winning_trades]) if winning_trades else 0
        avg_loss = abs(np.mean([t.pnl for t in losing_trades])) if losing_trades else 0
        profit_factor = abs(sum(t.pnl for t in winning_trades) / sum(abs(t.pnl) for t in losing_trades)) if losing_trades else float('inf')

        max_drawdown = 0
        peak = initial_capital
        for _, eq in equity_curve:
            if eq > peak:
                peak = eq
            dd = (peak - eq) / peak * 100
            if dd > max_drawdown:
                max_drawdown = dd

        if len(equity_values) > 1:
            returns = pd.Series(equity_values).pct_change().dropna()
            sharpe_ratio = np.sqrt(252) * returns.mean() / returns.std() if returns.std() > 0 else 0
            downside_returns = returns[returns < 0]
            sortino_ratio = np.sqrt(252) * returns.mean() / downside_returns.std() if len(downside_returns) > 0 and downside_returns.std() > 0 else 0
        else:
            sharpe_ratio = 0
            sortino_ratio = 0

        avg_holding_bars = 0
        calmar_ratio = total_return_pct / max_drawdown if max_drawdown > 0 else 0

        return {
            'total_return_pct': round(total_return_pct, 2),
            'total_pnl': round(total_pnl, 2),
            'win_rate': round(win_rate * 100, 2),
            'total_trades': len(trades),
            'avg_win': round(avg_win, 2),
            'avg_loss': round(avg_loss, 2),
            'profit_factor': round(profit_factor, 2),
            'max_drawdown_pct': round(max_drawdown, 2),
            'sharpe_ratio': round(sharpe_ratio, 2),
            'sortino_ratio': round(sortino_ratio, 2),
            'calmar_ratio': round(calmar_ratio, 2),
            'final_equity': round(equity_values[-1], 2) if equity_values else initial_capital,
        }
