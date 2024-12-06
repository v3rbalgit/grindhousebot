from typing import Dict, Type
from .base import SignalStrategy
from .rsi_strategy import RSIStrategy
from .macd_strategy import MACDStrategy
from .bollinger_strategy import BollingerStrategy
from .ichimoku_strategy import IchimokuStrategy
from .harmonic_strategy import HarmonicStrategy
from .volume_profile_strategy import VolumeProfileStrategy
from utils.models import StrategyType, SignalConfig
from utils.logger import logger


class StrategyFactory:
    """Factory for creating and managing trading strategies."""

    _strategies: Dict[StrategyType, Type[SignalStrategy]] = {
        StrategyType.RSI: RSIStrategy,
        StrategyType.MACD: MACDStrategy,
        StrategyType.BOLLINGER: BollingerStrategy,
        StrategyType.ICHIMOKU: IchimokuStrategy,
        StrategyType.HARMONIC: HarmonicStrategy,
        StrategyType.VOLUME_PROFILE: VolumeProfileStrategy
    }

    @classmethod
    def create_strategy(cls, strategy_type: StrategyType, config: SignalConfig) -> SignalStrategy:
        """
        Create a new strategy instance.

        Args:
            strategy_type: Type of strategy to create
            config: Configuration for the strategy

        Returns:
            Configured strategy instance

        Raises:
            ValueError: If strategy type is not registered
        """
        if strategy_type not in cls._strategies:
            raise ValueError(f"Unknown strategy type: {strategy_type}")

        strategy_class = cls._strategies[strategy_type]
        return strategy_class(
            interval=config.interval,
            window=config.window
        )

    @classmethod
    def register_strategy(cls, strategy_type: StrategyType, strategy_class: Type[SignalStrategy]) -> None:
        """
        Register a new strategy type.

        Args:
            strategy_type: Type identifier for the strategy
            strategy_class: Strategy class to register
        """
        cls._strategies[strategy_type] = strategy_class
        logger.info(f"Registered new strategy type: {strategy_type}")

    @classmethod
    def get_available_strategies(cls) -> list[StrategyType]:
        """Get list of registered strategy types."""
        return list(cls._strategies.keys())
