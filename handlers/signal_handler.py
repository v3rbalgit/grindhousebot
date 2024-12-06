from typing import Dict, List, Optional
from dataclasses import dataclass
from utils.models import SignalData, SignalType, StrategyType
from utils.logger import logger
from clients.openrouter_client import OpenRouterClient


@dataclass
class AggregatedSignal:
    """Represents an aggregated trading signal with combined confidence."""
    symbol: str
    signal_type: SignalType
    confidence: float
    price: float
    timestamp: int
    supporting_signals: List[SignalData]
    analysis: str


class SignalHandler:
    """
    Handles aggregation and analysis of trading signals across multiple strategies.

    Features:
    - Signal aggregation across strategies
    - Confidence score calculation
    - Signal ranking and filtering
    - AI-enhanced signal analysis
    """

    def __init__(self, openrouter_client: Optional[OpenRouterClient] = None):
        """Initialize the signal handler."""
        self.openrouter_client = openrouter_client
        self.confidence_weights = {
            StrategyType.RSI: 0.8,           # Strong weight for RSI as it's a reliable indicator
            StrategyType.MACD: 0.7,          # Good for trend confirmation
            StrategyType.BOLLINGER: 0.75,    # Effective for volatility-based signals
            StrategyType.ICHIMOKU: 0.85,     # High weight for multiple confirmations
            StrategyType.VOLUME_PROFILE: 0.6  # Support/resistance levels
        }
        self.min_confidence_threshold = 0.7   # Minimum confidence to generate a signal

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

        # Sort by confidence score
        return sorted(aggregated_signals, key=lambda x: x.confidence, reverse=True)

    def _create_aggregated_signal(self, signals: List[SignalData], signal_type: SignalType) -> Optional[AggregatedSignal]:
        """Create an aggregated signal from a list of signals of the same type."""
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

        # Only create signal if confidence meets threshold
        if confidence < self.min_confidence_threshold:
            return None

        # Use the most recent signal's price and timestamp
        latest_signal = max(signals, key=lambda x: x.timestamp)

        return AggregatedSignal(
            symbol=latest_signal.symbol,
            signal_type=signal_type,
            confidence=confidence,
            price=latest_signal.price,
            timestamp=latest_signal.timestamp,
            supporting_signals=signals,
            analysis=""  # Will be filled by generate_analysis
        )

    async def generate_analysis(self, signal: AggregatedSignal) -> str:
        """Generate a detailed analysis of the trading signal."""
        try:
            if not self.openrouter_client:
                return self._generate_basic_analysis(signal)

            # Prepare signal information for AI analysis
            signal_info = self._prepare_signal_info(signal)

            # Generate prompt for AI
            prompt = f"""Analyze this trading signal and provide a concise, professional analysis:

Symbol: {signal.symbol}
Signal Type: {signal.signal_type.value}
Confidence: {signal.confidence:.2f}
Current Price: {signal.price}

Supporting Signals:
{signal_info}

Provide a brief, clear trading recommendation including:
1. Key reasons for the signal
2. Important price levels to watch
3. Potential risks
4. Suggested stop loss and take profit levels (% based)
"""

            # Get AI analysis
            response = await self.openrouter_client.generate_text(prompt)
            return response if response else self._generate_basic_analysis(signal)

        except Exception as e:
            logger.error(f"Error generating analysis: {e}")
            return self._generate_basic_analysis(signal)

    def _prepare_signal_info(self, signal: AggregatedSignal) -> str:
        """Prepare signal information for analysis."""
        info = []
        for s in signal.supporting_signals:
            value = f"{s.value:.2f}" if isinstance(s.value, (int, float)) else s.value
            info.append(f"- {s.strategy.value.upper()}: {value}")
        return "\n".join(info)

    def _generate_basic_analysis(self, signal: AggregatedSignal) -> str:
        """Generate a basic analysis when AI is not available."""
        signal_type = "STRONG BUY" if signal.signal_type == SignalType.BUY else "STRONG SELL"
        confidence_text = "High" if signal.confidence > 0.8 else "Medium"

        supporting_strategies = [s.strategy.value.upper() for s in signal.supporting_signals]

        return (
            f"{signal_type} Signal ({confidence_text} Confidence: {signal.confidence:.2f})\n"
            f"Confirmed by: {', '.join(supporting_strategies)}\n"
            f"Current Price: {signal.price:.8f}"
        )

    async def format_discord_message(self, signals: List[AggregatedSignal]) -> str:
        """Format signals for Discord message."""
        if not signals:
            return "No significant trading signals at this time."

        message = ["🎯 **High-Confidence Trading Signals**\n"]

        # Group signals by type
        buy_signals = [s for s in signals if s.signal_type == SignalType.BUY]
        sell_signals = [s for s in signals if s.signal_type == SignalType.SELL]

        # Format buy signals
        if buy_signals:
            message.append("📈 **BUY Opportunities**")
            for signal in buy_signals:
                # Generate analysis for each signal
                analysis = await self.generate_analysis(signal)
                message.extend([
                    f"**{signal.symbol}** (Confidence: {signal.confidence:.2f})",
                    f"Price: {signal.price:.8f}",
                    f"{analysis}",
                    ""  # Empty line for spacing
                ])

        # Format sell signals
        if sell_signals:
            message.append("📉 **SELL Opportunities**")
            for signal in sell_signals:
                # Generate analysis for each signal
                analysis = await self.generate_analysis(signal)
                message.extend([
                    f"**{signal.symbol}** (Confidence: {signal.confidence:.2f})",
                    f"Price: {signal.price:.8f}",
                    f"{analysis}",
                    ""  # Empty line for spacing
                ])

        return "\n".join(message)
