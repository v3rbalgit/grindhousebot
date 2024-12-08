import pandas as pd
import pandas_ta as ta
import numpy as np
from typing import Optional, Tuple, List
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

    def calculate_indicator(self, df: pd.DataFrame) -> Optional[Tuple[float, float, List[float], float, float]]:
        """
        Calculate MACD values and dynamic threshold.

        Returns:
            Tuple of (MACD line, Signal line, Recent Histograms, Average Divergence, Dynamic Threshold)
            if successful, None otherwise
        """
        try:
            # Calculate MACD efficiently
            close = df['close']
            macd = ta.macd(close, fast=12, slow=26, signal=9)
            if macd is None or macd.empty:
                return None

            try:
                # Get current values
                macd_line = float(macd['MACD_12_26_9'].iat[-1])
                signal_line = float(macd['MACDs_12_26_9'].iat[-1])

                # Get recent histogram values for pattern analysis
                recent_hist = [float(x) for x in macd['MACDh_12_26_9'].tail(5)]

                # Calculate average divergence from recent values
                # Normalize by current price to make it price-independent
                current_price = float(close.iat[-1])
                avg_divergence = abs(macd['MACD_12_26_9'].tail(5).mean()) / current_price

                # Calculate dynamic threshold based on historical divergences
                # Convert all MACD values to price-relative percentages
                historical_macd = np.array(macd['MACD_12_26_9'].values, dtype=np.float64)
                historical_prices = np.array(close.values, dtype=np.float64)

                # Calculate price-relative divergences for the entire history
                # Using broadcasting for efficient calculation
                # Ensure non-zero division by adding small epsilon
                historical_divergences = np.abs(historical_macd / (historical_prices + 1e-10))

                # Use the median absolute deviation as our base threshold
                # This is more robust to outliers than standard deviation
                # Multiply by 1.4826 to make it equivalent to standard deviation for normal distributions
                dynamic_threshold = float(np.median(historical_divergences) * 1.4826)

                # Ensure minimum sensitivity
                MIN_THRESHOLD = 0.001  # 0.1% minimum
                dynamic_threshold = max(dynamic_threshold, MIN_THRESHOLD)

                logger.debug(f"Dynamic threshold calculated: {dynamic_threshold:.4f}")

                return macd_line, signal_line, recent_hist, avg_divergence, dynamic_threshold

            except (IndexError, KeyError) as e:
                logger.error(f"Error accessing MACD values: {e}")
                return None

        except Exception as e:
            logger.error(f"Error calculating MACD: {e}")
            return None

    def analyze_market(self, macd_values: Tuple[float, float, List[float], float, float]) -> Optional[Signal]:
        """
        Generate signal based on MACD divergence with improved confidence scoring.
        Buys on extreme negative divergence, sells on extreme positive divergence.

        Args:
            macd_values: Tuple of (MACD line, Signal line, Recent Histograms, Average Divergence, Dynamic Threshold)

        Returns:
            Signal if conditions are met, None otherwise
        """
        try:
            macd_line, signal_line, recent_hist, avg_divergence, base_threshold = macd_values

            # Current histogram represents current divergence
            curr_hist = recent_hist[-1]

            # Calculate histogram strength relative to recent movement
            hist_max = max(abs(h) for h in recent_hist[:-1])  # Exclude current histogram
            hist_strength = abs(curr_hist) / hist_max if hist_max > 0 else 0

            # Check for buy signal (significant negative divergence)
            if curr_hist < 0:
                # Base confidence from divergence magnitude
                # More negative = higher confidence
                base_confidence = min(abs(avg_divergence) / base_threshold, 1.0)

                # Histogram strength factor
                # Stronger negative histogram indicates stronger oversold condition
                strength_factor = min(hist_strength, 1.0)

                # Trend consistency factor
                # Check if histograms are getting more negative (strengthening oversold)
                trend_factor = 1.0
                if len(recent_hist) >= 3:
                    if abs(curr_hist) > abs(recent_hist[-2]):  # Growing negative histogram
                        trend_factor = 1.2  # 20% bonus
                    elif abs(curr_hist) < abs(recent_hist[-2]) * 0.5:  # Weakening negative histogram
                        trend_factor = 0.8  # 20% penalty

                # Extreme oversold bonus
                extreme_factor = 1.0
                if abs(avg_divergence) > base_threshold * 2:
                    extreme_factor = 1.1  # 10% bonus for extreme divergence

                # Final confidence calculation
                final_confidence = min(
                    base_confidence * 0.5 +          # Divergence magnitude (50%)
                    (strength_factor * 0.3) +        # Histogram strength (30%)
                    (trend_factor * 0.2),            # Trend consistency (20%)
                    1.0
                ) * extreme_factor                   # Apply extreme bonus

                signal = Signal(
                    'macd',
                    SignalType.BUY,
                    f"{avg_divergence:.4f}",
                    final_confidence
                )
                logger.info(f"Buy signal generated with negative MACD divergence {avg_divergence:.4f} (confidence: {final_confidence:.2f})")
                return signal

            # Check for sell signal (significant positive divergence)
            elif curr_hist > 0:
                # Base confidence from divergence magnitude
                # More positive = higher confidence
                base_confidence = min(abs(avg_divergence) / base_threshold, 1.0)

                # Histogram strength factor
                # Stronger positive histogram indicates stronger overbought condition
                strength_factor = min(hist_strength, 1.0)

                # Trend consistency factor
                # Check if histograms are getting more positive (strengthening overbought)
                trend_factor = 1.0
                if len(recent_hist) >= 3:
                    if abs(curr_hist) > abs(recent_hist[-2]):  # Growing positive histogram
                        trend_factor = 1.2  # 20% bonus
                    elif abs(curr_hist) < abs(recent_hist[-2]) * 0.5:  # Weakening positive histogram
                        trend_factor = 0.8  # 20% penalty

                # Extreme overbought bonus
                extreme_factor = 1.0
                if abs(avg_divergence) > base_threshold * 2:
                    extreme_factor = 1.1  # 10% bonus for extreme divergence

                # Final confidence calculation
                final_confidence = min(
                    base_confidence * 0.5 +          # Divergence magnitude (50%)
                    (strength_factor * 0.3) +        # Histogram strength (30%)
                    (trend_factor * 0.2),            # Trend consistency (20%)
                    1.0
                ) * extreme_factor                   # Apply extreme bonus

                signal = Signal(
                    'macd',
                    SignalType.SELL,
                    f"{avg_divergence:.4f}",
                    final_confidence
                )
                logger.info(f"Sell signal generated with positive MACD divergence {avg_divergence:.4f} (confidence: {final_confidence:.2f})")
                return signal

            return None

        except Exception as e:
            logger.error(f"Error analyzing market: {e}")
            return None
