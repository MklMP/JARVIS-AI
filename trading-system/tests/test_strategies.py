import pytest
import pandas as pd
import numpy as np
from strategies import (
    SMACrossoverStrategy, RSIStrategy, MACDStrategy,
    BollingerBandsStrategy, ADXStrategy, EMATrendStrategy,
    VolumeProfileStrategy, BreakoutStrategy
)


def make_sample_df(length=100):
    np.random.seed(42)
    close = 100 + np.cumsum(np.random.randn(length) * 0.5)
    df = pd.DataFrame({
        'open': close - np.random.rand(length) * 0.5,
        'high': close + np.random.rand(length) * 1.0,
        'low': close - np.random.rand(length) * 1.0,
        'close': close,
        'volume': np.random.randint(1000000, 5000000, length)
    })
    return df


class TestSMACrossover:
    def test_initialization(self):
        s = SMACrossoverStrategy({'fast_period': 9, 'slow_period': 21})
        assert s.name == 'sma_crossover'

    def test_generates_signal(self):
        s = SMACrossoverStrategy()
        df = make_sample_df(100)
        result = s.generate_signal(df)
        assert 'action' in result
        assert 'confidence' in result
        assert result['action'] in ('buy', 'sell', 'hold')


class TestRSIStrategy:
    def test_generates_signal(self):
        s = RSIStrategy()
        df = make_sample_df(100)
        result = s.generate_signal(df)
        assert result['action'] in ('buy', 'sell', 'hold')

    def test_oversold_signal(self):
        s = RSIStrategy({'oversold': 40})
        df = make_sample_df(100)
        from utils.indicators import add_all_indicators
        df = add_all_indicators(df)
        df['rsi'] = 25.0
        df['rsi'].iloc[-1] = 25.0
        df['rsi'].iloc[-2] = 20.0
        result = s.generate_signal(df)
        assert result['action'] in ('buy', 'hold')


class TestMACDStrategy:
    def test_generates_signal(self):
        s = MACDStrategy()
        df = make_sample_df(100)
        result = s.generate_signal(df)
        assert result['action'] in ('buy', 'sell', 'hold')


class TestBollingerBands:
    def test_generates_signal(self):
        s = BollingerBandsStrategy()
        df = make_sample_df(100)
        result = s.generate_signal(df)
        assert result['action'] in ('buy', 'sell', 'hold')


class TestADXStrategy:
    def test_generates_signal(self):
        s = ADXStrategy()
        df = make_sample_df(100)
        result = s.generate_signal(df)
        assert result['action'] in ('buy', 'sell', 'hold')


class TestEMATrend:
    def test_generates_signal(self):
        s = EMATrendStrategy()
        df = make_sample_df(100)
        result = s.generate_signal(df)
        assert result['action'] in ('buy', 'sell', 'hold')


class TestSignalCombiner:
    def test_combine_signals(self):
        from core.signal_combiner import SignalCombiner, Signal
        combiner = SignalCombiner()
        signals = [
            Signal(symbol='AAPL', action='buy', confidence=0.8,
                   strategy_name='sma', price=150.0),
            Signal(symbol='AAPL', action='buy', confidence=0.6,
                   strategy_name='rsi', price=150.0),
            Signal(symbol='AAPL', action='sell', confidence=0.4,
                   strategy_name='macd', price=150.0),
        ]
        combined = combiner.combine(signals, {'sma': 1.0, 'rsi': 1.0, 'macd': 1.0})
        assert combined.action == 'buy'
        assert combined.symbol == 'AAPL'
        assert combined.confidence > 0


class TestPortfolio:
    def test_open_close_position(self):
        from core.portfolio import Portfolio, Position
        from datetime import datetime
        p = Portfolio(100000)
        pos = Position(
            symbol='AAPL', quantity=10, entry_price=150,
            current_price=150, stop_loss=140, take_profit=170,
            side='buy', entry_time=datetime.now()
        )
        assert p.open_position(pos) == True
        assert p.position_count == 1
        assert abs(p.cash - (100000 - 1500)) < 0.01

        trade = p.close_position('AAPL', 160)
        assert trade is not None
        assert trade.pnl == 100.0
        assert p.position_count == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
