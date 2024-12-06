import pandas as pd
import numpy as np
from typing import Optional, Dict, List, Tuple, Union, Any, TypedDict
from .base import SignalStrategy
from utils.models import Signal, SignalType
from utils.logger import logger


class ProfileData(TypedDict):
    """Type for profile data to help with type checking."""
    current_price: float
    poc_price: float
    value_area: float
    profile: pd.Series


class VolumeProfileStrategy(SignalStrategy):
    """
    Volume Profile strategy for crypto markets.

    Features:
    - Volume distribution analysis
    - High/low volume node detection
    - Price acceptance/rejection patterns
    - Volume-based support/resistance levels
    """

    def __init__(self, interval: int = 60, window: int = 100) -> None:
        """
        Initialize Volume Profile strategy.

        Args:
            interval: Time interval in minutes
            window: Number of candles to keep
        """
        super().__init__(interval, window)
        self.price_levels = 100  # Number of price levels for volume distribution
        self.volume_threshold = 0.8  # Threshold for high volume nodes (80th percentile)

    @property
    def min_candles(self) -> int:
        """Minimum candles needed for volume profile analysis."""
        return 50  # Need enough data for reliable volume distribution

    def calculate_volume_profile(self, df: pd.DataFrame) -> Tuple[pd.Series, float, float]:
        """
        Calculate volume distribution across price levels.

        Args:
            df: Price DataFrame

        Returns:
            Tuple of (volume profile, POC price, value area)
        """
        try:
            # Calculate price range
            price_min = df['low'].min()
            price_max = df['high'].max()
            if not (isinstance(price_min, (int, float)) and isinstance(price_max, (int, float))):
                return pd.Series(dtype=float), 0.0, 0.0

            price_delta = (price_max - price_min) / self.price_levels

            # Create price levels
            price_levels = [price_min + i * price_delta for i in range(self.price_levels + 1)]
            profile = pd.Series(0.0, index=range(self.price_levels))

            # Distribute volume across price levels
            for _, row in df.iterrows():
                row_low = float(row['low'])
                row_high = float(row['high'])
                row_volume = float(row['volume'])

                for i in range(self.price_levels):
                    level_low = price_levels[i]
                    level_high = price_levels[i + 1]
                    if row_low <= level_high and row_high >= level_low:
                        overlap = min(row_high, level_high) - max(row_low, level_low)
                        profile.iloc[i] += row_volume * (overlap / (row_high - row_low))

            # Find Point of Control (price level with highest volume)
            poc_idx = int(profile.idxmax())
            poc_price = price_levels[poc_idx] + price_delta / 2

            # Calculate Value Area (70% of total volume)
            total_volume = float(profile.sum())
            sorted_idx = profile.sort_values(ascending=False).index
            cumsum = 0.0
            value_area_idx = []

            for idx in sorted_idx:
                cumsum += float(profile.iloc[int(idx)])
                value_area_idx.append(int(idx))
                if cumsum >= total_volume * 0.7:
                    break

            value_area = price_levels[max(value_area_idx)] + price_delta / 2

            return profile, poc_price, value_area

        except Exception as e:
            logger.error(f"Error calculating volume profile: {e}")
            return pd.Series(dtype=float), 0.0, 0.0

    def detect_volume_patterns(self, df: pd.DataFrame, profile: pd.Series) -> Dict[str, float]:
        """
        Detect volume-based patterns.

        Args:
            df: Price DataFrame
            profile: Volume profile series

        Returns:
            Dictionary of pattern names to confidence levels
        """
        patterns = {}
        try:
            current_price = float(df['close'].iloc[-1])

            # Find high volume nodes (HVN)
            volume_threshold = float(profile.quantile(self.volume_threshold))
            hvn_indices = profile[profile > volume_threshold].index.tolist()

            # Find low volume nodes (LVN)
            lvn_threshold = float(profile.quantile(0.2))  # Bottom 20%
            lvn_indices = profile[profile < lvn_threshold].index.tolist()

            # Calculate price per level
            price_min = float(df['low'].min())
            price_max = float(df['high'].max())
            price_delta = (price_max - price_min) / self.price_levels

            # Check for price near HVN
            for idx in hvn_indices:
                level_price = price_min + idx * price_delta
                if abs(current_price - level_price) < price_delta:
                    patterns['at_hvn'] = 0.8
                    break

            # Check for price in LVN
            for idx in lvn_indices:
                level_price = price_min + idx * price_delta
                if abs(current_price - level_price) < price_delta:
                    patterns['in_lvn'] = 0.7
                    break

            # Check for price acceptance
            recent_prices = [float(p) for p in df['close'].tail(10)]
            for idx in hvn_indices:
                level_price = price_min + idx * price_delta
                if all(abs(p - level_price) < price_delta for p in recent_prices):
                    patterns['price_acceptance'] = 0.9
                    break

            # Check for price rejection
            if len(df) >= 5:
                recent_high = float(df['high'].tail(5).max())
                recent_close = float(df['close'].iloc[-1])

                for idx in hvn_indices:
                    level_price = price_min + idx * price_delta
                    if (abs(recent_high - level_price) < price_delta and
                        recent_close < level_price - price_delta):
                        patterns['price_rejection'] = 0.8
                        break

        except Exception as e:
            logger.error(f"Error detecting volume patterns: {e}")

        return patterns

    def calculate_indicator(self, df: pd.DataFrame) -> Optional[ProfileData]:
        """Calculate volume profile and related indicators."""
        try:
            # Calculate volume profile
            profile, poc_price, value_area = self.calculate_volume_profile(df)
            if profile.empty:
                return None

            current_price = float(df['close'].iloc[-1])

            return {
                'current_price': current_price,
                'poc_price': poc_price,
                'value_area': value_area,
                'profile': profile
            }

        except Exception as e:
            logger.error(f"Error calculating volume profile indicators: {e}")
            return None

    def analyze_market(self, df: pd.DataFrame, profile_data: ProfileData) -> Optional[Signal]:
        """
        Analyze market conditions using volume profile and additional indicators.

        Args:
            df: Price DataFrame
            profile_data: Volume profile data

        Returns:
            Signal if conditions are met, None otherwise
        """
        try:
            # Calculate market trend
            trend = self.calculate_market_trend(df)

            # Detect volume patterns
            profile = profile_data['profile']
            if not isinstance(profile, pd.Series):
                return None
            volume_patterns = self.detect_volume_patterns(df, profile)

            # Get current market position
            current_price = profile_data['current_price']
            poc_price = profile_data['poc_price']
            value_area = profile_data['value_area']

            # Volume confirmation
            volume = float(df['volume'].iloc[-1])
            volume_ma = float(df['volume'].rolling(window=20).mean().iloc[-1])
            volume_confirmed = volume > volume_ma

            # Generate signals with multiple confirmations
            signal = None

            # Check for potential buy signal
            if current_price < poc_price:  # Price below POC
                if trend > 0:  # Uptrend confirmation
                    confidence = 0.5 + (abs(trend) * 0.3)  # Base confidence + trend strength

                    # Add pattern confidence
                    if 'at_hvn' in volume_patterns:
                        confidence += volume_patterns['at_hvn'] * 0.2
                    if 'price_acceptance' in volume_patterns:
                        confidence += volume_patterns['price_acceptance'] * 0.2

                    # Volume confirmation
                    if volume_confirmed:
                        confidence += 0.1

                    if confidence > 0.7:  # High confidence threshold
                        signal = Signal(
                            'volume_profile',
                            SignalType.BUY,
                            f"POC: {poc_price:.2f}"
                        )
                        logger.info(f"Buy signal generated with confidence {confidence:.2f}")

            # Check for potential sell signal
            elif current_price > value_area:  # Price above value area
                if trend < 0:  # Downtrend confirmation
                    confidence = 0.5 + (abs(trend) * 0.3)  # Base confidence + trend strength

                    # Add pattern confidence
                    if 'in_lvn' in volume_patterns:
                        confidence += volume_patterns['in_lvn'] * 0.2
                    if 'price_rejection' in volume_patterns:
                        confidence += volume_patterns['price_rejection'] * 0.2

                    # Volume confirmation
                    if volume_confirmed:
                        confidence += 0.1

                    if confidence > 0.7:  # High confidence threshold
                        signal = Signal(
                            'volume_profile',
                            SignalType.SELL,
                            f"VA: {value_area:.2f}"
                        )
                        logger.info(f"Sell signal generated with confidence {confidence:.2f}")

            return signal

        except Exception as e:
            logger.error(f"Error analyzing market: {e}")
            return None
