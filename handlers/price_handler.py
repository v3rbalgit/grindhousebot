import pandas as pd
import asyncio
from typing import Dict, List, Set, Optional
from discord import Message
from collections import deque
from utils.models import PriceData, SignalData, SignalConfig, StrategyType, SignalType
from clients import BybitClient, OpenRouterClient
from strategies import StrategyFactory
from handlers.signal_handler import SignalHandler
from utils.logger import logger
from utils.constants import DEFAULT_INTERVAL, validate_interval, interval_to_minutes


class PriceHandler:
    """
    Handles price data processing and signal generation.
    """

    FIXED_WINDOW_SIZE = 150

    def __init__(self,
                 message: Message,
                 bybit_client: BybitClient,
                 openrouter_client: Optional[OpenRouterClient] = None,
                 interval: Optional[str] = None) -> None:
        """
        Initialize the price handler.

        Args:
        message: Discord message for sending responses
        bybit_client: Async Bybit client
        openrouter_client: OpenRouter client for AI-enhanced analysis
        interval: Optional interval override (e.g., '1', '5', '15', '60', etc.)
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

        # Initialize signal handler
        self.signal_handler = SignalHandler(openrouter_client)

        # Signal batching
        self._updated_symbols: Set[str] = set()
        self._current_candle_time: Optional[int] = None

        # Validate and set interval
        self.interval_str = validate_interval(interval) if interval else DEFAULT_INTERVAL
        self.interval_minutes = interval_to_minutes(self.interval_str)

    @property
    def interval(self) -> str:
        """Get the interval string used for WebSocket subscriptions."""
        return self.interval_str

    @property
    def active_strategies(self) -> List[StrategyType]:
        """Get list of active strategies."""
        return list(self.strategies.keys())

    async def add_strategy(self, strategy_type: StrategyType) -> None:
        """Add a new strategy to monitor."""
        if strategy_type in self.strategies:
            return

        config = SignalConfig(
            interval=self.interval_minutes,
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
        """Initialize data for a new symbol."""
        try:
            # Fetch historical data using fixed window size
            klines = await self.client.get_klines(
                symbol=symbol,
                interval=self.interval_str,
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
                self.signals.clear()  # Clear old signals for new timeframe

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

            # If we've received updates for all symbols, process and send aggregated signals
            if len(self._updated_symbols) == len(self.symbols):
                await self._process_aggregated_signals()
                self._updated_symbols.clear()

        except Exception as e:
            logger.error(f"Error processing candle data for {symbol}: {e}")

    async def _check_signals(self, symbol: str) -> None:
        """Check for trading signals for a symbol."""
        # Get latest price data
        latest_price = self.price_data[symbol][-1]

        # Check signals for each strategy
        for strategy_type, strategy in self._strategy_instances.items():
            try:
                # Generate signal
                signals = strategy.generate_signals({symbol: latest_price})
                signal = signals.get(symbol)

                if signal:
                    # Create signal data
                    signal_data = SignalData(
                        symbol=symbol,
                        strategy=strategy_type,
                        signal_type=SignalType(signal.type),
                        value=signal.value,
                        timestamp=latest_price.timestamp,
                        price=latest_price.close
                    )

                    # Store signal
                    if symbol not in self.signals:
                        self.signals[symbol] = {}
                    self.signals[symbol][strategy_type] = signal_data

            except Exception as e:
                logger.error(f"Error checking {strategy_type} signals for {symbol}: {e}")

    async def _process_aggregated_signals(self) -> None:
        """Process and send aggregated signals."""
        try:
            # Aggregate signals using SignalHandler
            aggregated_signals = self.signal_handler.aggregate_signals(self.signals)

            if aggregated_signals:
                # Format message using SignalHandler
                message = await self.signal_handler.format_discord_message(aggregated_signals)

                # Send to Discord
                await self.message.channel.send(message)

        except Exception as e:
            logger.error(f"Error processing aggregated signals: {e}")

    async def _check_symbols(self) -> None:
        """Periodically check for new and delisted symbols."""
        while self._running:
            await asyncio.sleep(3600)  # Check every hour

            try:
                # Get current active symbols
                current_symbols = set(await self.client.get_usdt_instruments())

                # Find new and delisted symbols
                new_symbols = current_symbols - self.symbols
                delisted_symbols = self.symbols - current_symbols

                async with self.symbols_lock:
                    # Handle new symbols
                    for symbol in new_symbols:
                        await self._initialize_symbol_data(symbol)
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
