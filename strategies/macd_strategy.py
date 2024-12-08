import pandas as pd
import pandas_ta as ta
from typing import Optional, Tuple, List
from .base import SignalStrategy
from utils.models import Signal, SignalType
from utils.logger import logger


class MACDStrategy(SignalStrategy):
    """MACD-based signal generation strategy."""

    # Base threshold for significant divergence (1% of price)
    BASE_DIVERGENCE_THRESHOLD = 0.01

    def __init__(self, interval: int = 60, window: int = 100) -> None:
        """

        Args:
            interval: Time interval in minutes
            window: Number of candles to keep
        """
        super().__init__(interval, window)

    @property
    def min_candles(self) -> int:
        """Minimum candles needed for MACD calculation."""
        return 27  # 26 for slow MA + 1 for current candle

    def calculate_indicator(self, df: pd.DataFrame) -> Optional[Tuple[float, float, List[float], float]]:
        """
        Calculate MACD values.

        Returns:
            Tuple of (MACD line, Signal line, Recent Histograms, Average Divergence) if successful, None otherwise
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

                return macd_line, signal_line, recent_hist, avg_divergence

            except (IndexError, KeyError) as e:
                logger.error(f"Error accessing MACD values: {e}")
                return None

        except Exception as e:
            logger.error(f"Error calculating MACD: {e}")
            return None

    def analyze_market(self, macd_values: Tuple[float, float, List[float], float]) -> Optional[Signal]:
        """
        Generate signal based on MACD divergence with improved confidence scoring.
        Buys on extreme negative divergence, sells on extreme positive divergence.

        Args:
            macd_values: Tuple of (MACD line, Signal line, Recent Histograms, Average Divergence)

        Returns:
            Signal if conditions are met, None otherwise
        """
        try:
            macd_line, signal_line, recent_hist, avg_divergence = macd_values

            # Current histogram represents current divergence
            curr_hist = recent_hist[-1]

            # Calculate histogram strength relative to recent movement
            hist_max = max(abs(h) for h in recent_hist[:-1])  # Exclude current histogram
            hist_strength = abs(curr_hist) / hist_max if hist_max > 0 else 0

            # Check for buy signal (significant negative divergence)
            if curr_hist < 0:
                # Base confidence from divergence magnitude
                # More negative = higher confidence
                base_confidence = min(abs(avg_divergence) / self.BASE_DIVERGENCE_THRESHOLD, 1.0)

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
                if abs(avg_divergence) > self.BASE_DIVERGENCE_THRESHOLD * 2:
                    extreme_factor = 1.1  # 10% bonus for extreme divergence

                # Final confidence calculation
                final_confidence = min(
                    base_confidence * 0.5 +          # Divergence magnitude (50%)
                    (strength_factor * 0.3) +        # Histogram strength (30%)
                    (trend_factor * 0.2),            # Trend consistency (20%)
                    1.0
                ) * extreme_factor                   # Apply extreme bonus

                # Filter out weak singals
                if final_confidence < 0.5:
                    return None

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
                base_confidence = min(abs(avg_divergence) / self.BASE_DIVERGENCE_THRESHOLD, 1.0)

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
                if abs(avg_divergence) > self.BASE_DIVERGENCE_THRESHOLD * 2:
                    extreme_factor = 1.1  # 10% bonus for extreme divergence

                # Final confidence calculation
                final_confidence = min(
                    base_confidence * 0.5 +          # Divergence magnitude (50%)
                    (strength_factor * 0.3) +        # Histogram strength (30%)
                    (trend_factor * 0.2),            # Trend consistency (20%)
                    1.0
                ) * extreme_factor                   # Apply extreme bonus

                # Filter out weak signals
                if final_confidence < 0.5:
                    return None

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
