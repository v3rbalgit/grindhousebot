from discord import Client, Message, Intents
from pybit.usdt_perpetual import HTTP
import asyncio
import pandas as pd
from enum import Enum, auto
from os import getenv
from dotenv import load_dotenv
from handlers import PositionHandler, PriceHandler
from strategies import RSIStrategy
from bybit_ws import BybitWsClient
from util import setup_logger

load_dotenv()


class Order(Enum):
  ASCENDING = auto()
  DESCENDING = auto()

# TODO: implement other strategies for PriceHandler
class GrindhouseBot(Client):
  """
    Discord bot that listens to latest position and price data from Bybit account and displays them in Discord channel.

  """
  bybit_ws_client_private: BybitWsClient
  bybit_ws_client_public: BybitWsClient
  position_handler: PositionHandler | None = None
  price_handler: PriceHandler | None = None

  bybit_client = HTTP(
    endpoint=getenv('url'),
    api_key=getenv('api_key'),
    api_secret=getenv('secret_key')
  )

  logger = setup_logger(__name__)


  async def setup_hook(self):
    self.bybit_ws_client_private = BybitWsClient(api_key=getenv("api_key",""), secret_key=getenv("secret_key",""))
    self.bybit_ws_client_public = BybitWsClient()
    await self.bybit_ws_client_private.connect()
    await self.bybit_ws_client_public.connect()


  async def on_ready(self):
    self.logger.info(f'Logged in as {self.user}')


  async def on_message(self, message: Message):
    message_list = message.content.split(' ')

    if message.author != self.user and message.content.startswith('!'):
      match message_list[0]:
        case '!active':
          await self.display_active_positions(message)

        case '!listen':
          if len(message_list) == 1:
            return await message.channel.send(":warning: **MISSING ARGUMENT** :warning:")

          match message_list[1]:
            case 'positions':
              await self.open_position_listener(message)
            case 'signals':
              await self.open_signal_listener(message)
            case _:
              await message.channel.send(":question: **UNKNOWN ARGUMENT** :question:")

        case '!unlisten':
          if len(message_list) == 1:
            return await message.channel.send(":warning: **MISSING ARGUMENT** :warning:")

          match message_list[1]:
            case 'positions':
              await self.close_position_listener(message)
            case 'signals':
              await self.close_signal_listener(message)
            case _:
              await message.channel.send(":question: **UNKNOWN ARGUMENT** :question:")

        case '!top':
          if len(message_list) == 1:
            return await message.channel.send(":warning: **MISSING ARGUMENT** :warning:")

          match message_list[1]:
            case 'winners':
              await self.display_top_coins(message, order=Order.DESCENDING)
            case 'losers':
              await self.display_top_coins(message, order=Order.ASCENDING)
            case _:
              await message.channel.send(":question: **UNKNOWN ARGUMENT** :question:")

        case '!clear':
          await self.clear_messages(message)

        case _:
          await message.channel.send(":question: **UNKNOWN COMMAND** :question:")


  async def display_active_positions(self, message: Message):
    position_handler = PositionHandler(message, self.bybit_client)

    if not position_handler.positions:
      await message.channel.send(":no_entry_sign: **NO OPEN POSITIONS** :no_entry_sign:")
      return

    tasks = [asyncio.create_task(message.channel.send(position_handler.build_response(position))) for position in position_handler.positions]
    asyncio.gather(*tasks)


  async def display_top_coins(self, message: Message, *, order: Order):
    if not self.price_handler:
      await message.channel.send(':warning: **LISTEN TO SIGNALS FIRST** :warning:')
      return

    response = ''

    daily_pct_changes = pd.DataFrame(self.price_handler.daily_pct_changes, index=['pct_change']).T

    match order:
      case Order.DESCENDING:
        daily_pct_changes.sort_values(by=['pct_change'], inplace=True, ascending=False)
        response += ':thumbsup: BEST COINS TODAY :thumbsup:\n\n'
      case Order.ASCENDING:
        daily_pct_changes.sort_values(by=['pct_change'], inplace=True)
        response += ':thumbsdown: WORST COINS TODAY :thumbsdown: \n\n'

    for index in daily_pct_changes.head().index:
      response += f'**{"+" if daily_pct_changes["pct_change"][index] >= 0 else ""}{daily_pct_changes["pct_change"][index] * 100:.2f}%** {index}\n'  # type: ignore
    await message.channel.send(response)


  async def clear_messages(self, message: Message):
    async for msg in message.channel.history(limit=200):
      if msg.pinned: continue
      await msg.delete()


  async def open_position_listener(self, message: Message):
    self.position_handler = PositionHandler(message, self.bybit_client)

    try:
      if self._is_listening('positions'):
        return await message.channel.send(':no_entry_sign: **ALREADY LISTENING** :no_entry_sign:')

      await message.channel.send(':exclamation: **LISTENING FOR POSITION CHANGES** :exclamation:')
      await self.bybit_ws_client_private.subscribe('position', self.position_handler)

    except ValueError as e:
      self.logger.error(e.args[0])


  async def close_position_listener(self, message: Message):
    if not self.position_handler: return

    try:
      if self._is_listening('positions'):
        await message.channel.send(':grey_exclamation: **LISTENING STOPPED** :grey_exclamation:')
        await self.bybit_ws_client_private.unsubscribe('position')

        if not len(self.bybit_ws_client_private.subscriptions):
          await self.bybit_ws_client_private.disconnect()
          self.position_handler = None

    except ValueError as e:
      self.logger.error(e.args[0])


  async def open_signal_listener(self, message: Message):
    self.price_handler = PriceHandler(message, self.bybit_client, strategy=RSIStrategy(interval=60), save_to_db=True)

    try:
      if self._is_listening('signals', symbols=self.price_handler.symbols):
        return await message.channel.send(':no_entry_sign: **ALREADY LISTENING** :no_entry_sign:')

      await message.channel.send(':exclamation: **LISTENING FOR PRICE SIGNALS** :exclamation:')
      await self.bybit_ws_client_public.subscribe([f'candle.D.{symbol}' for symbol in self.price_handler.symbols], self.price_handler)

    except ValueError as e:
      self.logger.error(e.args[0])


  async def close_signal_listener(self, message: Message):
    if not self.price_handler: return

    try:
      if self._is_listening('signals', symbols=self.price_handler.symbols):
        self.price_handler.daily_pct_changes.clear()
        await message.channel.send(':grey_exclamation: **LISTENING STOPPED** :grey_exclamation:')
        await self.bybit_ws_client_public.unsubscribe([f'candle.D.{symbol}' for symbol in self.price_handler.symbols])

        if not len(self.bybit_ws_client_public.subscriptions):
          await self.bybit_ws_client_public.disconnect()
          self.price_handler = None

    except ValueError as e:
      self.logger.error(e.args[0])


  def _is_listening(self, topic: str, *, symbols: list[str] | None = None) -> bool:
    if topic == 'positions':
      return True if 'position' in self.bybit_ws_client_private.subscriptions.keys() else False

    if topic == 'signals':
      if symbols:
        return all([True if f"candle.D.{symbol}" in self.bybit_ws_client_public.subscriptions.keys() else False for symbol in symbols])

    raise ValueError(f'Unknown topic: {topic}')


intents = Intents.default()
intents.members = True
intents.message_content = True

bot = GrindhouseBot(intents=intents)
bot.run(getenv('discord_bot_token',''))
