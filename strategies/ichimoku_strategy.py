import pandas as pd
import pandas_ta as ta
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
            # Calculate Ichimoku components
            high = df['high']
            low = df['low']
            close = df['close']

            # Tenkan-sen (Conversion Line)
            tenkan_high = high.rolling(window=self.tenkan_period).max()
            tenkan_low = low.rolling(window=self.tenkan_period).min()
            tenkan = (tenkan_high + tenkan_low) / 2

            # Kijun-sen (Base Line)
            kijun_high = high.rolling(window=self.kijun_period).max()
            kijun_low = low.rolling(window=self.kijun_period).min()
            kijun = (kijun_high + kijun_low) / 2

            # Senkou Span A (Leading Span A)
            senkou_a = ((tenkan + kijun) / 2).shift(self.displacement)

            # Senkou Span B (Leading Span B)
            senkou_high = high.rolling(window=self.senkou_period).max()
            senkou_low = low.rolling(window=self.senkou_period).min()
            senkou_b = ((senkou_high + senkou_low) / 2).shift(self.displacement)

            # Chikou Span (Lagging Span)
            chikou = close.shift(-self.displacement)

            # Get latest values
            current_close = float(close.iloc[-1])
            current_values = {
                'close': current_close,
                'tenkan': float(tenkan.iloc[-1]),
                'kijun': float(kijun.iloc[-1]),
                'senkou_a': float(senkou_a.iloc[-self.displacement-1]),  # Current cloud
                'senkou_b': float(senkou_b.iloc[-self.displacement-1]),  # Current cloud
                'chikou': float(chikou.iloc[-self.displacement-1]) if len(chikou) > self.displacement else None,
                'future_senkou_a': float(senkou_a.iloc[-1]),  # Future cloud
                'future_senkou_b': float(senkou_b.iloc[-1])   # Future cloud
            }

            return current_values

        except Exception as e:
            logger.error(f"Error calculating Ichimoku: {e}")
            return None

    def detect_ichimoku_patterns(self, df: pd.DataFrame, values: Dict[str, float]) -> Dict[str, float]:
        """
        Detect Ichimoku-specific patterns.

        Args:
            df: Price DataFrame
            values: Current Ichimoku values

        Returns:
            Dictionary of pattern names to confidence levels (0-1)
        """
        patterns = {}
        try:
            # TK Cross (Tenkan/Kijun Cross)
            prev_tenkan = float(df['tenkan'].iloc[-2])
            prev_kijun = float(df['kijun'].iloc[-2])

            if prev_tenkan < prev_kijun and values['tenkan'] > values['kijun']:
                patterns['tk_cross_bullish'] = 0.8
            elif prev_tenkan > prev_kijun and values['tenkan'] < values['kijun']:
                patterns['tk_cross_bearish'] = 0.8

            # Cloud Breakout
            if values['close'] > max(values['senkou_a'], values['senkou_b']):
                patterns['cloud_breakout_bullish'] = 0.9
            elif values['close'] < min(values['senkou_a'], values['senkou_b']):
                patterns['cloud_breakout_bearish'] = 0.9

            # Cloud Twist
            if values['future_senkou_a'] > values['future_senkou_b'] and values['senkou_a'] < values['senkou_b']:
                patterns['cloud_twist_bullish'] = 0.7
            elif values['future_senkou_a'] < values['future_senkou_b'] and values['senkou_a'] > values['senkou_b']:
                patterns['cloud_twist_bearish'] = 0.7

            # Chikou Span Cross
            if values['chikou'] is not None:
                if values['chikou'] > values['close']:
                    patterns['chikou_cross_bullish'] = 0.6
                elif values['chikou'] < values['close']:
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

            # Volume confirmation
            volume_confirmed = df['volume'].iloc[-1] > df['volume'].rolling(window=20).mean().iloc[-1]

            # Generate signals with multiple confirmations
            signal = None

            # Check for potential buy signal
            if ichimoku_values['close'] > ichimoku_values['kijun']:  # Price above base line
                if trend > 0:  # Uptrend confirmation
                    confidence = 0.5 + (abs(trend) * 0.3)  # Base confidence + trend strength

                    # Add pattern confidence
                    if 'tk_cross_bullish' in ichimoku_patterns:
                        confidence += ichimoku_patterns['tk_cross_bullish'] * 0.2
                    if 'cloud_breakout_bullish' in ichimoku_patterns:
                        confidence += ichimoku_patterns['cloud_breakout_bullish'] * 0.2
                    if 'cloud_twist_bullish' in ichimoku_patterns:
                        confidence += ichimoku_patterns['cloud_twist_bullish'] * 0.1
                    if 'chikou_cross_bullish' in ichimoku_patterns:
                        confidence += ichimoku_patterns['chikou_cross_bullish'] * 0.1

                    # Volume confirmation
                    if volume_confirmed:
                        confidence += 0.1

                    if confidence > 0.7:  # High confidence threshold
                        signal = Signal(
                            'ichimoku',
                            SignalType.BUY,
                            f"TK: {ichimoku_values['tenkan']:.2f}/{ichimoku_values['kijun']:.2f}"
                        )
                        logger.info(f"Buy signal generated with confidence {confidence:.2f}")

            # Check for potential sell signal
            elif ichimoku_values['close'] < ichimoku_values['kijun']:  # Price below base line
                if trend < 0:  # Downtrend confirmation
                    confidence = 0.5 + (abs(trend) * 0.3)  # Base confidence + trend strength

                    # Add pattern confidence
                    if 'tk_cross_bearish' in ichimoku_patterns:
                        confidence += ichimoku_patterns['tk_cross_bearish'] * 0.2
                    if 'cloud_breakout_bearish' in ichimoku_patterns:
                        confidence += ichimoku_patterns['cloud_breakout_bearish'] * 0.2
                    if 'cloud_twist_bearish' in ichimoku_patterns:
                        confidence += ichimoku_patterns['cloud_twist_bearish'] * 0.1
                    if 'chikou_cross_bearish' in ichimoku_patterns:
                        confidence += ichimoku_patterns['chikou_cross_bearish'] * 0.1

                    # Volume confirmation
                    if volume_confirmed:
                        confidence += 0.1

                    if confidence > 0.7:  # High confidence threshold
                        signal = Signal(
                            'ichimoku',
                            SignalType.SELL,
                            f"TK: {ichimoku_values['tenkan']:.2f}/{ichimoku_values['kijun']:.2f}"
                        )
                        logger.info(f"Sell signal generated with confidence {confidence:.2f}")

            return signal

        except Exception as e:
            logger.error(f"Error analyzing market: {e}")
            return None
