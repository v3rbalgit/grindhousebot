import pandas as pd
import pandas_ta as ta
from typing import Optional, Dict
from .base import SignalStrategy
from utils.models import Signal, SignalType
from utils.logger import logger


class BollingerStrategy(SignalStrategy):
    """
    Bollinger Bands strategy with dynamic analysis.

    Features:
    - Dynamic band width analysis
    - Squeeze detection
    - Pattern recognition at band touches
    - Volume confirmation
    - Multiple timeframe trend confirmation
    """

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
        """Calculate Bollinger Bands with additional indicators."""
        try:
            # Calculate Bollinger Bands efficiently
            close = df['close']
            bb = ta.bbands(close, length=20, std=2)
            if bb is None or bb.empty:
                logger.warning("Bollinger Bands calculation returned None or empty")
                return None

            # Verify required columns exist
            required_columns = ['BBU_20_2.0', 'BBM_20_2.0', 'BBL_20_2.0']
            if not all(col in bb.columns for col in required_columns):
                logger.warning(f"Missing required BB columns. Available columns: {bb.columns.tolist()}")
                return None

            # Get latest values efficiently
            try:
                current_close = float(close.iat[-1])
                upper_band = float(bb['BBU_20_2.0'].iat[-1])
                middle_band = float(bb['BBM_20_2.0'].iat[-1])
                lower_band = float(bb['BBL_20_2.0'].iat[-1])
            except (IndexError, KeyError) as e:
                logger.error(f"Error accessing BB values: {e}")
                return None

            # Avoid division by zero
            if middle_band == 0 or (upper_band - lower_band) == 0:
                logger.warning("Invalid BB values (division by zero)")
                return None

            # Calculate BB width (volatility measure)
            bb_width = (upper_band - lower_band) / middle_band

            # Calculate % B (position within bands)
            percent_b = (current_close - lower_band) / (upper_band - lower_band)

            # Store BB values for pattern detection
            df['BBU_20_2.0'] = bb['BBU_20_2.0']
            df['BBM_20_2.0'] = bb['BBM_20_2.0']
            df['BBL_20_2.0'] = bb['BBL_20_2.0']

            return {
                'close': current_close,
                'upper': upper_band,
                'middle': middle_band,
                'lower': lower_band,
                'width': bb_width,
                'percent_b': percent_b
            }

        except Exception as e:
            logger.error(f"Error calculating Bollinger Bands: {e}")
            return None

    def detect_bb_patterns(self, df: pd.DataFrame, bb_values: Dict[str, float]) -> Dict[str, float]:
        """
        Detect Bollinger Bands specific patterns.

        Args:
            df: Price DataFrame
            bb_values: Current BB indicator values

        Returns:
            Dictionary of pattern names to confidence levels (0-1)
        """
        patterns = {}
        try:
            # Get recent data efficiently
            recent_data = df.iloc[-20:]
            close = recent_data['close']
            upper = recent_data['BBU_20_2.0']
            lower = recent_data['BBL_20_2.0']
            middle = recent_data['BBM_20_2.0']

            # Detect BB squeeze (low volatility)
            try:
                recent_widths = (upper - lower) / middle
                avg_width = recent_widths.mean()
                if bb_values['width'] < avg_width * 0.8:  # Width is 20% below average
                    patterns['squeeze'] = 0.8
            except Exception as e:
                logger.warning(f"Error calculating BB squeeze: {e}")

            # Detect price touches on bands efficiently
            try:
                current_close = bb_values['close']
                if abs(current_close - bb_values['upper']) / bb_values['upper'] < 0.001:
                    patterns['upper_touch'] = 0.7
                elif abs(current_close - bb_values['lower']) / bb_values['lower'] < 0.001:
                    patterns['lower_touch'] = 0.7
            except Exception as e:
                logger.warning(f"Error detecting band touches: {e}")

            # Detect walking the band efficiently
            try:
                recent_closes = close.tail(5)
                recent_upper = upper.tail(5)
                recent_lower = lower.tail(5)

                upper_touches = sum(1 for c, u in zip(recent_closes, recent_upper)
                                if abs(c - u) / u < 0.001)
                lower_touches = sum(1 for c, l in zip(recent_closes, recent_lower)
                                if abs(c - l) / l < 0.001)

                if upper_touches >= 3:
                    patterns['walking_upper'] = 0.9
                elif lower_touches >= 3:
                    patterns['walking_lower'] = 0.9
            except Exception as e:
                logger.warning(f"Error detecting band walking: {e}")

        except Exception as e:
            logger.error(f"Error detecting BB patterns: {e}")

        return patterns

    def analyze_market(self, df: pd.DataFrame, bb_values: Dict[str, float]) -> Optional[Signal]:
        """
        Analyze market conditions using Bollinger Bands and additional indicators.

        Args:
            df: Price DataFrame
            bb_values: Current BB indicator values

        Returns:
            Signal if conditions are met, None otherwise
        """
        try:
            # Calculate market trend
            trend = self.calculate_market_trend(df)

            # Detect BB-specific patterns
            bb_patterns = self.detect_bb_patterns(df, bb_values)

            # Detect general patterns
            patterns = self.detect_patterns(df)

            # Volume confirmation (optimized)
            volume = df['volume']
            volume_ma = volume.rolling(window=20).mean()
            volume_confirmed = volume.iat[-1] > volume_ma.iat[-1]

            # Generate signals with multiple confirmations
            signal = None

            # Check for potential buy signal
            if bb_values['percent_b'] < 0.1:  # Price near lower band
                if trend > 0:  # Uptrend confirmation
                    confidence = 0.5 + (abs(trend) * 0.3)  # Base confidence + trend strength

                    # Add pattern confidence
                    if 'squeeze' in bb_patterns:
                        confidence += bb_patterns['squeeze'] * 0.2
                    if 'lower_touch' in bb_patterns:
                        confidence += bb_patterns['lower_touch'] * 0.2
                    if 'double_bottom' in patterns:
                        confidence += patterns['double_bottom'] * 0.2

                    # Volume confirmation
                    if volume_confirmed:
                        confidence += 0.1

                    if confidence > 0.7:  # High confidence threshold
                        signal = Signal(
                            'bollinger',
                            SignalType.BUY,
                            bb_values['percent_b']
                        )
                        logger.info(f"Buy signal generated with confidence {confidence:.2f}")

            # Check for potential sell signal
            elif bb_values['percent_b'] > 0.9:  # Price near upper band
                if trend < 0:  # Downtrend confirmation
                    confidence = 0.5 + (abs(trend) * 0.3)  # Base confidence + trend strength

                    # Add pattern confidence
                    if 'squeeze' in bb_patterns:
                        confidence += bb_patterns['squeeze'] * 0.2
                    if 'upper_touch' in bb_patterns:
                        confidence += bb_patterns['upper_touch'] * 0.2
                    if 'walking_upper' in bb_patterns:
                        confidence += bb_patterns['walking_upper'] * 0.2

                    # Volume confirmation
                    if volume_confirmed:
                        confidence += 0.1

                    if confidence > 0.7:  # High confidence threshold
                        signal = Signal(
                            'bollinger',
                            SignalType.SELL,
                            bb_values['percent_b']
                        )
                        logger.info(f"Sell signal generated with confidence {confidence:.2f}")

            return signal

        except Exception as e:
            logger.error(f"Error analyzing market: {e}")
            return None
