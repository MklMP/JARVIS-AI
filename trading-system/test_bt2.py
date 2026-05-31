from backtesting.engine import BacktestEngine
engine = BacktestEngine({'backtest': {}})
result = engine.run('AAPL', start='2023-06-01', end='2024-06-01', initial_capital=100000)
print(result)
