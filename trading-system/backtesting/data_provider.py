import pandas as pd
import yfinance as yf
import time as time_module
from typing import Optional, Dict
from datetime import datetime, timedelta
from utils.logger import setup_logger


INTERVAL_LIMITS = {
    '1m':  {'period': '5d',  'ttl': 30},
    '2m':  {'period': '5d',  'ttl': 60},
    '5m':  {'period': '1mo', 'ttl': 120},
    '15m': {'period': '1mo', 'ttl': 300},
    '30m': {'period': '1mo', 'ttl': 600},
    '1h':  {'period': '2mo', 'ttl': 1200},
    '1d':  {'period': '6mo', 'ttl': 3600},
}


class DataProvider:
    def __init__(self):
        self.logger = setup_logger("data_provider")
        self.cache: Dict[str, tuple] = {}

    def _normalize(self, df: pd.DataFrame) -> Optional[pd.DataFrame]:
        try:
            if df is None or df.empty:
                return None
            df = df.copy()
            cols = []
            for c in df.columns:
                if isinstance(c, tuple):
                    cols.append(str(c[0]).lower())
                else:
                    cols.append(str(c).lower())
            df.columns = cols
            df = df[['open', 'high', 'low', 'close', 'volume']]
            df = df.dropna()
            return df
        except Exception as e:
            self.logger.error(f"Normalize error: {e}")
            return None

    def fetch(
        self,
        symbol: str,
        interval: str = '1d',
        period: str = None,
        start: str = None,
        end: str = None,
        force: bool = False
    ) -> Optional[pd.DataFrame]:
        limits = INTERVAL_LIMITS.get(interval, {'period': '1mo', 'ttl': 300})
        if period is None:
            period = limits['period']
        ttl = limits['ttl']
        cache_key = f"{symbol}_{interval}_{period}"
        now = time_module.time()

        if not force and cache_key in self.cache:
            cached_time, cached_df = self.cache[cache_key]
            if now - cached_time < ttl:
                return cached_df

        try:
            if start and end:
                df = yf.download(symbol, start=start, end=end, interval=interval, progress=False)
            else:
                df = yf.download(symbol, period=period, interval=interval, progress=False)

            df = self._normalize(df)
            if df is None or len(df) < 5:
                # Fallback: try daily data
                self.logger.warning(f"{symbol}: fallback to daily")
                df = yf.download(symbol, period='6mo', interval='1d', progress=False)
                df = self._normalize(df)
                if df is None or len(df) < 5:
                    return None

            self.cache[cache_key] = (time_module.time(), df)
            self.logger.info(f"{symbol}: {len(df)} velas ({interval}/{period})")
            return df

        except Exception as e:
            self.logger.error(f"Error {symbol}: {e}")
            return None

    def fetch_latest(self, symbol: str) -> Optional[pd.DataFrame]:
        return self.fetch(symbol, interval='1d', period='1mo', force=True)

    def clear_cache(self):
        self.cache.clear()
        self.logger.info("Cache cleared")
