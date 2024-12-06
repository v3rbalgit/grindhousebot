from discord import Client, Message, Intents
from typing import Optional
from os import getenv
from dotenv import load_dotenv

from clients import BybitClient, BybitWsClient
from handlers.command_handler import CommandHandler
from utils.logger import logger

load_dotenv()


class GrindhouseBot(Client):
    """Discord bot for cryptocurrency trading signals."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bybit_client = BybitClient(testnet=False)
        self.bybit_ws_client: Optional[BybitWsClient] = None
        self.command_handler: Optional[CommandHandler] = None
        logger.info("Initializing Grindhouse Bot")

    async def setup_hook(self) -> None:
        """Set up WebSocket connection and command handler."""
        self.bybit_ws_client = BybitWsClient()
        await self.bybit_ws_client.connect()
        self.command_handler = CommandHandler(self.bybit_client, self.bybit_ws_client)
        logger.info("WebSocket connection established")

    async def on_ready(self) -> None:
        """Log when bot is ready."""
        logger.info(f"Bot logged in as {self.user}")

    async def on_message(self, message: Message) -> None:
        """Handle incoming Discord messages."""
        if message.author == self.user or not message.content.startswith('!'):
            return

        command_parts = message.content.split(maxsplit=1)
        command = command_parts[0][1:]  # Remove ! prefix
        args = command_parts[1] if len(command_parts) > 1 else ""
        logger.info(f"Processing command from {message.author.display_name}: {message.content}")

        try:
            if self.command_handler is None:
                await message.channel.send("⚠️ **BOT NOT READY** ⚠️")
                return

            match command:
                case 'listen':
                    await self.command_handler.handle_listen(message, args)
                case 'unlisten':
                    await self.command_handler.handle_unlisten(message, args)
                case 'interval':
                    await self.command_handler.handle_interval(message, args)
                case 'top':
                    await self.command_handler.handle_top(message, args)
                case 'clear':
                    await self.command_handler.handle_clear(message, args)
                case 'chat':
                    await self.command_handler.handle_chat(message, args)
                case _:
                    await message.channel.send("❓ **UNKNOWN COMMAND** ❓")
                    logger.warning(f"Unknown command received: {command}")

        except Exception as e:
            logger.error(f"Error processing command '{command}': {str(e)}", exc_info=True)
            await message.channel.send("⚠️ **AN ERROR OCCURRED** ⚠️")


def main():
    """Start the Discord bot."""
    intents = Intents.default()
    intents.members = True
    intents.message_content = True

    bot = GrindhouseBot(intents=intents)
    bot.run(getenv('DISCORD_BOT_TOKEN', ''))


if __name__ == '__main__':
    main()
