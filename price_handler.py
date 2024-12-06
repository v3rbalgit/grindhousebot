import pandas as pd
import asyncio
from typing import Dict, List, Set, Optional
from discord import Message
from collections import deque
from utils.models import PriceData, SignalData, SignalConfig, StrategyType, SignalType
from clients import BybitClient
from strategies import StrategyFactory
from utils.logger import logger
from utils.constants import DEFAULT_INTERVAL, DEFAULT_MINUTES


class PriceHandler:
    """
    Handles price data processing and signal generation.
    """

    FIXED_WINDOW_SIZE = 150

    def __init__(self,
                 message: Message,
                 bybit_client: BybitClient) -> None:
        """
        Initialize the price handler.

        Args:
        message: Discord message for sending responses
        bybit_client: Async Bybit client
        """
        self.message = message
        self.client = bybit_client
        self.symbols: Set[str] = set()
        self.symbols_lock = asyncio.Lock()
        self.price_data: Dict[str, deque] = {}
        self.signals: Dict[str, Dict[StrategyType, SignalData]] = {}
        self.strategies: Dict[StrategyType, SignalConfig] = {}
        self._strategy_instances = {}
        self._symbol_check_task: Optional[asyncio.Task] = None
        self._running = True

        # Signal batching
        self._signal_batch: Dict[StrategyType, Dict[SignalType, List[SignalData]]] = {}
        self._updated_symbols: Set[str] = set()
        self._current_candle_time: Optional[int] = None

    @property
    def interval(self) -> str:
        """Get the interval string used for WebSocket subscriptions."""
        return DEFAULT_INTERVAL

    @property
    def active_strategies(self) -> List[StrategyType]:
        """Get list of active strategies."""
        return list(self.strategies.keys())

    async def add_strategy(self, strategy_type: StrategyType) -> None:
        """Add a new strategy to monitor."""
        if strategy_type in self.strategies:
            return

        config = SignalConfig(
            interval=DEFAULT_MINUTES,
            strategy_type=strategy_type,
            window=self.FIXED_WINDOW_SIZE
        )
        self.strategies[strategy_type] = config

        # Initialize strategy instance using factory
        self._strategy_instances[strategy_type] = StrategyFactory.create_strategy(
            strategy_type=strategy_type,
            config=config
        )

        logger.info(f"Added {strategy_type.value.upper()} strategy with {config.interval}m interval")

    async def remove_strategy(self, strategy_type: Optional[StrategyType] = None) -> None:
        """
        Remove a strategy or all strategies.

        Args:
        strategy_type: Strategy to remove, or None to remove all
        """
        if strategy_type:
            self.strategies.pop(strategy_type, None)
            self._strategy_instances.pop(strategy_type, None)
            # Remove signals for this strategy
            for symbol_signals in self.signals.values():
                symbol_signals.pop(strategy_type, None)
            logger.info(f"Removed {strategy_type} strategy")
        else:
            self.strategies.clear()
            self._strategy_instances.clear()
            self.signals.clear()
            logger.info("Removed all strategies")

    async def initialize(self) -> None:
        """Initialize handler with market data."""
        if not self.strategies:
            logger.error("Cannot initialize price handler without strategies")
            return

        # Send initialization start message
        await self.message.channel.send("🔄 Initializing symbols, please wait...")

        # Get all USDT perpetual symbols
        symbols = await self.client.get_usdt_instruments()

        # Initialize symbols one by one, silently
        await asyncio.gather(*(self._initialize_symbol_data(symbol) for symbol in symbols))

        # Send initialization complete message
        await self.message.channel.send(f"✅ Initialization complete. Monitoring {len(self.symbols)} USDT pairs")

        # Start symbol check task
        self._symbol_check_task = asyncio.create_task(self._check_symbols())
        logger.info("Started symbol monitoring task")

    async def _initialize_symbol_data(self, symbol: str) -> None:
        """
        Initialize data for a new symbol.
        """
        try:
            # Use the first strategy's interval for historical data
            interval = next(iter(self.strategies.values())).interval

            # Fetch historical data using fixed window size
            klines = await self.client.get_klines(
                symbol=symbol,
                interval=str(interval),
                limit=self.FIXED_WINDOW_SIZE
            )

            # Initialize deque with fixed window size
            price_deque = deque([PriceData(
                symbol=symbol,
                timestamp=k["start_time"],
                open=k["open"],
                high=k["high"],
                low=k["low"],
                close=k["close"],
                volume=k["volume"],
                turnover=k["turnover"]
            ) for k in klines], maxlen=self.FIXED_WINDOW_SIZE)

            async with self.symbols_lock:
                self.symbols.add(symbol)
                self.price_data[symbol] = price_deque

            # Initialize strategy data
            for strategy in self._strategy_instances.values():
                if symbol not in strategy.dataframes:
                    df = pd.DataFrame(
                        [p.to_dict() for p in price_deque],
                        index=[p.timestamp for p in price_deque]
                    )
                    strategy.dataframes[symbol] = df

        except Exception as e:
            logger.debug(f"Failed to initialize data for {symbol}: {e}")

    async def handle_price_update(self, data: Dict, symbol: str) -> None:
        """
        Process a price update for a symbol.

        Args:
        data: Price update data from WebSocket
        symbol: Symbol being updated
        """
        if symbol not in self.symbols:
            return

        if not isinstance(data, list) or not data:
            logger.warning(f"Invalid data format for {symbol}")
            return

        candle = data[0]
        if not candle.get('confirm', False):
            logger.debug(f"Skipping unconfirmed candle for {symbol}")
            return

        try:
            # Get candle start time
            candle_time = candle["start"]

            # If this is a new candle timeframe, reset tracking
            if self._current_candle_time != candle_time:
                self._current_candle_time = candle_time
                self._updated_symbols.clear()
                self._signal_batch.clear()

            # Create new price data point
            new_price = PriceData(
                symbol=symbol,
                timestamp=candle_time,
                open=float(candle["open"]),
                high=float(candle["high"]),
                low=float(candle["low"]),
                close=float(candle["close"]),
                volume=float(candle["volume"]),
                turnover=float(candle["turnover"])
            )

            # Update price history
            if symbol in self.price_data:
                self.price_data[symbol].append(new_price)
                logger.debug(f"Added new candle for {symbol}")

            # Update strategy dataframes
            for strategy in self._strategy_instances.values():
                if symbol in strategy.dataframes:
                    df = strategy.dataframes[symbol]
                    new_data = pd.DataFrame(
                        [new_price.to_dict()],
                        index=[new_price.timestamp]
                    )
                    df = pd.concat([df, new_data])
                    if len(df) > self.FIXED_WINDOW_SIZE:
                        df = df.iloc[-self.FIXED_WINDOW_SIZE:]
                    strategy.dataframes[symbol] = df

            # Generate signals if we have enough data
            if len(self.price_data[symbol]) >= 2:
                await self._check_signals(symbol)

            # Track that this symbol has been updated
            self._updated_symbols.add(symbol)

            # If we've received updates for all symbols, send the signals
            if len(self._updated_symbols) == len(self.symbols):
                await self._send_signal_batch()
                # Reset for next round
                self._updated_symbols.clear()

        except Exception as e:
            logger.error(f"Error processing candle data for {symbol}: {e}")

    def _add_to_batch(self, signal: SignalData) -> None:
        """Add a signal to the batch."""
        if signal.strategy not in self._signal_batch:
            self._signal_batch[signal.strategy] = {
                SignalType.BUY: [],
                SignalType.SELL: []
            }
        self._signal_batch[signal.strategy][signal.signal_type].append(signal)

    async def _send_signal_batch(self) -> None:
        """Send all batched signals."""
        try:
            # Create a copy of the batch to avoid modification during iteration
            batch_copy = {
                strategy: {
                    signal_type: signals.copy()
                    for signal_type, signals in signal_dict.items()
                }
                for strategy, signal_dict in self._signal_batch.items()
            }

            # Clear the batch before processing to avoid any race conditions
            self._signal_batch.clear()

            # Process the copied batch
            for strategy, signals in batch_copy.items():
                if not any(signals.values()):
                    continue

                message = [f"🔔 **{strategy.upper()} Signals**\n"]

                # Process BUY signals
                if signals[SignalType.BUY]:
                    message.append("📈 **BUY Signals**")
                    # Sort by value if numerical (RSI), or just group if string (MACD)
                    if isinstance(signals[SignalType.BUY][0].value, (int, float)):
                        sorted_signals = sorted(signals[SignalType.BUY], key=lambda x: x.value)
                    else:
                        sorted_signals = signals[SignalType.BUY]

                    for signal in sorted_signals:
                        # Format value based on type
                        value_str = f"{signal.value:.2f}" if isinstance(signal.value, (int, float)) else signal.value
                        message.append(
                            f"{signal.symbol} Price: {signal.price:.8f} "
                            f"{strategy.upper()}: {value_str}"
                        )
                    message.append("")

                # Process SELL signals
                if signals[SignalType.SELL]:
                    message.append("📉 **SELL Signals**")
                    # Sort by value if numerical (RSI), or just group if string (MACD)
                    if isinstance(signals[SignalType.SELL][0].value, (int, float)):
                        sorted_signals = sorted(signals[SignalType.SELL], key=lambda x: x.value, reverse=True)
                    else:
                        sorted_signals = signals[SignalType.SELL]

                    for signal in sorted_signals:
                        # Format value based on type
                        value_str = f"{signal.value:.2f}" if isinstance(signal.value, (int, float)) else signal.value
                        message.append(
                            f"{signal.symbol} Price: {signal.price:.8f} "
                            f"{strategy.upper()}: {value_str}"
                        )

                if len(message) > 1:
                    await self.message.channel.send("\n".join(message))

        except Exception as e:
            logger.error(f"Error sending signal batch: {e}")

    async def _check_symbols(self) -> None:
        """Periodically check for new and delisted symbols."""
        while self._running:
            # Check every hour
            await asyncio.sleep(3600)

            try:
                # Get current active symbols
                current_symbols = set(await self.client.get_usdt_instruments())

                # Find new and delisted symbols
                new_symbols = current_symbols - self.symbols
                delisted_symbols = self.symbols - current_symbols

                async with self.symbols_lock:
                    # Handle new symbols
                    for symbol in new_symbols:
                        if await self._initialize_symbol_data(symbol):
                            self.symbols.add(symbol)
                            await self.message.channel.send(f"📝 New symbol listed: **{symbol}**")

                    # Handle delisted symbols
                    for symbol in delisted_symbols:
                        self.symbols.remove(symbol)
                        self.price_data.pop(symbol, None)
                        self.signals.pop(symbol, None)
                        for strategy in self._strategy_instances.values():
                            strategy.dataframes.pop(symbol, None)
                        await self.message.channel.send(f"🗑️ Symbol delisted: **{symbol}**")

            except Exception as e:
                logger.error(f"Error checking symbols: {e}")

    async def _check_signals(self, symbol: str) -> None:
        """
        Check for trading signals for a symbol.

        Args:
        symbol: Symbol to check signals for
        """
        # Get latest price data
        latest_price = self.price_data[symbol][-1]

        # Check signals for each strategy
        for strategy_type, strategy in self._strategy_instances.items():
            # Generate signal
            signals = strategy.generate_signals({symbol: latest_price})
            signal = signals.get(symbol)

            if not signal:
                # Clear signal if it exists
                if symbol in self.signals and strategy_type in self.signals[symbol]:
                    logger.info(f"Signal cleared for {symbol} ({strategy_type.value.upper()})")
                    self.signals[symbol].pop(strategy_type)
                continue

            # Create signal data
            signal_data = SignalData(
                symbol=symbol,
                strategy=strategy_type,
                signal_type=SignalType(signal.type),
                value=signal.value,
                timestamp=latest_price.timestamp,
                price=latest_price.close
            )

            # Initialize signals dict for symbol if needed
            if symbol not in self.signals:
                self.signals[symbol] = {}

            # Check if this is a new signal
            if (strategy_type not in self.signals[symbol] or
                self.signals[symbol][strategy_type].signal_type != signal_data.signal_type):
                self.signals[symbol][strategy_type] = signal_data
                logger.info(f"New {signal_data.signal_type.value.upper()} signal for {symbol} ({strategy_type.value.upper()}) at {signal_data.price}")
                self._add_to_batch(signal_data)

    async def cleanup(self) -> None:
        """Clean up resources."""
        self._running = False
        if self._symbol_check_task:
            self._symbol_check_task.cancel()
            try:
                await self._symbol_check_task
            except asyncio.CancelledError:
                pass
        logger.info("Cleaned up PriceHandler resources")
