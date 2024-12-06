import pandas as pd
import pandas_ta as ta
from typing import Optional, Tuple
from .base import SignalStrategy
from utils.models import Signal, SignalType
from utils.logger import logger


class MACDStrategy(SignalStrategy):
    """
    MACD-based signal generation strategy with dynamic analysis.

    Features:
    - MACD crossover detection
    - Trend strength confirmation
    - Volume analysis
    - Pattern recognition
    """

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

    def calculate_indicator(self, df: pd.DataFrame) -> Optional[Tuple[float, float, float]]:
        """
        Calculate MACD values with additional trend indicators.

        Returns:
            Tuple of (MACD line, Signal line, Histogram) if successful, None otherwise
        """
        try:
            # Calculate MACD efficiently
            close = df['close']
            macd = ta.macd(close, fast=12, slow=26, signal=9)
            if macd is None or macd.empty:
                return None

            try:
                # Use iat for efficient single value access
                macd_line = float(macd['MACD_12_26_9'].iat[-1])
                signal_line = float(macd['MACDs_12_26_9'].iat[-1])
                histogram = float(macd['MACDh_12_26_9'].iat[-1])

                # Store histogram for pattern detection
                df['MACDh_12_26_9'] = macd['MACDh_12_26_9']

                return macd_line, signal_line, histogram

            except (IndexError, KeyError) as e:
                logger.error(f"Error accessing MACD values: {e}")
                return None

        except Exception as e:
            logger.error(f"Error calculating MACD: {e}")
            return None

    def analyze_market(self, df: pd.DataFrame, macd_values: Tuple[float, float, float]) -> Optional[Signal]:
        """
        Analyze market conditions using MACD and additional indicators.

        Args:
            df: Price DataFrame
            macd_values: Tuple of (MACD line, Signal line, Histogram)

        Returns:
            Signal if conditions are met, None otherwise
        """
        try:
            macd_line, signal_line, histogram = macd_values

            # Get previous histogram value efficiently
            try:
                prev_histogram = float(df['MACDh_12_26_9'].iat[-2])
            except (IndexError, KeyError) as e:
                logger.error(f"Error accessing previous histogram: {e}")
                return None

            # Calculate market trend
            trend = self.calculate_market_trend(df)

            # Detect patterns
            patterns = self.detect_patterns(df)

            # Volume confirmation (optimized)
            volume = df['volume']
            volume_ma = volume.rolling(window=20).mean()
            volume_confirmed = volume.iat[-1] > volume_ma.iat[-1]

            # Generate signals with multiple confirmations
            signal = None

            # Check for bullish signal
            if histogram > 0 and prev_histogram < 0:  # Bullish crossover
                if trend > 0:  # Uptrend confirmation
                    confidence = 0.5 + (abs(trend) * 0.3)  # Base confidence + trend strength

                    # Add pattern confidence
                    if 'double_bottom' in patterns:
                        confidence += patterns['double_bottom'] * 0.2
                    if 'breakout' in patterns:
                        confidence += patterns['breakout'] * 0.2

                    # Volume confirmation
                    if volume_confirmed:
                        confidence += 0.1

                    # MACD strength confirmation (with safety check)
                    if signal_line != 0:
                        macd_strength = abs(macd_line - signal_line) / abs(signal_line)
                        confidence += min(macd_strength * 0.2, 0.2)

                    if confidence > 0.7:  # High confidence threshold
                        signal = Signal(
                            'macd',
                            SignalType.BUY,
                            'bullish crossover'
                        )
                        logger.info(f"Buy signal generated with confidence {confidence:.2f}")

            # Check for bearish signal
            elif histogram < 0 and prev_histogram > 0:  # Bearish crossover
                if trend < 0:  # Downtrend confirmation
                    confidence = 0.5 + (abs(trend) * 0.3)  # Base confidence + trend strength

                    # Add pattern confidence
                    if 'volume_spike' in patterns:
                        confidence += patterns['volume_spike'] * 0.2

                    # Volume confirmation
                    if volume_confirmed:
                        confidence += 0.1

                    # MACD strength confirmation (with safety check)
                    if signal_line != 0:
                        macd_strength = abs(macd_line - signal_line) / abs(signal_line)
                        confidence += min(macd_strength * 0.2, 0.2)

                    if confidence > 0.7:  # High confidence threshold
                        signal = Signal(
                            'macd',
                            SignalType.SELL,
                            'bearish crossover'
                        )
                        logger.info(f"Sell signal generated with confidence {confidence:.2f}")

            return signal

        except Exception as e:
            logger.error(f"Error analyzing market: {e}")
            return None
