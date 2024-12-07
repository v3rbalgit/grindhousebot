import pandas as pd
from typing import Optional, Dict
from .base import SignalStrategy
from utils.models import Signal, SignalType
from utils.logger import logger


class IchimokuStrategy(SignalStrategy):
    """
    Ichimoku Cloud strategy optimized for crypto markets.

    Features:
    - Crypto-optimized periods (20, 60, 120, 30)
    - Multiple timeframe analysis
    - Cloud breakout detection
    - TK cross signals
    - Future price projections
    """

    def __init__(self, interval: int = 60, window: int = 150) -> None:
        """
        Initialize Ichimoku strategy with crypto-specific settings.

        Args:
            interval: Time interval in minutes
            window: Number of candles to keep (must be > 120 + displacement)
        """
        super().__init__(interval, window)
        # Crypto-optimized periods
        self.tenkan_period = 20      # Conversion line (fast)
        self.kijun_period = 60       # Base line (slow)
        self.senkou_period = 120     # Cloud span
        self.displacement = 30       # Future cloud displacement

    @property
    def min_candles(self) -> int:
        """Minimum candles needed for Ichimoku calculation."""
        return self.senkou_period + self.displacement  # Need enough data for cloud calculation

    def calculate_indicator(self, df: pd.DataFrame) -> Optional[Dict[str, float]]:
        """Calculate Ichimoku components with crypto-optimized settings."""
        try:
            # Cache DataFrame columns for efficient access
            high = df['high']
            low = df['low']
            close = df['close']

            # Calculate components efficiently
            try:
                # Tenkan-sen (Conversion Line)
                tenkan = (high.rolling(window=self.tenkan_period).max() +
                         low.rolling(window=self.tenkan_period).min()) / 2

                # Kijun-sen (Base Line)
                kijun = (high.rolling(window=self.kijun_period).max() +
                        low.rolling(window=self.kijun_period).min()) / 2

                # Senkou Span A (Leading Span A)
                senkou_a = ((tenkan + kijun) / 2).shift(self.displacement)

                # Senkou Span B (Leading Span B)
                senkou_b = ((high.rolling(window=self.senkou_period).max() +
                           low.rolling(window=self.senkou_period).min()) / 2).shift(self.displacement)

                # Chikou Span (Lagging Span)
                chikou = close.shift(-self.displacement)

                # Store calculated values in DataFrame for pattern detection
                df['tenkan'] = tenkan
                df['kijun'] = kijun
                df['senkou_a'] = senkou_a
                df['senkou_b'] = senkou_b
                df['chikou'] = chikou

                # Get latest values efficiently
                current_close = float(close.iat[-1])
                current_values = {
                    'close': current_close,
                    'tenkan': float(tenkan.iat[-1]),
                    'kijun': float(kijun.iat[-1]),
                    'senkou_a': float(senkou_a.iat[-self.displacement-1]),  # Current cloud
                    'senkou_b': float(senkou_b.iat[-self.displacement-1]),  # Current cloud
                    'chikou': float(chikou.iat[-self.displacement-1]) if len(chikou.dropna()) > self.displacement else None,
                    'future_senkou_a': float(senkou_a.iat[-1]),  # Future cloud
                    'future_senkou_b': float(senkou_b.iat[-1])   # Future cloud
                }

                return current_values

            except (IndexError, KeyError) as e:
                logger.error(f"Error accessing Ichimoku values: {e}")
                return None

        except Exception as e:
            logger.error(f"Error calculating Ichimoku: {e}")
            return None

    def detect_ichimoku_patterns(self, df: pd.DataFrame, values: Dict[str, float]) -> Dict[str, float]:
        """
        Detect Ichimoku-specific patterns.

        Args:
            df: Price DataFrame with calculated Ichimoku values
            values: Current Ichimoku values

        Returns:
            Dictionary of pattern names to confidence levels (0-1)
        """
        patterns = {}
        try:
            if len(df) < 2:
                return patterns

            # Get previous values efficiently
            try:
                prev_tenkan = float(df['tenkan'].iat[-2])
                prev_kijun = float(df['kijun'].iat[-2])
            except (IndexError, KeyError) as e:
                logger.error(f"Error accessing previous values: {e}")
                return patterns

            # TK Cross (Tenkan/Kijun Cross)
            if prev_tenkan < prev_kijun and values['tenkan'] > values['kijun']:
                patterns['tk_cross_bullish'] = 0.8
            elif prev_tenkan > prev_kijun and values['tenkan'] < values['kijun']:
                patterns['tk_cross_bearish'] = 0.8

            # Cloud Breakout (with cached values)
            current_close = values['close']
            current_senkou_a = values['senkou_a']
            current_senkou_b = values['senkou_b']

            if current_close > max(current_senkou_a, current_senkou_b):
                patterns['cloud_breakout_bullish'] = 0.9
            elif current_close < min(current_senkou_a, current_senkou_b):
                patterns['cloud_breakout_bearish'] = 0.9

            # Cloud Twist (with cached values)
            future_senkou_a = values['future_senkou_a']
            future_senkou_b = values['future_senkou_b']

            if future_senkou_a > future_senkou_b and current_senkou_a < current_senkou_b:
                patterns['cloud_twist_bullish'] = 0.7
            elif future_senkou_a < future_senkou_b and current_senkou_a > current_senkou_b:
                patterns['cloud_twist_bearish'] = 0.7

            # Chikou Span Cross
            if values['chikou'] is not None:
                chikou = values['chikou']
                if chikou > current_close:
                    patterns['chikou_cross_bullish'] = 0.6
                elif chikou < current_close:
                    patterns['chikou_cross_bearish'] = 0.6

        except Exception as e:
            logger.error(f"Error detecting Ichimoku patterns: {e}")

        return patterns

    def analyze_market(self, df: pd.DataFrame, ichimoku_values: Dict[str, float]) -> Optional[Signal]:
        """
        Analyze market conditions using Ichimoku and additional indicators.

        Args:
            df: Price DataFrame
            ichimoku_values: Current Ichimoku values

        Returns:
            Signal if conditions are met, None otherwise
        """
        try:
            # Calculate market trend
            trend = self.calculate_market_trend(df)

            # Detect Ichimoku-specific patterns
            ichimoku_patterns = self.detect_ichimoku_patterns(df, ichimoku_values)

            # Detect general patterns
            patterns = self.detect_patterns(df)

            # Volume confirmation (optimized)
            volume = df['volume']
            volume_ma = volume.rolling(window=20).mean()
            volume_confirmed = volume.iat[-1] > volume_ma.iat[-1]

            # Generate signals with multiple confirmations
            signal = None
            current_close = ichimoku_values['close']
            kijun = ichimoku_values['kijun']

            # Check for potential buy signal
            if current_close > kijun:  # Price above base line
                if trend > 0:  # Uptrend confirmation
                    confidence = 0.5 + (abs(trend) * 0.3)  # Base confidence + trend strength

                    # Add pattern confidence efficiently
                    for pattern, value in ichimoku_patterns.items():
                        if pattern.endswith('bullish'):
                            if pattern.startswith('tk_cross'):
                                confidence += value * 0.2
                            elif pattern.startswith('cloud_breakout'):
                                confidence += value * 0.2
                            elif pattern.startswith('cloud_twist'):
                                confidence += value * 0.1
                            elif pattern.startswith('chikou_cross'):
                                confidence += value * 0.1

                    # Volume confirmation
                    if volume_confirmed:
                        confidence += 0.1

                    if confidence > 0.7:  # High confidence threshold
                        signal = Signal(
                            'ichimoku',
                            SignalType.BUY,
                            f"TK: {ichimoku_values['tenkan']:.2f}/{kijun:.2f}"
                        )
                        logger.info(f"Buy signal generated with confidence {confidence:.2f}")

            # Check for potential sell signal
            elif current_close < kijun:  # Price below base line
                if trend < 0:  # Downtrend confirmation
                    confidence = 0.5 + (abs(trend) * 0.3)  # Base confidence + trend strength

                    # Add pattern confidence efficiently
                    for pattern, value in ichimoku_patterns.items():
                        if pattern.endswith('bearish'):
                            if pattern.startswith('tk_cross'):
                                confidence += value * 0.2
                            elif pattern.startswith('cloud_breakout'):
                                confidence += value * 0.2
                            elif pattern.startswith('cloud_twist'):
                                confidence += value * 0.1
                            elif pattern.startswith('chikou_cross'):
                                confidence += value * 0.1

                    # Volume confirmation
                    if volume_confirmed:
                        confidence += 0.1

                    if confidence > 0.7:  # High confidence threshold
                        signal = Signal(
                            'ichimoku',
                            SignalType.SELL,
                            f"TK: {ichimoku_values['tenkan']:.2f}/{kijun:.2f}"
                        )
                        logger.info(f"Sell signal generated with confidence {confidence:.2f}")

            return signal

        except Exception as e:
            logger.error(f"Error analyzing market: {e}")
            return None
