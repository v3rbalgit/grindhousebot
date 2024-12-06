import pandas as pd
from typing import Optional, Dict, Tuple, TypedDict
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
            # Get price data efficiently
            high = df['high']
            low = df['low']
            volume = df['volume']

            # Calculate price range
            price_min = float(low.min())
            price_max = float(high.max())
            if price_min >= price_max:
                return pd.Series(dtype=float), 0.0, 0.0

            price_delta = (price_max - price_min) / self.price_levels

            # Create price levels
            price_levels = [price_min + i * price_delta for i in range(self.price_levels + 1)]
            profile = pd.Series(0.0, index=range(self.price_levels))

            # Distribute volume across price levels efficiently
            for i in range(len(df)):
                row_low = float(low.iat[i])
                row_high = float(high.iat[i])
                row_volume = float(volume.iat[i])
                row_range = row_high - row_low

                if row_range <= 0:
                    continue

                for j in range(self.price_levels):
                    level_low = price_levels[j]
                    level_high = price_levels[j + 1]
                    if row_low <= level_high and row_high >= level_low:
                        overlap = min(row_high, level_high) - max(row_low, level_low)
                        profile.iloc[j] += row_volume * (overlap / row_range)

            # Find Point of Control efficiently
            poc_idx = int(profile.idxmax())
            poc_price = float(price_levels[poc_idx] + price_delta / 2)

            # Calculate Value Area efficiently
            total_volume = float(profile.sum())
            if total_volume == 0:
                return profile, poc_price, poc_price

            sorted_idx = profile.sort_values(ascending=False).index
            cumsum = 0.0
            value_area_idx = []

            for idx in sorted_idx:
                cumsum += float(profile.iloc[int(idx)])
                value_area_idx.append(int(idx))
                if cumsum >= total_volume * 0.7:
                    break

            value_area = float(price_levels[max(value_area_idx)] + price_delta / 2)

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
            # Get price data efficiently
            close = df['close']
            high = df['high']
            low = df['low']
            current_price = float(close.iat[-1])

            # Calculate price levels
            price_min = float(low.min())
            price_max = float(high.max())
            price_delta = (price_max - price_min) / self.price_levels

            # Find volume nodes efficiently
            volume_threshold = float(profile.quantile(self.volume_threshold))
            lvn_threshold = float(profile.quantile(0.2))  # Bottom 20%

            hvn_indices = profile[profile > volume_threshold].index
            lvn_indices = profile[profile < lvn_threshold].index

            # Cache price calculations
            level_prices = {
                idx: price_min + idx * price_delta
                for idx in set(hvn_indices) | set(lvn_indices)
            }

            # Check for price near HVN efficiently
            for idx in hvn_indices:
                if abs(current_price - level_prices[idx]) < price_delta:
                    patterns['at_hvn'] = 0.8
                    break

            # Check for price in LVN efficiently
            for idx in lvn_indices:
                if abs(current_price - level_prices[idx]) < price_delta:
                    patterns['in_lvn'] = 0.7
                    break

            # Check for price acceptance efficiently
            if len(df) >= 10:
                recent_closes = close.tail(10)
                for idx in hvn_indices:
                    level_price = level_prices[idx]
                    if all(abs(float(p) - level_price) < price_delta for p in recent_closes):
                        patterns['price_acceptance'] = 0.9
                        break

            # Check for price rejection efficiently
            if len(df) >= 5:
                recent_high = float(high.tail(5).max())
                for idx in hvn_indices:
                    level_price = level_prices[idx]
                    if (abs(recent_high - level_price) < price_delta and
                        current_price < level_price - price_delta):
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

            current_price = float(df['close'].iat[-1])

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

            # Volume confirmation (optimized)
            volume = df['volume']
            volume_ma = volume.rolling(window=20).mean()
            volume_confirmed = volume.iat[-1] > volume_ma.iat[-1]

            # Generate signals with multiple confirmations
            signal = None

            # Check for potential buy signal
            if current_price < poc_price:  # Price below POC
                if trend > 0:  # Uptrend confirmation
                    confidence = 0.5 + (abs(trend) * 0.3)  # Base confidence + trend strength

                    # Add pattern confidence efficiently
                    for pattern, value in volume_patterns.items():
                        if pattern in ('at_hvn', 'price_acceptance'):
                            confidence += value * 0.2

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

                    # Add pattern confidence efficiently
                    for pattern, value in volume_patterns.items():
                        if pattern in ('in_lvn', 'price_rejection'):
                            confidence += value * 0.2

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
