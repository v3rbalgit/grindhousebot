from dataclasses import dataclass
from typing import Protocol, TypeAlias
from dataclasses import dataclass
import pandas as pd
import pandas_ta as ta
import numpy as np


Dataframes: TypeAlias = dict[str,pd.DataFrame]

@dataclass(slots=True)
class PriceData:
  """
    Represents price data of a symbol.

  """
  open: float
  close: float
  high: float
  low: float
  timestamp: int


@dataclass(slots=True)
class Signal:
  """
    Represents signal data of a symbol.

  """
  type: str
  value: float


class Strategy(Protocol):
  """
    Base class for generating signals from real-time price data.
    Any inheriting classes can use following attributes and methods.
    They must implement their own `process` method.

    Attributes
    ----------
    `dataframes` : Dataframes
        Keeps track of price data corresponding to each symbol up to an amount defined by `window`
    `interval` : int
        Time interval to group price data by (in minutes)
    `window` : int
        Maximum amount of intervals to store in memory

    Methods
    -------
    watch(prices: dict[str, PriceData])
        Transforms PriceData objects representing price data corresponding to a symbol into dictionary of signals corresponding to a symbol
    process()
        Processes dataframe of running price data and returns dictionary of buy/sell signals for each symbol.

  """
  dataframes: Dataframes = {}
  interval: int
  window: int


  def __init__(self, /, interval: int, window: int) -> None:
    """
      Strategy class is not meant to be directly created, but inherited.

    """
    self.interval = interval
    self.window = window


  def watch(self, prices: dict[str, PriceData]) -> dict[str, Signal]:
    """
      Takes in final price data of all symbols in given interval, adds them into a dataframe, processes the dataframe and returns dictionary of signals corresponding to relevant symbols.

      Parameters
      ----------
      `prices` : dict[str, PriceData]
          Dictionary of final price data of all symbols in an interval, e.g. { 'BTCUSDT': PriceData(open, high, low, close, timestamp), ... }

      Returns
      -------
      dict[str, Signal]
          Dictionary of signals corresponding to the relevant symbol, e.g. { 'BTCUSDT': { 'type': 'buy', 'value': 13.421 } }

    """
    if not len(self.dataframes.keys()):
      for symbol, price in prices.items():
        self.dataframes[symbol] = pd.DataFrame({'open': price.open, 'high': price.high, 'low': price.low, 'close': price.close}, index=[price.timestamp], dtype=np.float64)
    else:
      if self.__max_length() == self.window:
        for symbol, price in prices.items():
          self.dataframes[symbol].drop([self.dataframes[symbol].index.values[0]], inplace=True)
          self.dataframes[symbol] = pd.concat([self.dataframes[symbol], pd.DataFrame({'open': price.open, 'high': price.high, 'low': price.low, 'close': price.close}, index=[price.timestamp])])
      else:
        for symbol, price in prices.items():
          if self.dataframes.get(symbol) is None:
            self.dataframes[symbol] = pd.DataFrame({'open': price.open, 'high': price.high, 'low': price.low, 'close': price.close}, index=[price.timestamp], dtype=np.float64)
            continue

          self.dataframes[symbol] = pd.concat([self.dataframes[symbol], pd.DataFrame({'open': price.open, 'high': price.high, 'low': price.low, 'close': price.close}, index=[price.timestamp])])

    return self.process()


  def __max_length(self) -> int:
    length = 0

    for prices in self.dataframes.values():
      if len(prices.axes[0]) > length:
        length = len(prices.axes[0])

    return length


  def process(self) -> dict[str, Signal]:
    ...


class RSIStrategy(Strategy):
  """
    Class for signalling buy/sell RSI values based on price data.

    Attributes
    ----------
    `sell` : int
        Defines a top signal to sell
    `buy` : int
        Defines a bottom signal to buy

    Methods
    -------
    process()
        Processes dataframe of running price data and returns dictionary of buy/sell signals for each symbol

  """
  sell: int
  buy: int


  def __init__(self, *, sell: int = 85, buy: int = 15, interval: int = 5, window: int = 20) -> None:
    """
      RSIStrategy objects provide buy/sell signals based on the Relative Strength Index.

      Parameters
      ----------
      `sell` : int
          Sell signal threshold for the RSI value (between 1 and 99)
      `buy` : int
          Buy signal threshold for the RSI value (between 1 and 99)
      `interval` : int
          Time interval to group price data by (in minutes)
      `window` : int
          Maximum amount of intervals to store in memory

    """
    self.sell = sell if sell > buy else buy
    self.buy = buy if buy < sell else sell
    super().__init__(interval, window)


  def process(self) -> dict[str, Signal]:
    """
      Processes dataframe of running price data and returns dictionary of buy/sell signals for each symbol.

      Returns
      -------
      dict[str, Signal]
          Dictionary of signals corresponding to the relevant symbol, e.g. { 'BTCUSDT': Signal('buy', 13.421), ... }

    """
    signals = {}

    for symbol, prices in self.dataframes.items():
      prices.ta.rsi(close='close', append=True)

      if 'RSI_14' in prices.columns:
        prices.fillna(50, inplace=True)
        rsi = prices['RSI_14'].iloc[-1]

        if rsi > self.sell and rsi != 100:
           signals[symbol] = Signal('sell', rsi)

        if rsi < self.buy and rsi != 0:
           signals[symbol] = Signal('buy', rsi)

    return signals
