import pandas as pd
from typing import Optional, Dict, List, Tuple, Union
from .base import SignalStrategy
from utils.models import Signal, SignalType
from utils.logger import logger


class HarmonicStrategy(SignalStrategy):
    """
    Harmonic Pattern strategy adapted for crypto markets.

    Features:
    - Multiple pattern recognition (Gartley, Butterfly, Bat, Crab)
    - Fibonacci ratio validation
    - Volatility-adjusted measurements
    - Pattern completion confidence scoring
    """

    # Fibonacci ratios with crypto-adapted tolerance
    FIBONACCI_RATIOS = {
        'GARTLEY': {
            'XA': 1.0,
            'AB': 0.618,
            'BC': 0.386,
            'CD': 1.272
        },
        'BUTTERFLY': {
            'XA': 1.0,
            'AB': 0.786,
            'BC': 0.382,
            'CD': 1.618
        },
        'BAT': {
            'XA': 1.0,
            'AB': 0.382,
            'BC': 0.886,
            'CD': 2.618
        },
        'CRAB': {
            'XA': 1.0,
            'AB': 0.382,
            'BC': 0.886,
            'CD': 3.618
        }
    }

    # Wider tolerance for crypto markets
    TOLERANCE = 0.15  # 15% tolerance for ratio matching

    def __init__(self, interval: int = 60, window: int = 100) -> None:
        """
        Initialize Harmonic Pattern strategy.

        Args:
            interval: Time interval in minutes
            window: Number of candles to keep
        """
        super().__init__(interval, window)

    @property
    def min_candles(self) -> int:
        """Minimum candles needed for pattern detection."""
        return 30  # Need enough data to identify swing points

    def find_swing_points(self, df: pd.DataFrame, window: int = 5) -> Tuple[List[int], List[int]]:
        """
        Find swing highs and lows in price data.

        Args:
            df: Price DataFrame
            window: Window size for swing point detection

        Returns:
            Tuple of (swing high indices, swing low indices)
        """
        highs = []
        lows = []

        for i in range(window, len(df) - window):
            # Check for swing high
            if all(df['high'].iloc[i] > df['high'].iloc[i-j] for j in range(1, window+1)) and \
               all(df['high'].iloc[i] > df['high'].iloc[i+j] for j in range(1, window+1)):
                highs.append(i)

            # Check for swing low
            if all(df['low'].iloc[i] < df['low'].iloc[i-j] for j in range(1, window+1)) and \
               all(df['low'].iloc[i] < df['low'].iloc[i+j] for j in range(1, window+1)):
                lows.append(i)

        return highs, lows

    def calculate_ratio(self, start: float, end: float, target: float) -> float:
        """Calculate retracement/extension ratio."""
        return abs((end - target) / (end - start))

    def validate_pattern(self, points: List[float], pattern_type: str) -> float:
        """
        Validate pattern measurements against Fibonacci ratios.

        Args:
            points: List of pattern points [X, A, B, C, D]
            pattern_type: Type of harmonic pattern

        Returns:
            Confidence score (0-1)
        """
        ratios = self.FIBONACCI_RATIOS[pattern_type]
        confidence = 0.0

        # Calculate actual ratios
        xa_ratio = self.calculate_ratio(points[0], points[1], points[1])  # XA movement
        ab_ratio = self.calculate_ratio(points[1], points[2], points[1])  # AB retracement
        bc_ratio = self.calculate_ratio(points[2], points[3], points[2])  # BC retracement
        cd_ratio = self.calculate_ratio(points[3], points[4], points[3])  # CD extension

        # Check each ratio against expected with tolerance
        checks = [
            (xa_ratio, ratios['XA']),
            (ab_ratio, ratios['AB']),
            (bc_ratio, ratios['BC']),
            (cd_ratio, ratios['CD'])
        ]

        for actual, expected in checks:
            diff = abs(actual - expected) / expected
            if diff <= self.TOLERANCE:
                # More confidence for closer matches
                confidence += (1 - (diff / self.TOLERANCE)) * 0.25

        return confidence

    def find_patterns(self, df: pd.DataFrame) -> Dict[str, float]:
        """
        Find harmonic patterns in price data.

        Args:
            df: Price DataFrame

        Returns:
            Dictionary of pattern types to confidence levels
        """
        patterns = {}
        try:
            # Find swing points
            highs, lows = self.find_swing_points(df)

            # Need at least 5 points for a pattern
            if len(highs) + len(lows) < 5:
                return patterns

            # Get recent swing points (last 5)
            points = sorted(highs + lows)[-5:]
            if len(points) < 5:
                return patterns

            # Get point values
            values = [df['close'].iloc[i] for i in points]

            # Check each pattern type
            for pattern in self.FIBONACCI_RATIOS.keys():
                confidence = self.validate_pattern(values, pattern)
                if confidence > 0.7:  # Only include high confidence patterns
                    patterns[f"{pattern.lower()}_bullish"] = confidence

                # Check inverse pattern
                inverse_values = [-v for v in values]
                confidence = self.validate_pattern(inverse_values, pattern)
                if confidence > 0.7:
                    patterns[f"{pattern.lower()}_bearish"] = confidence

        except Exception as e:
            logger.error(f"Error finding harmonic patterns: {e}")

        return patterns

    def calculate_indicator(self, df: pd.DataFrame) -> Optional[Dict[str, Union[str, float]]]:
        """Calculate pattern points and measurements."""
        try:
            patterns = self.find_patterns(df)
            if not patterns:
                return None

            # Get the strongest pattern
            pattern_type = max(patterns.items(), key=lambda x: x[1])[0]
            confidence = patterns[pattern_type]

            return {
                'pattern': pattern_type,
                'confidence': confidence
            }

        except Exception as e:
            logger.error(f"Error calculating harmonic patterns: {e}")
            return None

    def analyze_market(self, df: pd.DataFrame, pattern_data: Dict[str, Union[str, float]]) -> Optional[Signal]:
        """
        Analyze market conditions using harmonic patterns and additional indicators.

        Args:
            df: Price DataFrame
            pattern_data: Pattern type and confidence

        Returns:
            Signal if conditions are met, None otherwise
        """
        try:
            # Calculate market trend
            trend = self.calculate_market_trend(df)

            # Detect general patterns
            patterns = self.detect_patterns(df)

            # Volume confirmation
            volume_confirmed = df['volume'].iloc[-1] > df['volume'].rolling(window=20).mean().iloc[-1]

            # Generate signals with multiple confirmations
            signal = None
            pattern_type = str(pattern_data['pattern'])  # Ensure string type
            base_confidence = float(pattern_data['confidence'])  # Ensure float type

            # Check for potential buy signal
            if 'bullish' in pattern_type:
                if trend > 0:  # Uptrend confirmation
                    confidence = base_confidence + (abs(trend) * 0.2)  # Pattern confidence + trend strength

                    # Add pattern confidence
                    if 'double_bottom' in patterns:
                        confidence += patterns['double_bottom'] * 0.1
                    if 'breakout' in patterns:
                        confidence += patterns['breakout'] * 0.1

                    # Volume confirmation
                    if volume_confirmed:
                        confidence += 0.1

                    if confidence > 0.8:  # Higher threshold for harmonic patterns
                        signal = Signal(
                            'harmonic',
                            SignalType.BUY,
                            pattern_type
                        )
                        logger.info(f"Buy signal generated with confidence {confidence:.2f}")

            # Check for potential sell signal
            elif 'bearish' in pattern_type:
                if trend < 0:  # Downtrend confirmation
                    confidence = base_confidence + (abs(trend) * 0.2)  # Pattern confidence + trend strength

                    # Add pattern confidence
                    if 'double_top' in patterns:
                        confidence += patterns['double_top'] * 0.1
                    if 'breakdown' in patterns:
                        confidence += patterns['breakdown'] * 0.1

                    # Volume confirmation
                    if volume_confirmed:
                        confidence += 0.1

                    if confidence > 0.8:  # Higher threshold for harmonic patterns
                        signal = Signal(
                            'harmonic',
                            SignalType.SELL,
                            pattern_type
                        )
                        logger.info(f"Sell signal generated with confidence {confidence:.2f}")

            return signal

        except Exception as e:
            logger.error(f"Error analyzing market: {e}")
            return None
