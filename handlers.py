from typing import Any, Optional, Protocol, TypeAlias
from pybit.usdt_perpetual import HTTP
from discord import Message

import numpy as np
import pandas as pd

from strategies import PriceData, Strategy
import requests.exceptions


BybitPosition: TypeAlias = dict[str,Any]

RawData: TypeAlias = list[dict[str, Any]]


class Handler(Protocol):
  """
    Base class for handling data from Bybit websocket client.
    Any inheriting classes must implement these attributes and methods:

    Attributes
    ----------
    message : Message
        Message from Discord channel. Has `channel` attribute needed for sending back a response
    client : HTTP
        Bybit HTTP client used for querying inital data

    Methods
    -------
    build_response(*args, **kwargs)
        Formats the response to Discord channel
    handle(payload, topic)
        Processes the incoming data

    """

  message: Message
  client: HTTP

  def __init__(self, message: Message, http_client: HTTP) -> None:
    """
      Handler class is not meant to be directly created, but inherited.

    """
    self.message = message
    self.client = http_client

  def build_response(self, *args, **kwargs) -> str:
    ...

  def handle(self, payload: list[dict[str, Any]], topic: str) -> None:
    ...


class PositionHandler(Handler):
  """
    Class for handling position data from Bybit websocket client.

  """

  def __init__(self, message: Message, http_client: HTTP) -> None:
    """
      PositionHandler objects contain `handle` method for processing real-time position data from Bybit account
      and `build_response` method for displaying them in a Discord channel.

      Parameters
      ----------
      `message` : Message
          Message from Discord channel. Has `channel` attribute needed for sending back a response
      `client` : HTTP
          Bybit HTTP client used for querying inital data

    """
    self.message = message
    self.client = http_client
    self.key_list = ('symbol', 'size', 'side', 'position_value', 'entry_price', 'liq_price', 'stop_loss', 'take_profit', 'mode')
    self.positions = self.get_positions()
    self.symbols = [position['symbol'] for position in self.positions]


  def get_positions(self) -> list[BybitPosition]:
    """
      Gets data on existing positions from Bybit.

      Returns
      -------
      list[BybitPosition] :
          List of dictionaries containing `symbol`, `size`, `side`, `position_value`, `entry_price`, `liq_price`, `stop_loss`, `take_profit`, `mode`

    """
    try:
      return [{ key:value for (key, value) in position['data'].items() if key in self.key_list} for position in self.client.my_position()['result'] if position['data']['size'] != 0]  # <-
    except requests.exceptions.ConnectionError:  # fix for Docker
      return self.get_positions()


  def build_response(self, position: BybitPosition, action: Optional[str] = None) -> str:
    """
      Formats a response for sending to a Discord channel.

      Parameters
      ----------
      `position` : BybitPosition
          Dictionary containing `symbol`, `size`, `side`, `position_value`, `entry_price`, `liq_price`, `stop_loss`, `take_profit`, `mode`
      `action` : Optional[str]
          Value of either 'new position', 'position updated', 'position closed' or `None`


      Returns
      -------
      str :
          Formatted response

    """
    try:
      response = ''
      price = float(self.client.latest_information_for_symbol(symbol=position['symbol'])['result'][0]['last_price'])  # <-

      pnl = (position['entry_price'] * position['size']) - (price * position['size'])
      pnl = pnl * -1 if position['side'] == 'Buy' else pnl

      size = f":moneybag: Size: ${position['position_value']:.2f} ({position['size']} {position['symbol'].replace('USDT','')})\n"
      entry = f":arrow_right: Entry: ${position['entry_price']}\n"
      close = f":arrow_left: Close: ${price}\n"
      take_profit = f":dart: Take profit: ${position['take_profit']}\n" if position['take_profit'] else ''
      stop_loss = f":flag_white: Stop loss: ${position['stop_loss']}\n" if position['stop_loss'] else ''
      liq_price = f":skull_crossbones: Liq. price: ${position['liq_price']}"
      pnl_string = f"\n\n:scales: PnL: ${pnl:.2f} {':white_check_mark:' if pnl >= 0 else ':x:'}"

      response += f':bangbang: **{action.upper()}** :bangbang:\n\n' if action else ''
      response += f":chart_with_upwards_trend: LONG {position['symbol']}\n\n" if position['side'] == 'Buy' else f":chart_with_downwards_trend: SHORT {position['symbol']}\n\n"

      match action:
        case 'new position':
          response += size + entry + take_profit + stop_loss + liq_price
        case 'position updated':
          response += size + entry + take_profit + stop_loss + liq_price
        case 'position closed':
          response += entry + close + pnl_string
        case _:
          response += size + entry + take_profit + stop_loss + liq_price + pnl_string

      return response
    except requests.exceptions.ConnectionError:  # fix for Docker
      return self.build_response(position, action)


  async def handle(self, payload: RawData, topic: str) -> None:
    """
      Processes incoming websocket data from Bybit with changes in positions
      and sends a response to a Discord channel.

      Parameters:
      -----------
      `payload` : RawData
          Dictionary containing raw position data
      `topic` : str
          Topic of the websocket data

    """
    response: str = ''

    positions: list[BybitPosition] = [{ key:value for (key, value) in message.items() if key in self.key_list} for message in payload]

    match positions[0].get('mode'):  # Bybit API returns one or two items in list depending on mode
      case 'MergedSingle':
        position = positions[0]

        if position['symbol'] not in self.symbols and position['side'] != 'None':
          self.positions.append(position)
          self.symbols.append(position['symbol'])
          response = self.build_response(position, 'new position')
          await self.message.channel.send(response)
          return

        index = next((i for (i, p) in enumerate(self.positions) if p['symbol'] == position['symbol']), None)

        if index is not None:  # index can have value 0
          if position['side'] == 'None':
            self.symbols.pop(index)
            response = self.build_response(self.positions.pop(index), 'position closed')
            await self.message.channel.send(response)
            return

          if all((position.get(k) == v for k, v in self.positions[index].items())): return  # check if any relevant data actually changed

          self.positions[index] = position
          response = self.build_response(position, 'position updated')
          await self.message.channel.send(response)

      case 'BothSide':
        if positions[0]['symbol'] not in self.symbols:
          position = positions[0] if positions[0].get('size') != 0 else positions[1] if positions[1].get('size') != 0 else None
          if position:
            self.positions.append(position)
            self.symbols.append(position['symbol'])
            response = self.build_response(position, 'new position')
            await self.message.channel.send(response)


        index = next((i for (i, p) in enumerate(self.positions) if p['symbol'] == positions[0]['symbol']), None)

        if index is not None:  # index can have value 0
          position = list(filter(lambda p: p.get('side') == self.positions[index].get('side'), positions))[0]

          if position['size'] == 0:
            self.symbols.pop(index)
            response = self.build_response(self.positions.pop(index), 'position closed')
            await self.message.channel.send(response)
            return

          if all((position.get(k) == v for k, v in self.positions[index].items())): return  # check if any relevant data actually changed

          self.positions[index] = position
          response = self.build_response(position, 'position updated')
          await self.message.channel.send(response)


class PriceHandler(Handler):
  """
    Class for handling price data from Bybit websocket client.

  """

  def __init__(self, message: Message, http_client: HTTP, *, strategy: Strategy):
    """
      PriceHandler objects contain `handle` method to process real-time price data of symbols traded via the USDT perpetual contract on Bybit
      in order to generate buy/sell signals and `build_response` method to display them in a Discord channel.

      Parameters
      ----------
      `message` : Message
          Message from Discord channel. Has `channel` attribute needed for sending back a response
      `client` : HTTP
          Bybit HTTP client used for querying inital data
      `strategy` : Strategy
          Strategy used to form buying or selling signals based on realtime prices

    """
    self.message = message
    self.client = http_client
    self.symbols = self.get_symbols()
    self.strategy = strategy
    self.daily_pct_changes = {}  # f.e. { 'BTCUSDT': -0.01254,... }
    self.running_intervals = {}  # keeps track of price data within current time interval
    self.signals = {}  # updates with relevant signals
    self.current_timestamp = 0
    self.current_interval = int((10 ** 6) * 60 * self.strategy.interval)  # convert interval (in minutes) to nanoseconds (Bybit timestamp format)


  def get_symbols(self) -> list[str]:
    """
    Gets all symbols traded via the USDT perpetual contract on Bybit.

    Returns
    -------
    list[str] :
        List of all USDT symbols traded via the USDT perpetual contract

    """
    try:
      response: dict[str, Any] = self.client.query_symbol()  # <-
      symbols: list[str] = []

      if response.get('result'):
        symbols.extend([result['name'] for result in response['result'] if result['name'].endswith('USDT')])

      return symbols
    except requests.exceptions.ConnectionError:  # fix for Docker
      return self.get_symbols()


  def build_response(self, *, symbol: str, signal: dict[str, Any]) -> str:
    """
      Formats a response for sending to a Discord channel.

      Parameters
      ----------
      `symbol` : str
          Symbol name corresponding to the signal
      `signal` : dict[str, Any]
          Signal data for the last interval


      Returns
      -------
      str :
          Formatted response

    """
    if signal['type'] == 'sell':
      return f':chart_with_upwards_trend: **{symbol} IS PUMPING** (RSI: {signal["value"]:.2f}) :chart_with_upwards_trend:'

    if signal['type'] == 'buy':
      return f':chart_with_downwards_trend: **{symbol} IS DUMPING** (RSI: {signal["value"]:.2f}) :chart_with_downwards_trend:'

    return ''


  async def handle(self, payload: RawData, topic: str) -> None:
    """
      Processes real-time price data of a given symbol
      and sends a response to a Discord channel.

      Parameters
      ----------
      `payload` : RawData
          Dictionary containing current price data of the subscribed symbol and interval
      `topic` : str
          Topic of the websocket data. Contains symbol name and subscribed interval, e.g. 'candle.D.BTCUSDT'

    """
    response: str = ''
    symbol: str = topic.split('.')[-1]
    data: dict[str, Any] = payload[0]

    daily = pd.Series([data['open'], data['close']], dtype=np.float64)
    daily_log_returns = np.log(1 + daily.pct_change())
    self.daily_pct_changes[symbol] = daily_log_returns.iloc[-1]  # type: ignore

    if self.current_timestamp == 0:
      self.current_timestamp = data['timestamp']

    if not self.running_intervals.get(symbol):
      self.running_intervals[symbol] = PriceData(data['close'], data['close'], data['close'], data['close'], self.current_timestamp)
      return

    if (data['timestamp'] - self.current_timestamp) < self.current_interval:
      self.running_intervals[symbol].close = data['close']
      self.running_intervals[symbol].high = data['close'] if data['close'] > self.running_intervals[symbol].high else self.running_intervals[symbol].high
      self.running_intervals[symbol].low = data['close'] if data['close'] < self.running_intervals[symbol].low else self.running_intervals[symbol].low
      return

    signals = self.strategy.watch(self.running_intervals)

    for symbol in self.symbols:
      if signals.get(symbol) is None and self.signals.get(symbol) is not None:
        self.signals[symbol] = None

      if signals.get(symbol) is not None and self.signals.get(symbol) is None:
        self.signals[symbol] = signals[symbol]
        response = self.build_response(symbol=symbol, signal=signals[symbol])
        await self.message.channel.send(response)

    self.current_timestamp += self.current_interval
    self.running_intervals.clear()