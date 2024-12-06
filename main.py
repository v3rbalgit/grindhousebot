from discord import Client, Message, Intents
from typing import Optional
from enum import Enum, auto
from os import getenv
from dotenv import load_dotenv

from price_handler import PriceHandler
from clients import BybitClient, BybitWsClient
from utils.models import StrategyType
from utils.logger import logger
from utils.constants import DEFAULT_INTERVAL

load_dotenv()


class Order(Enum):
    ASCENDING = auto()
    DESCENDING = auto()


class GrindhouseBot(Client):
    """Discord bot for cryptocurrency trading signals."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bybit_client = BybitClient(testnet=False)
        self.bybit_ws_client: Optional[BybitWsClient] = None
        self.price_handler: Optional[PriceHandler] = None
        logger.info("Initializing Grindhouse Bot")


    async def setup_hook(self) -> None:
        """Set up WebSocket connection."""
        self.bybit_ws_client = BybitWsClient()
        await self.bybit_ws_client.connect()
        logger.info("WebSocket connection established")


    async def on_ready(self) -> None:
        """Log when bot is ready."""
        logger.info(f"Bot logged in as {self.user}")


    async def on_message(self, message: Message) -> None:
        """Handle incoming Discord messages."""
        if message.author == self.user or not message.content.startswith('!'):
            return

        command_parts = message.content.split()
        command = command_parts[0][1:]  # Remove ! prefix
        logger.info(f"Processing command from {message.author.display_name}: {message.content}")

        try:
            match command:
                case 'listen':
                    if len(command_parts) < 2:
                        await message.channel.send("⚠️ **MISSING STRATEGY** ⚠️")
                        return

                    try:
                        strategy = StrategyType(command_parts[1].lower())
                        await self._start_signal_listener(message, strategy)
                    except ValueError:
                        await message.channel.send("❓ **UNKNOWN STRATEGY** ❓")

                case 'unlisten':
                    if len(command_parts) < 2:
                        # Stop all strategies
                        await self._stop_signal_listener(message)
                    else:
                        try:
                            strategy = StrategyType(command_parts[1].lower())
                            await self._stop_signal_listener(message, strategy)
                        except ValueError:
                            await message.channel.send("❓ **UNKNOWN STRATEGY** ❓")

                case 'top':
                    if len(command_parts) < 2:
                        await message.channel.send("⚠️ **MISSING ARGUMENT** ⚠️")
                        return

                    if command_parts[1] == 'winners':
                        await self._display_top_coins(message, ascending=False)
                    elif command_parts[1] == 'losers':
                        await self._display_top_coins(message, ascending=True)
                    else:
                        await message.channel.send("❓ **UNKNOWN ARGUMENT** ❓")

                case 'clear':
                    if len(command_parts) < 2:
                        await message.channel.send("⚠️ **MISSING COUNT** ⚠️")
                        return

                    try:
                        count = int(command_parts[1])
                        await self._clear_messages(message, count)
                    except ValueError:
                        await message.channel.send("❓ **INVALID COUNT** ❓")

                case _:
                    await message.channel.send("❓ **UNKNOWN COMMAND** ❓")
                    logger.warning(f"Unknown command received: {command}")

        except Exception as e:
            logger.error(f"Error processing command '{command}': {str(e)}", exc_info=True)
            await message.channel.send("⚠️ **AN ERROR OCCURRED** ⚠️")


    async def _start_signal_listener(self, message: Message, strategy: StrategyType) -> None:
        """
        Start listening for trading signals.

        Args:
            message: Discord message
            strategy: Strategy to listen for
        """
        try:
            if not self.price_handler:
                # Initialize price handler
                self.price_handler = PriceHandler(message=message, bybit_client=self.bybit_client)
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
                await message.channel.send(f'❗ **LISTENING FOR {strategy.upper()} SIGNALS** ❗')
            else:
                # Check if already listening to this strategy
                if strategy in self.price_handler.active_strategies:
                    await message.channel.send(f'🚫 **ALREADY LISTENING TO {strategy.upper()}** 🚫')
                    return

                # Add strategy
                await self.price_handler.add_strategy(strategy)
                await message.channel.send(f'❗ **LISTENING FOR {strategy.upper()} SIGNALS** ❗')

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
                        await self.bybit_ws_client.subscribe(
                            [f'kline.{DEFAULT_INTERVAL}.{symbol}' for symbol in symbols],
                            self.price_handler
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


def main():
    """Start the Discord bot."""
    intents = Intents.default()
    intents.members = True
    intents.message_content = True

    bot = GrindhouseBot(intents=intents)
    bot.run(getenv('DISCORD_BOT_TOKEN', ''))


if __name__ == '__main__':
    main()
