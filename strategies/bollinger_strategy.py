import pandas as pd
import pandas_ta as ta
from typing import Optional, Dict
from .base import SignalStrategy
from utils.models import Signal, SignalType
from utils.logger import logger


class BollingerStrategy(SignalStrategy):
    """Bollinger Bands strategy."""

    def __init__(self, interval: int = 60, window: int = 100) -> None:
        """
        Initialize Bollinger Bands strategy.

        Args:
            interval: Time interval in minutes
            window: Number of candles to keep
        """
        super().__init__(interval, window)

    @property
    def min_candles(self) -> int:
        """Minimum candles needed for BB calculation."""
        return 21  # 20 for BB + 1 for current candle

    def calculate_indicator(self, df: pd.DataFrame) -> Optional[Dict[str, float]]:
        """Calculate Bollinger Bands values."""
        try:
            # Calculate Bollinger Bands efficiently
            close = df['close']
            bb = ta.bbands(close, length=20, std=2)
            if bb is None or bb.empty:
                return None

            # Verify required columns exist
            required_columns = ['BBL_20_2', 'BBM_20_2', 'BBU_20_2']
            if not all(col in bb.columns for col in required_columns):
                logger.warning(f"Missing required BB columns. Available columns: {bb.columns.tolist()}")
                return None

            # Get latest values efficiently
            try:
                current_close = float(close.iat[-1])
                upper_band = float(bb['BBU_20_2'].iat[-1])
                middle_band = float(bb['BBM_20_2'].iat[-1])
                lower_band = float(bb['BBL_20_2'].iat[-1])

                # Calculate band width for volatility context
                band_width = (upper_band - lower_band) / middle_band

                return {
                    'close': current_close,
                    'upper': upper_band,
                    'middle': middle_band,
                    'lower': lower_band,
                    'width': band_width
                }

            except (IndexError, KeyError) as e:
                logger.error(f"Error accessing BB values: {e}")
                return None

        except Exception as e:
            logger.error(f"Error calculating Bollinger Bands: {e}")
            return None

    def analyze_market(self, bb_values: Dict[str, float]) -> Optional[Signal]:
        """
        Generate signal based on Bollinger Bands.

        Args:
            bb_values: Dictionary of current BB values

        Returns:
            Signal if conditions are met, None otherwise
        """
        try:
            current_close = bb_values['close']
            upper_band = bb_values['upper']
            lower_band = bb_values['lower']
            middle_band = bb_values['middle']
            band_width = bb_values['width']

            # Check for potential buy signal
            if current_close <= lower_band:
                # Calculate base confidence from band penetration
                penetration = (lower_band - current_close) / current_close
                base_confidence = min(penetration / 0.02, 1.0)  # 2% penetration for full confidence

                # Adjust confidence based on band width (volatility context)
                # Typical band width is around 4% (0.04) for crypto
                volatility_factor = min(band_width / 0.04, 1.5)  # Cap at 1.5x

                # Reduce confidence in high volatility, increase in low volatility
                adjusted_confidence = base_confidence * (1.0 / volatility_factor)

                # Consider distance from middle band (trend context)
                # Larger moves from middle band suggest stronger trends
                middle_distance = (middle_band - current_close) / current_close
                trend_factor = min(abs(middle_distance) / 0.03, 1.0)  # 3% for full impact

                # Final confidence combines all factors
                final_confidence = min(
                    (adjusted_confidence * 0.7) +  # Band penetration with volatility adjustment
                    (trend_factor * 0.3),         # Trend context
                    1.0
                )

                signal = Signal(
                    'bollinger',
                    SignalType.BUY,
                    f"{penetration:.4f}",  # Store penetration as percentage
                    final_confidence
                )
                logger.info(f"Buy signal generated at BB lower band (confidence: {final_confidence:.2f})")
                return signal

            # Check for potential sell signal
            elif current_close >= upper_band:
                # Calculate base confidence from band penetration
                penetration = (current_close - upper_band) / current_close
                base_confidence = min(penetration / 0.02, 1.0)  # 2% penetration for full confidence

                # Adjust confidence based on band width (volatility context)
                volatility_factor = min(band_width / 0.04, 1.5)  # Cap at 1.5x

                # Reduce confidence in high volatility, increase in low volatility
                adjusted_confidence = base_confidence * (1.0 / volatility_factor)

                # Consider distance from middle band (trend context)
                middle_distance = (current_close - middle_band) / current_close
                trend_factor = min(abs(middle_distance) / 0.03, 1.0)  # 3% for full impact

                # Final confidence combines all factors
                final_confidence = min(
                    (adjusted_confidence * 0.7) +  # Band penetration with volatility adjustment
                    (trend_factor * 0.3),         # Trend context
                    1.0
                )

                signal = Signal(
                    'bollinger',
                    SignalType.SELL,
                    f"{penetration:.4f}",  # Store penetration as percentage
                    final_confidence
                )
                logger.info(f"Sell signal generated at BB upper band (confidence: {final_confidence:.2f})")
                return signal

            return None

        except Exception as e:
            logger.error(f"Error analyzing market: {e}")
            return None
