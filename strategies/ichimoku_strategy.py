import pandas as pd
from typing import Optional, Dict
from .base import SignalStrategy
from utils.models import Signal, SignalType
from utils.logger import logger


class IchimokuStrategy(SignalStrategy):
    """Ichimoku Cloud strategy optimized for crypto markets."""

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
            # Log data availability
            candle_count = len(df)

            if candle_count < self.min_candles:
                logger.warning(f"Insufficient data for Ichimoku calculation. "
                             f"Have {candle_count}, need {self.min_candles}")
                return None

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

                # Calculate base values for Senkou spans without shift
                base_senkou_a = (tenkan + kijun) / 2
                base_senkou_b = (high.rolling(window=self.senkou_period).max() +
                               low.rolling(window=self.senkou_period).min()) / 2

                # Get latest values efficiently
                current_close = float(close.iat[-1])
                current_tenkan = float(tenkan.iat[-1])
                current_kijun = float(kijun.iat[-1])

                # Get current cloud values by looking back displacement periods
                try:
                    current_senkou_a = float(base_senkou_a.iat[-self.displacement])
                    current_senkou_b = float(base_senkou_b.iat[-self.displacement])
                except IndexError as e:
                    logger.error(f"Failed to get cloud values at displacement {self.displacement}: {e}")
                    return None

                # Calculate recent price volatility for context
                recent_highs = high.tail(self.tenkan_period)
                recent_lows = low.tail(self.tenkan_period)
                price_range = (recent_highs.max() - recent_lows.min()) / current_close

                return {
                    'close': current_close,
                    'tenkan': current_tenkan,
                    'kijun': current_kijun,
                    'senkou_a': current_senkou_a,
                    'senkou_b': current_senkou_b,
                    'price_range': price_range
                }

            except (IndexError, KeyError) as e:
                logger.error(f"Error accessing Ichimoku values: {e}")
                return None

        except Exception as e:
            logger.error(f"Error calculating Ichimoku: {e}")
            return None

    def analyze_market(self, values: Dict[str, float]) -> Optional[Signal]:
        """
        Generate signal based on Ichimoku cloud position and TK cross strength.

        Args:
            values: Dictionary of current Ichimoku values

        Returns:
            Signal if conditions are met, None otherwise
        """
        try:
            current_close = values['close']
            current_tenkan = values['tenkan']
            current_kijun = values['kijun']
            cloud_top = max(values['senkou_a'], values['senkou_b'])
            cloud_bottom = min(values['senkou_a'], values['senkou_b'])
            price_range = values['price_range']

            # Calculate cloud thickness relative to recent price range
            cloud_thickness = (cloud_top - cloud_bottom) / current_close
            relative_thickness = min(cloud_thickness / price_range, 1.0)

            # Calculate TK cross strength relative to recent price range
            tk_distance = abs(current_tenkan - current_kijun) / current_close
            relative_tk_strength = min(tk_distance / (price_range * 0.3), 1.0)

            # Check for potential buy signal
            if (current_close > cloud_top and  # Price above cloud
                current_tenkan > current_kijun):  # TK cross is bullish

                # Calculate confidence components
                cloud_distance = (current_close - cloud_top) / current_close
                cloud_conf = min(cloud_distance / (price_range * 0.2), 1.0)
                tk_conf = relative_tk_strength
                cloud_strength = relative_thickness

                # Final confidence calculation
                final_confidence = min(
                    (cloud_conf * 0.45) +         # Price position (45%)
                    (tk_conf * 0.35) +            # TK cross strength (35%)
                    (cloud_strength * 0.20),      # Cloud strength (20%)
                    1.0
                )

                signal = Signal(
                    'ichimoku',
                    SignalType.BUY,
                    f"{cloud_distance:.4f}",
                    final_confidence
                )
                logger.info(f"Buy signal generated above Ichimoku cloud (confidence: {final_confidence:.2f})")
                return signal

            # Check for potential sell signal
            elif (current_close < cloud_bottom and  # Price below cloud
                  current_tenkan < current_kijun):  # TK cross is bearish

                # Calculate confidence components
                cloud_distance = (cloud_bottom - current_close) / current_close
                cloud_conf = min(cloud_distance / (price_range * 0.2), 1.0)
                tk_conf = relative_tk_strength
                cloud_strength = relative_thickness

                # Final confidence calculation
                final_confidence = min(
                    (cloud_conf * 0.45) +         # Price position (45%)
                    (tk_conf * 0.35) +            # TK cross strength (35%)
                    (cloud_strength * 0.20),      # Cloud strength (20%)
                    1.0
                )

                signal = Signal(
                    'ichimoku',
                    SignalType.SELL,
                    f"{cloud_distance:.4f}",
                    final_confidence
                )
                logger.info(f"Sell signal generated below Ichimoku cloud (confidence: {final_confidence:.2f})")
                return signal

            return None

        except Exception as e:
            logger.error(f"Error analyzing market: {e}")
            return None
