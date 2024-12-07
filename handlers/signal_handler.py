from typing import Dict, List, Optional
from dataclasses import dataclass
import numpy as np
from utils.models import SignalData, SignalType, StrategyType


@dataclass
class AggregatedSignal:
    """Represents an aggregated trading signal with combined confidence."""
    symbol: str
    signal_type: SignalType
    confidence: float
    price: float
    timestamp: int
    supporting_signals: List[SignalData]


class SignalHandler:
    """Handles aggregation and analysis of trading signals."""

    # Discord message limit
    DISCORD_CHAR_LIMIT = 2000
    MAX_SIGNALS_PER_MESSAGE = 10
    MIN_SIGNAL_CONFIDENCE = 0.3

    # Strategy weights lookup table
    STRATEGY_WEIGHTS = {
        StrategyType.RSI: 0.32,       # Strong reversal signals
        StrategyType.ICHIMOKU: 0.27,  # Multiple confirmations
        StrategyType.MACD: 0.23,      # Good trend change signals
        StrategyType.BOLLINGER: 0.18  # Volatility-based signals
    }

    # Signal value description templates
    SIGNAL_TEMPLATES = {
        StrategyType.RSI: "RSI {:.0f}",
        StrategyType.MACD: "MACD Div {:.2%}",
        StrategyType.BOLLINGER: "BB {:.2%}",
        StrategyType.ICHIMOKU: "Cloud {:.2%}"
    }

    def __init__(self):
        """Initialize the signal handler."""
        # Pre-calculate total weight for normalization
        self.total_weight = sum(self.STRATEGY_WEIGHTS.values())

    def _describe_signal_value(self, signal: SignalData) -> str:
        """Generate a descriptive explanation of the signal value."""
        template = self.SIGNAL_TEMPLATES.get(signal.strategy)
        if template:
            return template.format(float(signal.value))
        return str(signal.value)

    def aggregate_signals(self, signals: Dict[str, Dict[StrategyType, SignalData]]) -> List[AggregatedSignal]:
        """
        Aggregate signals across all strategies and calculate combined confidence.

        Args:
            signals: Dictionary of signals by symbol and strategy

        Returns:
            List of aggregated signals, sorted by confidence
        """
        aggregated_signals = []

        for symbol, strategy_signals in signals.items():
            if not strategy_signals:
                continue

            # Filter and group signals by type
            buy_signals = []
            sell_signals = []

            for signal in strategy_signals.values():
                if signal.confidence >= self.MIN_SIGNAL_CONFIDENCE:
                    if signal.signal_type == SignalType.BUY:
                        buy_signals.append(signal)
                    else:
                        sell_signals.append(signal)

            # Process buy and sell signals
            for signal_group in (buy_signals, sell_signals):
                if signal_group:
                    signal_type = signal_group[0].signal_type
                    agg_signal = self._create_aggregated_signal(signal_group, signal_type)
                    if agg_signal:
                        aggregated_signals.append(agg_signal)

        # Sort by confidence once at the end
        return sorted(aggregated_signals, key=lambda x: x.confidence, reverse=True)

    def _create_aggregated_signal(self, signals: List[SignalData], signal_type: SignalType) -> Optional[AggregatedSignal]:
        """Create an aggregated signal from a list of signals."""
        if not signals:
            return None

        # Calculate weighted confidence efficiently
        confidences = np.array([signal.confidence for signal in signals])
        weights = np.array([self.STRATEGY_WEIGHTS.get(signal.strategy, 0.18) for signal in signals])

        # Calculate base confidence
        weighted_confidence = np.sum(confidences * weights) / self.total_weight

        # Apply agreement bonus if multiple signals
        if len(signals) > 1:
            # Scale bonus by average confidence
            bonus = min((len(signals) - 1) * 0.1, 0.2) * np.mean(confidences)
            weighted_confidence *= (1 + bonus)

        # Ensure confidence is between 0 and 1
        final_confidence = float(min(weighted_confidence, 1.0))

        # Get latest signal for timestamp and price
        latest_signal = max(signals, key=lambda x: x.timestamp)

        return AggregatedSignal(
            symbol=latest_signal.symbol,
            signal_type=signal_type,
            confidence=final_confidence,
            price=latest_signal.price,
            timestamp=latest_signal.timestamp,
            supporting_signals=signals
        )

    def _format_signal_batch(self, signals: List[AggregatedSignal], header: str = "") -> List[str]:
        """Format a batch of signals into message chunks."""
        messages: List[str] = []
        current_message = [header] if header else []

        for signal in signals:
            # Pre-format indicator details
            indicators = [self._describe_signal_value(s) for s in signal.supporting_signals]

            url = f"https://www.bybit.com/trade/usdt/{signal.symbol}"

            # Build signal message
            signal_msg = [
                f"[🌐]({url}) **{signal.symbol}** ({int(signal.confidence * 100)}% confidence)",
                f"Price: {signal.price}",
                " | ".join(indicators),
                ""  # Empty line for spacing
            ]

            # Check message length
            potential_msg = "\n".join(current_message + signal_msg)
            if len(potential_msg) > self.DISCORD_CHAR_LIMIT and current_message:
                messages.append("\n".join(current_message))
                current_message = [header] if header else []

            current_message.extend(signal_msg)

        if current_message:
            messages.append("\n".join(current_message))

        return messages

    async def format_discord_message(self, signals: List[AggregatedSignal]) -> List[str]:
        """Format signals into Discord messages."""
        if not signals:
            return ["No significant trading signals at this time."]

        # Take top signals up to limit and group by type
        top_signals = signals[:self.MAX_SIGNALS_PER_MESSAGE]
        buy_signals = [s for s in top_signals if s.signal_type == SignalType.BUY]
        sell_signals = [s for s in top_signals if s.signal_type == SignalType.SELL]

        messages: List[str] = []

        if buy_signals:
            messages.extend(self._format_signal_batch(
                buy_signals,
                "🎯 **High-Confidence Trading Signals**\n\n📈 **BUY Signals**"
            ))

        if sell_signals:
            messages.extend(self._format_signal_batch(
                sell_signals,
                "📉 **SELL Signals**"
            ))

        return messages
