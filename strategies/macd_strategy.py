import pandas as pd
import pandas_ta as ta
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
                avg_divergence = abs(macd['MACD_12_26_9'].tail(5).mean() - signal_line)

                return macd_line, signal_line, recent_hist, avg_divergence

            except (IndexError, KeyError) as e:
                logger.error(f"Error accessing MACD values: {e}")
                return None

        except Exception as e:
            logger.error(f"Error calculating MACD: {e}")
            return None

    def analyze_market(self, macd_values: Tuple[float, float, List[float], float]) -> Optional[Signal]:
        """
        Generate signal based on MACD with improved confidence scoring.

        Args:
            macd_values: Tuple of (MACD line, Signal line, Recent Histograms, Average Divergence)

        Returns:
            Signal if conditions are met, None otherwise
        """
        try:
            macd_line, signal_line, recent_hist, avg_divergence = macd_values

            # Check for crossover
            curr_hist = recent_hist[-1]
            prev_hist = recent_hist[-2]

            # Calculate histogram strength relative to recent movement
            hist_max = max(abs(h) for h in recent_hist[:-1])  # Exclude current histogram
            hist_strength = abs(curr_hist) / hist_max if hist_max > 0 else 0

            # Check for bullish signal (MACD crosses above signal)
            if curr_hist > 0 and prev_hist < 0:
                # Base confidence from divergence
                # Using 0.01 (1%) as baseline for strong divergence
                base_confidence = min(avg_divergence / 0.01, 1.0)

                # Histogram strength factor
                # Strong histogram after crossover indicates stronger momentum
                strength_factor = min(hist_strength, 1.0)

                # Trend consistency factor
                # Check if histograms are getting larger (strengthening trend)
                trend_factor = 1.0
                if len(recent_hist) >= 3:
                    if abs(curr_hist) > abs(recent_hist[-2]):  # Growing histogram
                        trend_factor = 1.2  # 20% bonus
                    elif abs(curr_hist) < abs(recent_hist[-2]) * 0.5:  # Weakening histogram
                        trend_factor = 0.8  # 20% penalty

                # Final confidence calculation
                final_confidence = min(
                    (base_confidence * 0.5) +     # Divergence (50%)
                    (strength_factor * 0.3) +     # Histogram strength (30%)
                    (trend_factor * 0.2),         # Trend consistency (20%)
                    1.0
                )

                signal = Signal(
                    'macd',
                    SignalType.BUY,
                    f"{avg_divergence:.4f}",
                    final_confidence
                )
                logger.info(f"Buy signal generated with MACD divergence {avg_divergence:.4f} (confidence: {final_confidence:.2f})")
                return signal

            # Check for bearish signal (MACD crosses below signal)
            elif curr_hist < 0 and prev_hist > 0:
                # Base confidence from divergence
                base_confidence = min(avg_divergence / 0.01, 1.0)

                # Histogram strength factor
                strength_factor = min(hist_strength, 1.0)

                # Trend consistency factor
                trend_factor = 1.0
                if len(recent_hist) >= 3:
                    if abs(curr_hist) > abs(recent_hist[-2]):  # Growing histogram
                        trend_factor = 1.2  # 20% bonus
                    elif abs(curr_hist) < abs(recent_hist[-2]) * 0.5:  # Weakening histogram
                        trend_factor = 0.8  # 20% penalty

                # Final confidence calculation
                final_confidence = min(
                    (base_confidence * 0.5) +     # Divergence (50%)
                    (strength_factor * 0.3) +     # Histogram strength (30%)
                    (trend_factor * 0.2),         # Trend consistency (20%)
                    1.0
                )

                signal = Signal(
                    'macd',
                    SignalType.SELL,
                    f"{avg_divergence:.4f}",
                    final_confidence
                )
                logger.info(f"Sell signal generated with MACD divergence {avg_divergence:.4f} (confidence: {final_confidence:.2f})")
                return signal

            return None

        except Exception as e:
            logger.error(f"Error analyzing market: {e}")
            return None
