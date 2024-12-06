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
            # Calculate Bollinger Bands
            bb = ta.bbands(df['close'], length=20, std=2)
            if bb is None or bb.empty:
                return None

            # Get latest values
            current_close = float(df['close'].iloc[-1])
            upper_band = float(bb['BBU_20_2.0'].iloc[-1])
            middle_band = float(bb['BBM_20_2.0'].iloc[-1])
            lower_band = float(bb['BBL_20_2.0'].iloc[-1])

            # Calculate BB width (volatility measure)
            bb_width = (upper_band - lower_band) / middle_band

            # Calculate % B (position within bands)
            percent_b = (current_close - lower_band) / (upper_band - lower_band)

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
            # Get historical BB values
            bb_hist = ta.bbands(df['close'].iloc[-20:], length=20, std=2)

            # Detect BB squeeze (low volatility)
            recent_widths = (bb_hist['BBU_20_2.0'] - bb_hist['BBL_20_2.0']) / bb_hist['BBM_20_2.0']
            avg_width = recent_widths.mean()
            if bb_values['width'] < avg_width * 0.8:  # Width is 20% below average
                patterns['squeeze'] = 0.8

            # Detect price touches on bands
            if abs(bb_values['close'] - bb_values['upper']) / bb_values['upper'] < 0.001:
                patterns['upper_touch'] = 0.7
            elif abs(bb_values['close'] - bb_values['lower']) / bb_values['lower'] < 0.001:
                patterns['lower_touch'] = 0.7

            # Detect walking the band (consistent touches)
            recent_closes = df['close'].iloc[-5:]
            upper_touches = sum(1 for c, u in zip(recent_closes, bb_hist['BBU_20_2.0']) if abs(c - u) / u < 0.001)
            lower_touches = sum(1 for c, l in zip(recent_closes, bb_hist['BBL_20_2.0']) if abs(c - l) / l < 0.001)

            if upper_touches >= 3:
                patterns['walking_upper'] = 0.9
            elif lower_touches >= 3:
                patterns['walking_lower'] = 0.9

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

            # Volume confirmation
            volume_confirmed = df['volume'].iloc[-1] > df['volume'].rolling(window=20).mean().iloc[-1]

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
