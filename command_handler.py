from discord import Message
from typing import Optional, List
from enum import Enum, auto

from price_handler import PriceHandler
from clients import BybitClient, BybitWsClient, OpenRouterClient
from utils.models import StrategyType
from utils.logger import logger
from utils.constants import DEFAULT_INTERVAL


class Order(Enum):
    ASCENDING = auto()
    DESCENDING = auto()


class CommandHandler:
    """Handler for Discord bot commands."""

    def __init__(self, bybit_client: BybitClient, bybit_ws_client: Optional[BybitWsClient] = None):
        """
        Initialize command handler.

        Args:
            bybit_client: Bybit REST client
            bybit_ws_client: Optional Bybit WebSocket client
        """
        self.bybit_client = bybit_client
        self.bybit_ws_client = bybit_ws_client
        self.price_handler: Optional[PriceHandler] = None
        self.chat_client = OpenRouterClient()

    def _parse_strategies(self, strategy_input: str) -> List[StrategyType]:
        """
        Parse strategy input into list of strategies.

        Args:
            strategy_input: Comma-separated strategy names or 'all'

        Returns:
            List of strategy types

        Raises:
            ValueError: If strategy is unknown
        """
        strategy_input = strategy_input.lower().strip()

        # Handle 'all' strategy
        if strategy_input == 'all':
            return [s for s in StrategyType if s != StrategyType.ALL]

        # Parse comma-separated strategies
        strategies = []
        for s in strategy_input.split(','):
            try:
                strategy = StrategyType(s.strip())
                if strategy != StrategyType.ALL:  # Prevent recursive 'all' in list
                    strategies.append(strategy)
            except ValueError:
                raise ValueError(f"Unknown strategy: {s.strip()}")

        if not strategies:
            raise ValueError("No valid strategies provided")

        return list(set(strategies))  # Remove duplicates

    async def handle_chat(self, message: Message, question: str) -> None:
        """
        Handle chat command.

        Args:
            message: Discord message
            question: User's question
        """
        if not question:
            await message.channel.send("⚠️ **MISSING QUESTION** ⚠️")
            return

        try:
            # Add thinking indicator
            thinking = await message.channel.send("🤔 **Thinking...**")

            # Get AI response
            response = await self.chat_client.chat(question)

            # Format response
            formatted_response = f"❓ **Question**: {question}\n\n📝 **Answer**: {response}"

            # Delete thinking message and send response
            await thinking.delete()
            await message.channel.send(formatted_response)
            logger.info(f"Processed chat question: {question[:50]}")

        except Exception as e:
            logger.error(f"Failed to process chat: {str(e)}", exc_info=True)
            await message.channel.send('⚠️ **FAILED TO PROCESS QUESTION** ⚠️')

    async def handle_listen(self, message: Message, args: str) -> None:
        """
        Handle listen command.

        Args:
            message: Discord message
            args: Command arguments
        """
        if not args:
            await message.channel.send("⚠️ **MISSING STRATEGY** ⚠️\nUse comma-separated values or 'all' for all strategies")
            return

        try:
            strategies = self._parse_strategies(args)
            await self._start_signal_listener(message, strategies)
        except ValueError as e:
            await message.channel.send(f"❓ **{str(e)}** ❓")

    async def handle_unlisten(self, message: Message, args: Optional[str] = None) -> None:
        """
        Handle unlisten command.

        Args:
            message: Discord message
            args: Optional command arguments
        """
        if not args:
            # Stop all strategies
            await self._stop_signal_listener(message)
        else:
            try:
                strategy = StrategyType(args.lower())
                await self._stop_signal_listener(message, strategy)
            except ValueError:
                await message.channel.send("❓ **UNKNOWN STRATEGY** ❓")

    async def handle_top(self, message: Message, args: str) -> None:
        """
        Handle top command.

        Args:
            message: Discord message
            args: Command arguments
        """
        if not args:
            await message.channel.send("⚠️ **MISSING ARGUMENT** ⚠️")
            return

        if args == 'winners':
            await self._display_top_coins(message, ascending=False)
        elif args == 'losers':
            await self._display_top_coins(message, ascending=True)
        else:
            await message.channel.send("❓ **UNKNOWN ARGUMENT** ❓")

    async def handle_clear(self, message: Message, args: str) -> None:
        """
        Handle clear command.

        Args:
            message: Discord message
            args: Command arguments
        """
        if not args:
            await message.channel.send("⚠️ **MISSING COUNT** ⚠️")
            return

        try:
            count = int(args)
            await self._clear_messages(message, count)
        except ValueError:
            await message.channel.send("❓ **INVALID COUNT** ❓")

    async def _start_signal_listener(self, message: Message, strategies: List[StrategyType]) -> None:
        """
        Start listening for trading signals.

        Args:
            message: Discord message
            strategies: List of strategies to listen for
        """
        try:
            if not self.price_handler:
                # Initialize price handler with first strategy
                self.price_handler = PriceHandler(message=message, bybit_client=self.bybit_client)

                # Add all strategies
                for strategy in strategies:
                    await self.price_handler.add_strategy(strategy)

                await self.price_handler.initialize()
                logger.info("Initialized price handler")

                # Subscribe to WebSocket updates if needed
                if self.bybit_ws_client is not None:
                    symbols = await self.bybit_client.get_usdt_instruments()
                    await self.bybit_ws_client.subscribe(
                        [f'kline.{DEFAULT_INTERVAL}.{symbol}' for symbol in symbols],
                        self.price_handler
                    )
                    logger.info(f"Subscribed to {len(symbols)} symbol candles")

                strategy_names = ', '.join(s.upper() for s in strategies)
                await message.channel.send(f'❗ **LISTENING FOR {strategy_names} SIGNALS** ❗')
            else:
                # Add new strategies
                new_strategies = []
                for strategy in strategies:
                    if strategy not in self.price_handler.active_strategies:
                        await self.price_handler.add_strategy(strategy)
                        new_strategies.append(strategy)

                if new_strategies:
                    strategy_names = ', '.join(s.upper() for s in new_strategies)
                    await message.channel.send(f'❗ **LISTENING FOR {strategy_names} SIGNALS** ❗')
                else:
                    await message.channel.send('🚫 **ALREADY LISTENING TO REQUESTED STRATEGIES** 🚫')

        except Exception as e:
            logger.error("Failed to start signal listener", exc_info=True)
            if self.price_handler and not self.price_handler.active_strategies:
                await self.price_handler.cleanup()
                self.price_handler = None
            await message.channel.send('⚠️ **FAILED TO START LISTENING** ⚠️')

    async def _stop_signal_listener(self, message: Message, strategy: Optional[StrategyType] = None) -> None:
        """
        Stop listening for trading signals.

        Args:
            message: Discord message
            strategy: Strategy to stop listening to, or None to stop all
        """
        if not self.price_handler:
            await message.channel.send("❗ **LISTEN FOR SIGNALS FIRST** ❗")
            return

        try:
            # If specific strategy requested
            if strategy:
                # Check if we're listening to this strategy
                if strategy not in self.price_handler.active_strategies:
                    await message.channel.send(f"❗ **LISTEN FOR {strategy.upper()} SIGNALS FIRST** ❗")
                    return

                # Remove specific strategy
                await self.price_handler.remove_strategy(strategy)
                await message.channel.send(f'⚪ **STOPPED {strategy.upper()} SIGNALS** ⚪')
                logger.info(f"Stopped {strategy.upper()} signals")

                # If no more strategies, cleanup
                if not self.price_handler.active_strategies:
                    if self.bybit_ws_client is not None:
                        symbols = await self.bybit_client.get_usdt_instruments()
                        await self.bybit_ws_client.unsubscribe(
                            [f'kline.{DEFAULT_INTERVAL}.{symbol}' for symbol in symbols]
                        )
                    await self.price_handler.cleanup()
                    self.price_handler = None
            else:
                # Stop all strategies
                await self.price_handler.remove_strategy(None)
                if self.bybit_ws_client is not None:
                    symbols = await self.bybit_client.get_usdt_instruments()
                    await self.bybit_ws_client.unsubscribe(
                        [f'kline.{DEFAULT_INTERVAL}.{symbol}' for symbol in symbols]
                    )
                await self.price_handler.cleanup()
                self.price_handler = None
                await message.channel.send('⚪ **STOPPED ALL SIGNALS** ⚪')
                logger.info("Stopped all signal listening")

        except Exception as e:
            logger.error("Failed to stop signal listener", exc_info=True)
            await message.channel.send('⚠️ **FAILED TO STOP SIGNALS** ⚠️')

    async def _display_top_coins(self, message: Message, ascending: bool) -> None:
        """Display top performing or worst performing coins."""
        try:
            # Get ticker data from Bybit API
            tickers = await self.bybit_client.get_tickers()

            # Sort by 24h price change percentage
            sorted_tickers = sorted(
                tickers,
                key=lambda x: float(x['price_24h_pcnt']),
                reverse=not ascending
            )

            # Take top 5 results
            top_tickers = sorted_tickers[:5]

            # Create response message
            response = '👎 WORST COINS TODAY 👎\n\n' if ascending else '👍 BEST COINS TODAY 👍\n\n'

            for ticker in top_tickers:
                pct = float(ticker['price_24h_pcnt']) * 100
                symbol = ticker['symbol']
                sign = "+" if pct > 0 else ""
                response += f'**{sign}{pct:.2f}%** {symbol}\n'

            await message.channel.send(response)
            logger.info(f"Displayed {'worst' if ascending else 'best'} performing coins")

        except Exception as e:
            logger.error("Failed to display top coins", exc_info=True)
            await message.channel.send('⚠️ **FAILED TO DISPLAY TOP COINS** ⚠️')

    async def _clear_messages(self, message: Message, count: int) -> None:
        """Clear specified number of messages from the channel."""
        if count < 1:
            await message.channel.send('❓ **COUNT MUST BE POSITIVE** ❓')
            return

        try:
            deleted = 0
            async for msg in message.channel.history(limit=count):
                if not msg.pinned:
                    await msg.delete()
                    deleted += 1
            logger.info(f"Cleared {deleted} messages")

        except Exception as e:
            logger.error("Failed to clear messages", exc_info=True)
            await message.channel.send('⚠️ **FAILED TO CLEAR MESSAGES** ⚠️')
