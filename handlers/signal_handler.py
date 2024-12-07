from typing import Dict, List, Optional
from dataclasses import dataclass
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

    def __init__(self):
        """Initialize the signal handler."""
        self.confidence_weights = {
            StrategyType.RSI: 0.8,           # Strong weight for RSI as it's a reliable indicator
            StrategyType.MACD: 0.7,          # Good for trend confirmation
            StrategyType.BOLLINGER: 0.75,    # Effective for volatility-based signals
            StrategyType.ICHIMOKU: 0.85      # High weight for multiple confirmations
        }
        # Increased threshold since we want strong combined signals
        self.min_confidence_threshold = 0.8

    def _describe_signal_value(self, signal: SignalData) -> str:
        """Generate a descriptive explanation of the signal value."""
        if signal.strategy == StrategyType.RSI:
            # RSI values are 0-100
            value = float(signal.value)
            if signal.signal_type == SignalType.BUY:
                return f"RSI {value:.0f} (Oversold)"
            else:
                return f"RSI {value:.0f} (Overbought)"

        elif signal.strategy == StrategyType.MACD:
            # MACD signals are crossovers
            if signal.signal_type == SignalType.BUY:
                return "MACD Bullish Cross"
            else:
                return "MACD Bearish Cross"

        elif signal.strategy == StrategyType.BOLLINGER:
            # Bollinger values are percent_b (position within bands)
            if signal.signal_type == SignalType.BUY:
                return "BB Lower Band Test"
            else:
                return "BB Upper Band Test"

        elif signal.strategy == StrategyType.ICHIMOKU:
            # Ichimoku signals include TK values
            if "TK:" in str(signal.value):
                return "Ichimoku TK Cross"
            elif signal.signal_type == SignalType.BUY:
                return "Price Above Cloud"
            else:
                return "Price Below Cloud"

        return str(signal.value)

    def aggregate_signals(self, signals: Dict[str, Dict[StrategyType, SignalData]]) -> List[AggregatedSignal]:
        """
        Aggregate signals across all strategies and calculate combined confidence.

        Args:
            signals: Dictionary of signals by symbol and strategy

        Returns:
            List of aggregated signals, sorted by confidence
        """
        aggregated_signals: List[AggregatedSignal] = []

        for symbol, strategy_signals in signals.items():
            if not strategy_signals:
                continue

            # Group signals by type (BUY/SELL)
            buy_signals = []
            sell_signals = []

            for strategy_type, signal in strategy_signals.items():
                if signal.signal_type == SignalType.BUY:
                    buy_signals.append(signal)
                else:
                    sell_signals.append(signal)

            # Process buy signals
            if buy_signals:
                agg_signal = self._create_aggregated_signal(buy_signals, SignalType.BUY)
                if agg_signal:
                    aggregated_signals.append(agg_signal)

            # Process sell signals
            if sell_signals:
                agg_signal = self._create_aggregated_signal(sell_signals, SignalType.SELL)
                if agg_signal:
                    aggregated_signals.append(agg_signal)

        return sorted(aggregated_signals, key=lambda x: x.confidence, reverse=True)

    def _create_aggregated_signal(self, signals: List[SignalData], signal_type: SignalType) -> Optional[AggregatedSignal]:
        """Create an aggregated signal from a list of signals."""
        if not signals:
            return None

        # Calculate combined confidence
        total_weight = 0
        weighted_confidence = 0

        for signal in signals:
            weight = self.confidence_weights.get(signal.strategy, 0.5)
            total_weight += weight
            weighted_confidence += weight

        if total_weight == 0:
            return None

        confidence = weighted_confidence / total_weight

        # Only create signal if confidence meets higher threshold
        if confidence < self.min_confidence_threshold:
            return None

        latest_signal = max(signals, key=lambda x: x.timestamp)

        return AggregatedSignal(
            symbol=latest_signal.symbol,
            signal_type=signal_type,
            confidence=confidence,
            price=latest_signal.price,
            timestamp=latest_signal.timestamp,
            supporting_signals=signals
        )

    def _format_signal_batch(self, signals: List[AggregatedSignal], header: str = "") -> List[str]:
        """Format a batch of signals into message chunks."""
        messages = []
        current_message = [header] if header else []

        for signal in signals:
            # Format signal message
            signal_msg = [
                f"**{signal.symbol}** ({signal.confidence:.2f})",
                f"Price: {signal.price}"
            ]

            # Add indicator details
            indicators = []
            for s in signal.supporting_signals:
                desc = self._describe_signal_value(s)
                indicators.append(desc)

            if indicators:
                signal_msg.append(" | ".join(indicators))
            signal_msg.append("")  # Empty line for spacing

            # Check if adding this signal would exceed limit
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

        # Sort all signals by confidence first
        sorted_signals = sorted(signals, key=lambda x: x.confidence, reverse=True)

        # Take top signals up to limit
        top_signals = sorted_signals[:self.MAX_SIGNALS_PER_MESSAGE]

        # Group by signal type
        buy_signals = [s for s in top_signals if s.signal_type == SignalType.BUY]
        sell_signals = [s for s in top_signals if s.signal_type == SignalType.SELL]

        messages = []

        if buy_signals:
            header = "🎯 **High-Confidence Trading Signals**\n\n📈 **BUY Signals**"
            messages.extend(self._format_signal_batch(buy_signals, header))

        if sell_signals:
            header = "📉 **SELL Signals**"
            messages.extend(self._format_signal_batch(sell_signals, header))

        return messages
