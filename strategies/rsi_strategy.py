import pandas as pd
import pandas_ta as ta
from typing import Optional
from .base import SignalStrategy
from utils.models import Signal, SignalType
from utils.logger import logger

class RSIStrategy(SignalStrategy):
    """RSI-based signal generation strategy."""

    def __init__(self, interval: int = 60, window: int = 100, buy: int = 30, sell: int = 70) -> None:
        """
        Initialize RSI strategy.

        Args:
            interval: Time interval in minutes
            window: Number of candles to keep
            buy: RSI buy threshold (oversold)
            sell: RSI sell threshold (overbought)
        """
        super().__init__(interval, window)
        self.buy = min(buy, sell - 1)  # Ensure buy < sell
        self.sell = max(sell, buy + 1)  # Ensure sell > buy
        logger.info(f"RSI signal thresholds: buy={self.buy}, sell={self.sell}")

    @property
    def min_candles(self) -> int:
        """Minimum candles needed for RSI calculation."""
        return 15  # 14 for RSI + 1 for current candle

    def process(self, symbol: str) -> Optional[Signal]:
        """Generate RSI-based signal."""
        df = self.dataframes[symbol]
        df.ta.rsi(close='close', append=True)

        if 'RSI_14' not in df.columns:
            return None

        # Get latest RSI value
        rsi = float(df['RSI_14'].iloc[-1])

        if rsi > self.sell and rsi != 100:
            logger.debug(f"RSI overbought signal for {symbol}: {rsi:.2f}")
            return Signal('rsi', SignalType.SELL, rsi)
        if rsi < self.buy and rsi != 0:
            logger.debug(f"RSI oversold signal for {symbol}: {rsi:.2f}")
            return Signal('rsi', SignalType.BUY, rsi)

        return None
