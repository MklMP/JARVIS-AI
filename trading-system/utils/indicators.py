import numpy as np
import pandas as pd
import ta


def add_all_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df = df.rename(columns={
        'Open': 'open', 'High': 'high', 'Low': 'low',
        'Close': 'close', 'Volume': 'volume'
    }, errors='ignore')
    df.columns = [c.lower() for c in df.columns]

    df['sma_9'] = ta.trend.sma_indicator(df['close'], window=9)
    df['sma_21'] = ta.trend.sma_indicator(df['close'], window=21)
    df['sma_50'] = ta.trend.sma_indicator(df['close'], window=50)
    df['sma_200'] = ta.trend.sma_indicator(df['close'], window=200)

    df['ema_9'] = ta.trend.ema_indicator(df['close'], window=9)
    df['ema_21'] = ta.trend.ema_indicator(df['close'], window=21)
    df['ema_50'] = ta.trend.ema_indicator(df['close'], window=50)
    df['ema_200'] = ta.trend.ema_indicator(df['close'], window=200)

    df['rsi'] = ta.momentum.rsi(df['close'], window=14)

    macd = ta.trend.MACD(df['close'])
    df['macd'] = macd.macd()
    df['macd_signal'] = macd.macd_signal()
    df['macd_diff'] = macd.macd_diff()

    bb = ta.volatility.BollingerBands(df['close'], window=20, window_dev=2)
    df['bb_high'] = bb.bollinger_hband()
    df['bb_mid'] = bb.bollinger_mavg()
    df['bb_low'] = bb.bollinger_lband()
    df['bb_width'] = (df['bb_high'] - df['bb_low']) / df['bb_mid']
    df['bb_position'] = (df['close'] - df['bb_low']) / (df['bb_high'] - df['bb_low'])

    df['atr'] = ta.volatility.average_true_range(df['high'], df['low'], df['close'], window=14)

    df['adx'] = ta.trend.adx(df['high'], df['low'], df['close'], window=14)

    stoch = ta.momentum.StochasticOscillator(
        df['high'], df['low'], df['close'], window=14, smooth_window=3
    )
    df['stoch_k'] = stoch.stoch()
    df['stoch_d'] = stoch.stoch_signal()

    df['cci'] = ta.trend.cci(df['high'], df['low'], df['close'], window=20)

    df['williams_r'] = ta.momentum.williams_r(df['high'], df['low'], df['close'], lbp=14)

    df['obv'] = ta.volume.on_balance_volume(df['close'], df['volume'])
    df['volume_sma'] = ta.trend.sma_indicator(df['volume'], window=20)
    df['volume_ratio'] = df['volume'] / df['volume_sma']

    df['vwap'] = (df['volume'] * (df['high'] + df['low'] + df['close']) / 3).cumsum() / df['volume'].cumsum()

    df['price_position'] = (df['close'] - df['low'].rolling(50).min()) / (
        df['high'].rolling(50).max() - df['low'].rolling(50).min()
    )

    df['volatility'] = df['close'].pct_change().rolling(20).std()

    df['momentum_1'] = df['close'].pct_change(1)
    df['momentum_5'] = df['close'].pct_change(5)
    df['momentum_10'] = df['close'].pct_change(10)

    df['returns'] = df['close'].pct_change()
    df['log_returns'] = np.log(df['close'] / df['close'].shift(1))

    df['support'] = df['low'].rolling(20).min()
    df['resistance'] = df['high'].rolling(20).max()

    return df


def detect_divergence(df: pd.DataFrame, lookback: int = 20) -> dict:
    result = {
        'rsi_bullish_div': False,
        'rsi_bearish_div': False,
        'macd_bullish_div': False,
        'macd_bearish_div': False,
    }
    recent = df.tail(lookback)

    price_low = recent['close'].min()
    price_high = recent['close'].max()
    price_low_idx = recent['close'].idxmin()
    price_high_idx = recent['close'].idxmax()

    rsi_low = recent['rsi'].min()
    rsi_high = recent['rsi'].max()
    rsi_low_idx = recent['rsi'].idxmin()
    rsi_high_idx = recent['rsi'].idxmax()

    if price_low_idx < rsi_low_idx and price_low < recent.loc[price_low_idx, 'close']:
        result['rsi_bullish_div'] = True
    if price_high_idx < rsi_high_idx and price_high > recent.loc[price_high_idx, 'close']:
        result['rsi_bearish_div'] = True

    macd_low = recent['macd'].min()
    macd_high = recent['macd'].max()
    macd_low_idx = recent['macd'].idxmin()
    macd_high_idx = recent['macd'].idxmax()

    if price_low_idx < macd_low_idx:
        result['macd_bullish_div'] = True
    if price_high_idx < macd_high_idx:
        result['macd_bearish_div'] = True

    return result
