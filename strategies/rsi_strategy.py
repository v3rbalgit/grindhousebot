import pandas as pd
import pandas_ta as ta
from typing import Optional, Tuple
from .base import SignalStrategy
from utils.models import Signal, SignalType
from utils.logger import logger


class RSIStrategy(SignalStrategy):
    """RSI-based signal generation strategy."""

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
        return 15  # 14 for RSI + 1 for current candle

    def calculate_indicator(self, df: pd.DataFrame) -> Optional[Tuple[float, float]]:
        """
        Calculate RSI value and its rate of change.

        Returns:
            Tuple of (Current RSI, Previous RSI) if successful, None otherwise
        """
        try:
            # Calculate RSI efficiently
            close = df['close']
            rsi = ta.rsi(close, length=14)
            if rsi is None or rsi.empty or len(rsi) < 2:
                return None

            # Get current and previous RSI values
            current_rsi = float(rsi.iat[-1])
            prev_rsi = float(rsi.iat[-2])

            return current_rsi, prev_rsi

        except Exception as e:
            logger.error(f"Error calculating RSI: {e}")
            return None

    def analyze_market(self, rsi_values: Tuple[float, float]) -> Optional[Signal]:
        """
        Generate signal based on RSI value with improved confidence scoring.

        Args:
            rsi_values: Tuple of (Current RSI, Previous RSI)

        Returns:
            Signal if conditions are met, None otherwise
        """
        try:
            current_rsi, prev_rsi = rsi_values

            # Calculate RSI momentum (rate of change)
            rsi_momentum = current_rsi - prev_rsi

            # Check for oversold conditions (RSI < 30)
            if current_rsi < 30:
                # Base confidence from RSI level
                # More oversold = higher confidence
                # 30 -> 0.0, 20 -> 0.5, 10 -> 1.0
                base_confidence = min((30 - current_rsi) / 20, 1.0)

                # Momentum factor
                # Stronger downward momentum reduces confidence (might go lower)
                # Slowing momentum or reversal increases confidence
                momentum_factor = 1.0
                if rsi_momentum < 0:  # Still falling
                    momentum_factor = max(1.0 + (rsi_momentum / 10), 0.5)  # Cap reduction at 50%
                else:  # Starting to rise
                    momentum_factor = min(1.0 + (rsi_momentum / 20), 1.2)  # Cap increase at 20%

                # Extreme oversold bonus (RSI < 20)
                extreme_factor = 1.0
                if current_rsi < 20:
                    extreme_factor = 1.1  # 10% bonus for extreme oversold

                # Combine factors with weights
                final_confidence = min(
                    base_confidence * 0.6 +          # RSI level (60%)
                    (momentum_factor * 0.4),         # Momentum (40%)
                    1.0
                ) * extreme_factor                   # Apply extreme bonus

                signal = Signal(
                    'rsi',
                    SignalType.BUY,
                    current_rsi,
                    final_confidence
                )
                logger.info(f"Buy signal generated with RSI {current_rsi:.1f} (confidence: {final_confidence:.2f})")
                return signal

            # Check for overbought conditions (RSI > 70)
            elif current_rsi > 70:
                # Base confidence from RSI level
                # More overbought = higher confidence
                # 70 -> 0.0, 80 -> 0.5, 90 -> 1.0
                base_confidence = min((current_rsi - 70) / 20, 1.0)

                # Momentum factor
                # Stronger upward momentum reduces confidence (might go higher)
                # Slowing momentum or reversal increases confidence
                momentum_factor = 1.0
                if rsi_momentum > 0:  # Still rising
                    momentum_factor = max(1.0 - (rsi_momentum / 10), 0.5)  # Cap reduction at 50%
                else:  # Starting to fall
                    momentum_factor = min(1.0 - (rsi_momentum / 20), 1.2)  # Cap increase at 20%

                # Extreme overbought bonus (RSI > 80)
                extreme_factor = 1.0
                if current_rsi > 80:
                    extreme_factor = 1.1  # 10% bonus for extreme overbought

                # Combine factors with weights
                final_confidence = min(
                    base_confidence * 0.6 +          # RSI level (60%)
                    (momentum_factor * 0.4),         # Momentum (40%)
                    1.0
                ) * extreme_factor                   # Apply extreme bonus

                signal = Signal(
                    'rsi',
                    SignalType.SELL,
                    current_rsi,
                    final_confidence
                )
                logger.info(f"Sell signal generated with RSI {current_rsi:.1f} (confidence: {final_confidence:.2f})")
                return signal

            return None

        except Exception as e:
            logger.error(f"Error analyzing market: {e}")
            return None
