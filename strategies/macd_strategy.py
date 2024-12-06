import pandas as pd
import pandas_ta as ta
from typing import Optional
from .base import SignalStrategy
from utils.models import Signal, SignalType
from utils.logger import logger


class MACDStrategy(SignalStrategy):
    """MACD-based signal generation strategy."""

    def __init__(self, interval: int = 60, window: int = 100) -> None:
        """
        Initialize MACD strategy.

        Args:
            interval: Time interval in minutes
            window: Number of candles to keep
        """
        super().__init__(interval, window)

    @property
    def min_candles(self) -> int:
        """Minimum candles needed for MACD calculation."""
        return 27  # 26 for slow MA + 1 for current candle

    def process(self, symbol: str) -> Optional[Signal]:
        """Generate MACD-based signal."""
        df = self.dataframes[symbol]
        df.ta.macd(close='close', fast=12, slow=26, signal=9, append=True)

        if 'MACDh_12_26_9' not in df.columns:
            return None

        # Get last two MACD histogram values
        hist = df['MACDh_12_26_9'].iloc[-2:]
        if len(hist) < 2 or hist.isna().any():
            return None

        prev_macd = float(hist.iloc[0])
        cur_macd = float(hist.iloc[1])

        if cur_macd > 0 and prev_macd < 0:
            logger.debug(f"MACD bullish crossover for {symbol}")
            return Signal('macd', SignalType.BUY, 'bullish crossover')
        if cur_macd < 0 and prev_macd > 0:
            logger.debug(f"MACD bearish crossover for {symbol}")
            return Signal('macd', SignalType.SELL, 'bearish crossover')

        return None
