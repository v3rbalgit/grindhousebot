from enum import Enum
from typing import Optional, List, Dict, Union
from pydantic import BaseModel, Field, field_validator
from dataclasses import dataclass
from utils.constants import interval_to_minutes


class StrategyType(str, Enum):
    """Available trading strategies."""
    RSI = "rsi"
    MACD = "macd"
    BOLLINGER = "bollinger"
    ICHIMOKU = "ichimoku"
    HARMONIC = "harmonic"
    VOLUME_PROFILE = "volume_profile"
    ALL = "all"  # Special case to enable all strategies


class SignalType(str, Enum):
    """Types of trading signals."""
    BUY = "buy"
    SELL = "sell"


@dataclass(frozen=True)
class Signal:
    """Trading signal data."""
    name: str
    type: str
    value: Union[float, str]


@dataclass(slots=True)
class PriceData:
    """Price data for a trading symbol."""
    symbol: str
    timestamp: int
    open: float
    high: float
    low: float
    close: float
    volume: float
    turnover: float

    def to_dict(self) -> Dict[str, float]:
        """Convert to dictionary for DataFrame creation."""
        return {
            'open': self.open,
            'high': self.high,
            'low': self.low,
            'close': self.close,
            'volume': self.volume
        }


class SignalConfig(BaseModel):
    """
    Configuration for signal generation.

    Features:
    - Configurable time interval
    - Window size for historical data
    - Strategy selection
    - Symbol tracking
    """
    interval: int = Field(60, description="Interval in minutes")
    strategy_type: StrategyType = Field(StrategyType.RSI, description="Strategy to use")
    window: int = Field(100, description="Number of candles to keep")
    symbols: List[str] = Field(default_factory=list, description="Symbols to track")

    @field_validator('interval', mode='before')
    @classmethod
    def validate_interval(cls, v: Union[str, int]) -> int:
        """Convert interval to minutes if needed."""
        if isinstance(v, str):
            return interval_to_minutes(v)
        return v


class SignalData(BaseModel):
    """Model for signal events."""
    symbol: str
    strategy: StrategyType
    signal_type: SignalType
    value: Union[float, str]
    timestamp: int
    price: float


# Command Models
class Command(BaseModel):
    """Base model for bot commands."""
    command: str = Field(..., description="The command name without the ! prefix")


class ListenCommand(Command):
    """Model for listen commands."""
    command: str = "listen"
    strategies: List[StrategyType] = Field(..., description="Strategies to listen to")

    @field_validator('strategies', mode='before')
    @classmethod
    def validate_strategies(cls, v: Union[str, List[str]]) -> List[StrategyType]:
        """Convert string input to list of strategies."""
        if isinstance(v, str):
            v = [s.strip() for s in v.split(',')]
        return [StrategyType(s.lower()) for s in v]


class UnlistenCommand(Command):
    """Model for unlisten commands."""
    command: str = "unlisten"
    strategy: Optional[StrategyType] = Field(None, description="Strategy to stop listening to")


class TopCommand(Command):
    """Model for top commands."""
    command: str = "top"
    type: str = Field(..., description="winners or losers")


class ClearCommand(Command):
    """Model for clear commands."""
    command: str = "clear"
    count: int = Field(..., ge=1, description="Number of messages to clear")
