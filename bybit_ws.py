import asyncio
import websockets.client as ws
import websockets.exceptions as ws_exc
import hmac
import json
import time
from uuid import uuid4
from enum import StrEnum
from util import setup_logger
from handlers import Handler


class Domain(StrEnum):
  """
    Connection domain.

  """
  PUBLIC = 'public',
  PRIVATE = 'private'


class BybitWsClient:
  """
    Class for connecting to a Bybit websocket server.

    Attributes
    ----------
    `websocket` : ws.WebSocketClientProtocol
        websockets instance representing Websocket connection

  """

  websocket: ws.WebSocketClientProtocol


  def __init__(self, *, api_key: str | None = None, secret_key: str | None = None) -> None:
    """
      Creates an asynchronous Bybit websocket client.
      If `api_key` and `secret_key` are provided, the client will connect via the private domain.
      If not, it will use public domain.

      Parameters
      ----------
      `api_key` : str | None
          Bybit account API key
      `secret_key` : str | None
          Bybit account secret key

    """
    self._credentials = {}
    self.subscriptions = []
    self.domain = Domain.PUBLIC

    if api_key and secret_key:
      self.domain = Domain.PRIVATE
      self._credentials['api_key'] = api_key
      self._credentials['secret_key'] = secret_key

    self.url = f'wss://stream.bybit.com/realtime_{self.domain.value}'
    self._logger = setup_logger(uuid4().hex)
    self._stream_task = None
    self._retries = 0


  async def connect(self) -> None:
    """
      Connects the websocket client to Bybit and authenticates if necessary.

    """
    try:
      self.websocket = await ws.connect(self.url)
      self._logger.info(f'Connected to {self.url}')
      self._retries = 0

      if self.domain == Domain.PRIVATE:
        expires = time.time_ns() + 5000

        signature = str(hmac.new(
            bytes(self._credentials['secret_key'], 'utf-8'),
            bytes(f'GET/realtime{expires}', 'utf-8'), digestmod='sha256'
        ).hexdigest())

        await self.websocket.send(
          json.dumps({ 'op': 'auth', 'args': [self._credentials['api_key'], expires, signature]})
        )
        response = await self.websocket.recv()

        self._logger.info('Successfully authenticated') if json.loads(response).get('success') else self._logger.warning('Authentication failed!')

      if self.subscriptions:
        await self._resubscribe()

    except ws_exc.InvalidURI:
      self._logger.error(f'Invalid server url {self.url}')

    except asyncio.TimeoutError:
      self._logger.error('Connection timed out. Retrying in 5 seconds...')

      await asyncio.sleep(5.0)

      if self._retries < 10:
        self._retries += 1
        await self.connect()
        return

      try:
        await self.disconnect()
      except ws_exc.ConnectionClosedError:
        self._logger.critical(f'Could not connect to {self.url} after 10 retries. Session closed.')


  async def disconnect(self) -> None:
    """
      Disconnects the websocket client from Bybit.

    """
    try:
      if not self.websocket.closed:
        await self.websocket.close()
    except ws_exc.ConnectionClosed:
      self._logger.info(f'Disconnected from {self.url}')


  async def subscribe(self, topics: str | list[str], handler: Handler) -> None:
    """
      Subscribes to topics on the Bybit API and fires the `handle` method on handler on every message.
      For full list of topics consult Bybit API documentation.

      Parameters
      ----------
      `topics` : str | list[str]
          Topic or list of topics to subscribe to (found in the Bybit API documentation)
      `handler` :
          Handler object to call `handle` method on every message in the subscribed topics

    """
    if isinstance(topics, str):
      topics = [topics]

    await self._prepare_sub('subscribe', topics)

    self.subscriptions.append({
      'topics': topics,
      'handler': handler
    })

    self._logger.info(f'Subscribed to {",".join(topics)}')

    self._stream_task = asyncio.create_task(self._stream())
    await self._stream_task


  async def unsubscribe(self, topics: str | list[str]) -> None:
    """
      Unsubscribes from topics on the Bybit API. For full list of topics consult Bybit API documentation.

      Parameters
      ----------
      `topics` : str | list[str]
          Topic or list of topics to unsubscribe from (found in the Bybit API documentation)

    """
    if isinstance(topics, str):
      topics = [topics]

    await self._prepare_sub('unsubscribe', topics)

    for i, sub in enumerate(self.subscriptions):
      if set(sub['topics']) == set(topics):
        self.subscriptions.pop(i)

    self._logger.info(f'Unsubscribed from {",".join(topics)}')

    if self.subscriptions:
      self._stream_task = asyncio.create_task(self._stream())
      asyncio.gather(self._stream_task)


  async def _resubscribe(self) -> None:
    tasks = []

    for sub in self.subscriptions:
      tasks.append(self.subscribe(sub['topics'], sub['handler']))

    asyncio.gather(*tasks)


  async def _prepare_sub(self, action: str, topics: str | list[str]) -> None:
    if self.websocket.closed:
      await self.connect()

    if self._stream_task:
      self._stream_task.cancel()

      try:
        await self._stream_task

      except asyncio.CancelledError:
        self._stream_task = None

    await self.websocket.send(json.dumps({ 'op': action, 'args': topics }))
    response = await self.websocket.recv()

    if json.loads(response).get('success') is False:
      raise ValueError(f'{action.capitalize()} failed: {json.loads(response).get("ret_msg")}')


  async def _stream(self) -> None:
    try:
      async for message in self.websocket:
        payload = json.loads(message)

        index = next((i for (i, s) in enumerate(self.subscriptions) if payload.get('topic') in s['topics']), None)

        if index is not None:
          asyncio.create_task(self.subscriptions[index]['handler'].handle(payload['data'], payload['topic']))

    except ws_exc.ConnectionClosedError:
      self._logger.error(f'Disconnected from {self.url}. Retrying...')
      await self.connect()
