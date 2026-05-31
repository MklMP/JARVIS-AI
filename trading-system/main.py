import os
import sys
import yaml
import argparse
from datetime import datetime

from core.engine import TradingEngine
from backtesting.engine import BacktestEngine
from ml.model_trainer import ModelTrainer
from ml.signal_filter import MLSignalFilter
from backtesting.data_provider import DataProvider
from utils.logger import setup_logger


def load_config():
    config_path = os.path.join(os.path.dirname(__file__), 'config', 'config.yaml')
    if os.path.exists(config_path):
        with open(config_path) as f:
            return yaml.safe_load(f)
    return {}


def cmd_backtest(args):
    config = load_config()
    engine = BacktestEngine(config)
    symbols = args.symbols.split(',') if args.symbols else config.get('trading', {}).get('symbols', ['AAPL'])
    results = engine.run_multi(symbols)
    return results


def cmd_analyze(args):
    config = load_config()
    engine = TradingEngine(config)
    provider = DataProvider()
    symbols = args.symbols.split(',') if args.symbols else config.get('trading', {}).get('symbols', ['AAPL'])

    for symbol in symbols:
        df = provider.fetch(symbol, interval=args.timeframe or '1d', period=args.period or '6mo')
        if df is not None:
            signal = engine.analyze_market(symbol, df)
            print(f"\n{'='*50}")
            print(f"ANALYSIS: {symbol}")
            print(f"{'='*50}")
            print(f"Action: {signal['action'].upper()}")
            print(f"Confidence: {signal['confidence']:.2%}")
            print(f"Weighted Score: {signal['weighted_score']:.4f}")
            print(f"Agreement: {signal['agreement_ratio']:.2%}")
            print(f"\nSignals breakdown:")
            for s in signal['signals']:
                print(f"  {s['strategy']:25s}: {s['action']:5s} (conf: {s['confidence']:.2%})")
            print()


def cmd_train(args):
    config = load_config()
    provider = DataProvider()
    trainer = ModelTrainer(config)

    symbols = args.symbols.split(',') if args.symbols else config.get('trading', {}).get('symbols', ['AAPL', 'MSFT'])

    all_data = None
    for symbol in symbols:
        df = provider.fetch(symbol, interval='1d', period='2y')
        if df is not None:
            from utils.indicators import add_all_indicators
            df = add_all_indicators(df)
            all_data = df if all_data is None else pd.concat([all_data, df])

    if all_data is not None:
        results = trainer.train(all_data)
        print(f"\nTraining Results:")
        for k, v in results.items():
            print(f"  {k}: {v}")
        if args.save:
            trainer.save_model()
    else:
        print("No data available for training")


def cmd_live(args):
    config = load_config()
    provider = DataProvider()
    engine = TradingEngine(config)
    symbols = args.symbols.split(',') if args.symbols else config.get('trading', {}).get('symbols', ['AAPL'])

    print(f"\n{'='*50}")
    print(f"LIVE TRADING - Press Ctrl+C to stop")
    print(f"{'='*50}\n")

    try:
        import time
        while True:
            for symbol in symbols:
                df = provider.fetch(symbol, interval=args.timeframe or '15m', period='5d')
                if df is None:
                    continue
                signal = engine.analyze_market(symbol, df)
                execution = engine.execute_signal(symbol, signal, df)
                if execution:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] {execution['action'].upper()} {execution['symbol']}: "
                          f"{execution['quantity']:.0f} @ ${execution['price']:.2f}")
            status = engine.get_status()
            print(f"  Equity: ${status['total_equity']:.2f} | "
                  f"Positions: {status['open_positions']} | "
                  f"PnL: ${status['total_pnl']:.2f}")
            time.sleep(60)
    except KeyboardInterrupt:
        print("\nStopped.")


def cmd_interactive(args):
    config = load_config()
    engine = TradingEngine(config)
    provider = DataProvider()

    print("\n" + "="*60)
    print("  QUANTUMTRADE INTERACTIVE ENGINE")
    print("="*60)
    print(f"  Active Strategies: {engine.strategy_manager.get_strategy_count()}")
    print(f"  Tracked Symbols: {', '.join(config.get('trading', {}).get('symbols', ['AAPL']))}")
    print("="*60)
    print("  Commands: analyze <symbol> | status | backtest <symbol> | quit")
    print("="*60)

    while True:
        try:
            cmd = input("\n>> ").strip().lower()
            if cmd in ('quit', 'exit', 'q'):
                break
            elif cmd == 'status':
                s = engine.get_status()
                print(f"\nEquity: ${s['total_equity']:.2f}")
                print(f"Cash: ${s['cash']:.2f}")
                print(f"Positions: {s['open_positions']}")
                print(f"PnL: {s['total_pnl_pct']:.2f}%")
                print(f"Win Rate: {s['win_rate']:.1f}%")
                print(f"Trades: {s['total_trades']}")
                for p in s.get('positions', []):
                    print(f"  {p['symbol']}: {p['quantity']:.0f} @ ${p['entry']:.2f} "
                          f"(PnL: {p['pnl_pct']:.2f}%)")
            elif cmd.startswith('analyze'):
                parts = cmd.split()
                symbol = parts[1] if len(parts) > 1 else 'AAPL'
                df = provider.fetch(symbol, interval='1d', period='6mo')
                if df is not None:
                    signal = engine.analyze_market(symbol, df)
                    print(f"\n{symbol}: {signal['action'].upper()} (conf: {signal['confidence']:.2%})")
                    for s in signal['signals']:
                        print(f"  {s['strategy']:25s}: {s['action']:5s} ({s['confidence']:.2%})")
            elif cmd.startswith('backtest'):
                parts = cmd.split()
                symbol = parts[1] if len(parts) > 1 else 'AAPL'
                be = BacktestEngine(config)
                be.run(symbol)
            elif cmd == 'strategies':
                for s in engine.strategy_manager.get_active_strategies():
                    print(f"  - {s}")
            else:
                print("Unknown command. Try: analyze <symbol>, status, backtest <symbol>, strategies, quit")
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"Error: {e}")

    print("Goodbye!")


def main():
    parser = argparse.ArgumentParser(description="QuantumTrade - AI Trading Engine")
    parser.add_argument('--version', action='version', version='1.0.0')

    subparsers = parser.add_subparsers(dest='command', help='Commands')

    p_analyze = subparsers.add_parser('analyze', help='Analyze market')
    p_analyze.add_argument('--symbols', default='', help='Comma-separated symbols')
    p_analyze.add_argument('--timeframe', default='1d', help='Timeframe')
    p_analyze.add_argument('--period', default='6mo', help='Period')

    p_backtest = subparsers.add_parser('backtest', help='Run backtest')
    p_backtest.add_argument('--symbols', default='', help='Comma-separated symbols')
    p_backtest.add_argument('--start', default='2023-01-01')
    p_backtest.add_argument('--end', default='2024-01-01')

    p_train = subparsers.add_parser('train', help='Train ML model')
    p_train.add_argument('--symbols', default='', help='Comma-separated symbols')
    p_train.add_argument('--save', action='store_true', help='Save model')

    p_live = subparsers.add_parser('live', help='Run live trading')
    p_live.add_argument('--symbols', default='', help='Comma-separated symbols')
    p_live.add_argument('--timeframe', default='15m')

    subparsers.add_parser('interactive', help='Interactive mode')
    subparsers.add_parser('server', help='Start webhook server')

    args = parser.parse_args()

    if args.command == 'analyze':
        cmd_analyze(args)
    elif args.command == 'backtest':
        cmd_backtest(args)
    elif args.command == 'train':
        cmd_train(args)
    elif args.command == 'live':
        cmd_live(args)
    elif args.command == 'interactive':
        cmd_interactive(args)
    elif args.command == 'server':
        import uvicorn
        config = load_config()
        host = config.get('server', {}).get('host', '0.0.0.0')
        port = config.get('server', {}).get('port', 8080)
        uvicorn.run("server:app", host=host, port=port, reload=False)
    else:
        parser.print_help()


if __name__ == "__main__":
    import pandas as pd
    main()
