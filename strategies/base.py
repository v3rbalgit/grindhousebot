from abc import ABC, abstractmethod
import pandas as pd
import pandas_ta as ta
from typing import Dict, Optional, Any, Tuple
from utils.models import PriceData, Signal
from utils.logger import logger


class SignalStrategy(ABC):
    """
    Abstract base class for signal generation strategies.

    Features:
    - Dynamic threshold calculation
    - Market trend analysis
    - Pattern recognition
    - Adaptive signal generation
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

    def calculate_market_trend(self, df: pd.DataFrame, period: int = 20) -> float:
        """
        Calculate the overall market trend using multiple indicators.

        Args:
            df: Price DataFrame
            period: Period for trend calculation

        Returns:
            Trend strength (-1 to 1, where -1 is strong downtrend, 1 is strong uptrend)
        """
        try:
            if len(df) < 50:  # Need at least 50 candles for reliable EMAs
                return 0

            # Calculate EMAs for trend direction
            ema20 = ta.ema(df['close'], length=20)
            ema50 = ta.ema(df['close'], length=50)

            # Calculate ADX for trend strength
            adx = ta.adx(df['high'], df['low'], df['close'])

            # Check for None values
            if ema20 is None or ema50 is None or adx is None:
                return 0

            # Get latest values, ensuring they exist
            ema20_last = ema20.iloc[-1] if not ema20.empty else None
            ema50_last = ema50.iloc[-1] if not ema50.empty else None
            adx_last = adx['ADX_14'].iloc[-1] if not adx.empty else None

            # Safety check for None values
            if ema20_last is None or ema50_last is None or adx_last is None:
                return 0

            # Calculate trend
            ema_trend = 1 if ema20_last > ema50_last else -1
            adx_strength = min(float(adx_last) / 100, 1)  # Normalize to 0-1

            # Combine signals
            trend = ema_trend * adx_strength

            return trend
        except Exception as e:
            logger.error(f"Error calculating market trend: {e}")
            return 0

    def detect_patterns(self, df: pd.DataFrame) -> Dict[str, float]:
        """
        Detect common chart patterns.

        Args:
            df: Price DataFrame

        Returns:
            Dictionary of pattern names to confidence levels (0-1)
        """
        patterns = {}
        try:
            # Example patterns (extend based on strategy needs):

            # Double Bottom
            if len(df) >= 20:
                lows = df['low'].rolling(window=5).min()
                if len(lows.unique()) >= 2:
                    recent_lows = lows.tail(20)
                    min_points = recent_lows[recent_lows == recent_lows.min()].index
                    if len(min_points) >= 2:
                        patterns['double_bottom'] = 0.8

            # Breakout
            if len(df) >= 10:
                recent_high = df['high'].rolling(window=10).max().iloc[-1]
                if df['close'].iloc[-1] > recent_high:
                    patterns['breakout'] = 0.9

            # Volume Spike
            if len(df) >= 5:
                avg_volume = df['volume'].rolling(window=5).mean().iloc[-1]
                if df['volume'].iloc[-1] > avg_volume * 2:
                    patterns['volume_spike'] = 0.7

        except Exception as e:
            logger.error(f"Error detecting patterns: {e}")

        return patterns

    def calculate_dynamic_thresholds(self, df: pd.DataFrame) -> Tuple[float, float]:
        """
        Calculate dynamic thresholds based on market conditions.

        Args:
            df: Price DataFrame

        Returns:
            Tuple of (lower_threshold, upper_threshold)
        """
        try:
            # Calculate volatility
            returns = df['close'].pct_change()
            volatility = returns.std()

            # Adjust thresholds based on volatility
            base_lower = 30
            base_upper = 70

            # More volatile markets need wider thresholds
            volatility_factor = min(volatility * 100, 1)  # Cap at 100%
            threshold_adjustment = 10 * volatility_factor

            lower_threshold = base_lower - threshold_adjustment
            upper_threshold = base_upper + threshold_adjustment

            return lower_threshold, upper_threshold
        except Exception as e:
            logger.error(f"Error calculating dynamic thresholds: {e}")
            return 30, 70  # Default values

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
    def analyze_market(self, df: pd.DataFrame, indicator_value: Any) -> Optional[Signal]:
        """
        Analyze market conditions and generate signal.

        Args:
            df: Price DataFrame
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

            # Calculate main indicator
            indicator_value = self.calculate_indicator(df)
            if indicator_value is None:
                return None

            # Get market analysis signal
            return self.analyze_market(df, indicator_value)

        except Exception as e:
            logger.error(f"Error processing {symbol}: {e}")

        return None