import pandas as pd
import pandas_ta as ta
from typing import Optional
from .base import SignalStrategy
from utils.models import Signal, SignalType
from utils.logger import logger


class RSIStrategy(SignalStrategy):
    """
    RSI-based signal generation strategy with dynamic thresholds.

    Features:
    - Dynamic RSI thresholds based on market volatility
    - Trend confirmation using EMA crossovers
    - Pattern recognition for stronger signals
    - Volume analysis for confirmation
    """

    def __init__(self, interval: int = 60, window: int = 100) -> None:
        """
        Initialize RSI strategy.

        Args:
            interval: Time interval in minutes
            window: Number of candles to keep
        """
        super().__init__(interval, window)

    @property
    def min_candles(self) -> int:
        """Minimum candles needed for RSI calculation."""
        return 50  # Need enough data for EMAs (50) and RSI (14)

    def calculate_indicator(self, df: pd.DataFrame) -> Optional[float]:
        """Calculate RSI value with additional trend indicators."""
        try:
            # Calculate RSI
            df.ta.rsi(close='close', append=True)
            if 'RSI_14' not in df.columns:
                return None

            return float(df['RSI_14'].iloc[-1])
        except Exception as e:
            logger.error(f"Error calculating RSI: {e}")
            return None

    def analyze_market(self, df: pd.DataFrame, rsi_value: float) -> Optional[Signal]:
        """
        Analyze market conditions using RSI and additional indicators.

        Args:
            df: Price DataFrame
            rsi_value: Current RSI value

        Returns:
            Signal if conditions are met, None otherwise
        """
        try:
            # Get dynamic thresholds based on market conditions
            lower_threshold, upper_threshold = self.calculate_dynamic_thresholds(df)

            # Calculate market trend (only if we have enough data)
            if len(df) >= 50:  # Need at least 50 candles for reliable EMAs
                trend = self.calculate_market_trend(df)
            else:
                trend = 0  # Neutral trend if not enough data

            # Detect patterns
            patterns = self.detect_patterns(df)

            # Volume confirmation
            volume_confirmed = df['volume'].iloc[-1] > df['volume'].rolling(window=20).mean().iloc[-1]

            # Generate signals with multiple confirmations
            signal = None

            if rsi_value < lower_threshold:
                # Potential buy signal
                if trend >= 0:  # Uptrend or neutral confirmation
                    confidence = 0.5 + (abs(trend) * 0.3)  # Base confidence + trend strength

                    # Add pattern confidence
                    if 'double_bottom' in patterns:
                        confidence += patterns['double_bottom'] * 0.2
                    if 'breakout' in patterns:
                        confidence += patterns['breakout'] * 0.2

                    # Volume confirmation
                    if volume_confirmed:
                        confidence += 0.1

                    if confidence > 0.7:  # High confidence threshold
                        signal = Signal(
                            'rsi',
                            SignalType.BUY,
                            rsi_value
                        )
                        logger.info(f"Buy signal generated with confidence {confidence:.2f}")

            elif rsi_value > upper_threshold:
                # Potential sell signal
                if trend <= 0:  # Downtrend or neutral confirmation
                    confidence = 0.5 + (abs(trend) * 0.3)  # Base confidence + trend strength

                    # Add pattern confidence
                    if 'volume_spike' in patterns:
                        confidence += patterns['volume_spike'] * 0.2

                    # Volume confirmation
                    if volume_confirmed:
                        confidence += 0.1

                    if confidence > 0.7:  # High confidence threshold
                        signal = Signal(
                            'rsi',
                            SignalType.SELL,
                            rsi_value
                        )
                        logger.info(f"Sell signal generated with confidence {confidence:.2f}")

            return signal

        except Exception as e:
            logger.error(f"Error analyzing market: {e}")
            return None
