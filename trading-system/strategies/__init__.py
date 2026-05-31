from .base import BaseStrategy
from .sma_crossover import SMACrossoverStrategy
from .rsi_strategy import RSIStrategy
from .macd_strategy import MACDStrategy
from .bollinger_bands import BollingerBandsStrategy
from .ichimoku_cloud import IchimokuCloudStrategy
from .stochastic_rsi import StochasticRSIStrategy
from .adx_strategy import ADXStrategy
from .parabolic_sar import ParabolicSARStrategy
from .volume_profile import VolumeProfileStrategy
from .vwap_reversion import VWAPReversionStrategy
from .fibonacci_retracement import FibonacciRetracementStrategy
from .ema_trend import EMATrendStrategy
from .support_resistance import SupportResistanceStrategy
from .breakout_strategy import BreakoutStrategy

STRATEGY_REGISTRY = {
    'sma_crossover': SMACrossoverStrategy,
    'rsi_strategy': RSIStrategy,
    'macd_strategy': MACDStrategy,
    'bollinger_bands': BollingerBandsStrategy,
    'ichimoku_cloud': IchimokuCloudStrategy,
    'stochastic_rsi': StochasticRSIStrategy,
    'adx_strategy': ADXStrategy,
    'parabolic_sar': ParabolicSARStrategy,
    'volume_profile': VolumeProfileStrategy,
    'vwap_reversion': VWAPReversionStrategy,
    'fibonacci_retracement': FibonacciRetracementStrategy,
    'ema_trend': EMATrendStrategy,
    'support_resistance': SupportResistanceStrategy,
    'breakout_strategy': BreakoutStrategy,
}

__all__ = [
    'BaseStrategy', 'SMACrossoverStrategy', 'RSIStrategy', 'MACDStrategy',
    'BollingerBandsStrategy', 'IchimokuCloudStrategy', 'StochasticRSIStrategy',
    'ADXStrategy', 'ParabolicSARStrategy', 'VolumeProfileStrategy',
    'VWAPReversionStrategy', 'FibonacciRetracementStrategy', 'EMATrendStrategy',
    'SupportResistanceStrategy', 'BreakoutStrategy', 'STRATEGY_REGISTRY',
]
