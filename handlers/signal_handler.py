from typing import Dict, List, Optional, Set
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
    DISCORD_CHAR_LIMIT = 4000
    MAX_SIGNALS_PER_MESSAGE = 10

    # Signal value description templates
    SIGNAL_TEMPLATES = {
        StrategyType.RSI: "RSI {:.0f}",
        StrategyType.MACD: "MACD Div {:.2%}",
        StrategyType.BOLLINGER: "BB {:.2%}",
        StrategyType.ICHIMOKU: "Cloud {:.2%}"
    }

    def _describe_signal_value(self, signal: SignalData) -> str:
        """Generate a descriptive explanation of the signal value."""
        template = self.SIGNAL_TEMPLATES.get(signal.strategy)
        if template:
            return template.format(float(signal.value))
        return str(signal.value)

    def aggregate_signals(self, signals: Dict[str, Dict[StrategyType, SignalData]], active_strategies: Set[StrategyType]) -> List[AggregatedSignal]:
        """
        Aggregate signals across all strategies and calculate combined confidence.

        Args:
            signals: Dictionary of signals by symbol and strategy
            active_strategies: Set of strategies currently being listened to

        Returns:
            List of aggregated signals, sorted by confidence
        """
        # Early return for empty inputs to avoid unnecessary processing
        if not signals or not active_strategies:
            return []

        aggregated_signals: List[AggregatedSignal] = []
        # Pre-calculate active strategy count to avoid repeated len() calls
        active_strat_count = len(active_strategies)

        for symbol, strategy_signals in signals.items():
            if not strategy_signals:
                continue

            # Group signals by type using dictionary views for efficiency
            # This avoids creating unnecessary intermediate lists
            signal_values = strategy_signals.values()
            signal_types = {SignalType.BUY: [], SignalType.SELL: []}

            # Single pass grouping of signals by their type
            # More efficient than multiple list comprehensions
            for signal in signal_values:
                signal_types[signal.signal_type].append(signal)

            # Process non-empty signal groups
            # We only create aggregated signals for groups that have signals
            for signal_type, signal_group in signal_types.items():
                if signal_group:
                    agg_signal = self._create_aggregated_signal(signal_group, signal_type, active_strat_count)
                    if agg_signal:
                        aggregated_signals.append(agg_signal)

        if not aggregated_signals:
            return []

        # Use numpy for efficient calculations of confidence scores
        # This is faster than Python's built-in functions for numerical operations
        confidences = np.fromiter((s.confidence for s in aggregated_signals), dtype=np.float64)
        avg_confidence = np.mean(confidences)

        # Filter and sort in one pass using numpy
        # This is more efficient than doing separate filter and sort operations
        # We only keep signals with above-average confidence
        mask = confidences >= avg_confidence
        filtered_signals = [s for i, s in enumerate(aggregated_signals) if mask[i]]

        # Sort by confidence in descending order
        return sorted(filtered_signals, key=lambda x: x.confidence, reverse=True)

    def _create_aggregated_signal(self, signals: List[SignalData], signal_type: SignalType, active_strat_count: int) -> Optional[AggregatedSignal]:
        """Create an aggregated signal from a list of signals."""
        if not signals:
            return None

        signal_count = len(signals)

        # Calculate average confidence using numpy array operations
        # This is more efficient than Python's built-in mean calculation
        confidences = np.fromiter((signal.confidence for signal in signals), dtype=np.float64)
        avg_confidence = np.mean(confidences)

        # Calculate the ratio of agreeing strategies vs active strategies
        # This represents how many of the strategies we're listening to are in agreement
        # Higher ratio means more strategies agree on this signal
        strategy_agreement_ratio = signal_count / active_strat_count

        # Combine average confidence with agreement ratio
        # This ensures higher confidence when more of our active strategies agree
        final_confidence = avg_confidence * strategy_agreement_ratio

        # Find the latest signal using numpy's argmax
        # This is more efficient than using max() with a key function
        timestamps = np.fromiter((signal.timestamp for signal in signals), dtype=np.int64)
        latest_idx = np.argmax(timestamps)
        latest_signal = signals[latest_idx]

        return AggregatedSignal(
            symbol=latest_signal.symbol,
            signal_type=signal_type,
            confidence=float(final_confidence),
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
                f"**[{signal.symbol}]({url})** ({int(signal.confidence * 100)}% confidence)",
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
        else:
            messages: List[str] = ["🎯 **High-Confidence Trading Signals**\n\n"]

            # Take top signals up to limit and group by type
            top_signals = signals[:self.MAX_SIGNALS_PER_MESSAGE]
            buy_signals = [s for s in top_signals if s.signal_type == SignalType.BUY]
            sell_signals = [s for s in top_signals if s.signal_type == SignalType.SELL]

            if buy_signals:
                messages.extend(self._format_signal_batch(
                    buy_signals,
                    "📈 **BUY Signals**"
                ))

            if sell_signals:
                messages.extend(self._format_signal_batch(
                    sell_signals,
                    "📉 **SELL Signals**"
                ))

            return messages
