from abc import ABC, abstractmethod
import pandas as pd
import pandas_ta as ta
from typing import Dict, Optional
from utils.models import PriceData, Signal
from utils.logger import logger


class SignalStrategy(ABC):
    """
    Abstract base class for signal generation strategies.

    Optimized for AWS Lambda:
    - Minimal memory footprint
    - Efficient DataFrame operations
    - No persistent storage
    """

    def __init__(self, interval: int, window: int) -> None:
        """
        Initialize the strategy.

        Args:
            interval: Time interval in minutes
            window: Maximum number of candles to keep in memory
        """
        self.interval = interval
        self.window = window
        self.dataframes: Dict[str, pd.DataFrame] = {}
        logger.info(f"Initialized {self.__class__.__name__} (interval={interval}, window={window})")

    def generate_signals(self, prices: Dict[str, PriceData]) -> Dict[str, Optional[Signal]]:
        """
        Generate signals from price data.

        Args:
            prices: Dictionary of symbol to latest price data

        Returns:
            Dictionary of symbol to signal (if any)
        """
        signals = {}

        for symbol, price in prices.items():
            # Create or update price DataFrame
            new_data = pd.DataFrame(
                [price.to_dict()],
                index=[price.timestamp]
            )

            if symbol not in self.dataframes:
                self.dataframes[symbol] = new_data
                logger.debug(f"Created new DataFrame for {symbol}")
            else:
                df = self.dataframes[symbol]
                df = pd.concat([df, new_data])

                # Keep only required window of data
                if len(df) > self.window:
                    df = df.iloc[-self.window:]

                self.dataframes[symbol] = df

            # Generate signal if we have enough data
            if len(self.dataframes[symbol]) >= self.min_candles:
                signals[symbol] = self.process(symbol)
            else:
                logger.debug(f"Insufficient data for {symbol} ({len(self.dataframes[symbol])}/{self.min_candles} candles)")
                signals[symbol] = None

        return signals

    def cleanup(self) -> None:
        """Clean up resources to free memory."""
        count = len(self.dataframes)
        self.dataframes.clear()
        logger.debug(f"Cleared {count} DataFrames from memory")

    @property
    @abstractmethod
    def min_candles(self) -> int:
        """Minimum number of candles needed for the strategy."""
        pass

    @abstractmethod
    def process(self, symbol: str) -> Optional[Signal]:
        """
        Process price data and generate signal.

        Args:
            symbol: Trading symbol to process

        Returns:
            Signal if conditions are met, None otherwise
        """
        pass