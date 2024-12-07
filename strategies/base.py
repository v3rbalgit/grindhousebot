from abc import ABC, abstractmethod
import pandas as pd
from typing import Dict, Optional, Any
from utils.models import PriceData, Signal
from utils.logger import logger


class SignalStrategy(ABC):
    """Abstract base class for signal generation strategies."""

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
            try:
                # Create new data with timestamp as index
                timestamp = pd.to_datetime(price.timestamp)
                new_data = pd.DataFrame(
                    [price.to_dict()],
                    index=[timestamp]
                )

                if symbol not in self.dataframes:
                    self.dataframes[symbol] = new_data
                    logger.debug(f"Created new DataFrame for {symbol}")
                else:
                    df = self.dataframes[symbol]

                    # Ensure index is datetime (only if needed)
                    if not isinstance(df.index, pd.DatetimeIndex):
                        df.index = pd.to_datetime(df.index)

                    # Optimize DataFrame operations
                    if len(df) >= self.window:
                        # If at max window, drop oldest and append new
                        df = pd.concat([df.iloc[-(self.window-1):], new_data])
                    else:
                        # Otherwise just append
                        df = pd.concat([df, new_data])

                    # Remove duplicates and sort (if needed)
                    if df.index.duplicated().any():
                        df = df[~df.index.duplicated(keep='last')].sort_index()

                    self.dataframes[symbol] = df

                # Generate signal if we have enough data
                if len(self.dataframes[symbol]) >= self.min_candles:
                    signals[symbol] = self.process(symbol)
                else:
                    logger.debug(f"Insufficient data for {symbol} ({len(self.dataframes[symbol])}/{self.min_candles} candles)")
                    signals[symbol] = None

            except Exception as e:
                logger.error(f"Error processing data for {symbol}: {e}")
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
    def calculate_indicator(self, df: pd.DataFrame) -> Any:
        """
        Calculate the strategy's indicator value(s).

        Args:
            df: Price DataFrame

        Returns:
            Calculated indicator value(s)
        """
        pass

    @abstractmethod
    def analyze_market(self, indicator_value: Any) -> Optional[Signal]:
        """
        Analyze market conditions and generate signal.

        Args:
            indicator_value: Current indicator value(s)

        Returns:
            Signal if conditions are met, None otherwise
        """
        pass

    def process(self, symbol: str) -> Optional[Signal]:
        """
        Process price data and generate signal.

        Args:
            symbol: Trading symbol to process

        Returns:
            Signal if conditions are met, None otherwise
        """
        try:
            df = self.dataframes[symbol]

            # Calculate indicator
            indicator_value = self.calculate_indicator(df)
            if indicator_value is None:
                return None

            # Analyze market
            return self.analyze_market(indicator_value)

        except Exception as e:
            logger.error(f"Error processing {symbol}: {e}")

        return None
