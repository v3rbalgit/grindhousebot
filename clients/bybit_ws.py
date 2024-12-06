import asyncio
import json
from typing import Optional, Union, List, Dict, Any
from websockets.asyncio.client import connect
from websockets.asyncio.connection import Connection
from utils.logger import logger


class BybitWsClient:
    """
    WebSocket client for Bybit's public WebSocket API.

    Handles connection management, message processing, and subscription handling
    for real-time market data streams.
    """

    def __init__(self) -> None:
        """Initialize WebSocket client with default configuration."""
        self.url = 'wss://stream.bybit.com/v5/public/linear'
        self.websocket: Optional[Connection] = None
        self.subscriptions: List[Dict[str, Any]] = []
        self._running = True
        self._process_task: Optional[asyncio.Task] = None
        self._max_queue_size = 1000
        logger.info("Initialized WebSocket client")

    async def connect(self) -> None:
        """
        Connect to WebSocket server and start message processing.

        Creates an asyncio task that maintains the connection and handles reconnection.
        """
        self._running = True
        self._process_task = asyncio.create_task(self._process_messages())
        logger.info("Started WebSocket message processing")

    async def _process_messages(self) -> None:
        """
        Process incoming WebSocket messages with automatic reconnection.

        Maintains the WebSocket connection, handles subscriptions, and processes
        incoming messages. Automatically reconnects on connection loss.
        """
        while self._running:
            try:
                async with connect(
                    self.url,
                    ping_interval=20,
                    ping_timeout=20,
                    close_timeout=10,
                    max_queue=self._max_queue_size,
                    logger=logger
                ) as websocket:
                    self.websocket = websocket
                    logger.info(f"Connected to {self.url}")

                    # Process messages
                    async for message in websocket:
                        if not self._running:
                            break

                        try:
                            data = json.loads(message)

                            # Handle heartbeat/status messages
                            if 'success' in data:
                                continue

                            # Process market data messages
                            if 'topic' in data and 'data' in data:
                                topic = data['topic']
                                symbol = topic.split('.')[-1]

                                for sub in self.subscriptions:
                                    if topic in sub['topics']:
                                        asyncio.create_task(sub['handler'].handle_price_update(data['data'], symbol))

                        except json.JSONDecodeError:
                            logger.warning(f"Invalid JSON received: {message}")
                            continue
                        except Exception as e:
                            logger.error(f"Error processing message: {e}", exc_info=True)
                            continue

            except Exception as e:
                if self._running:
                    logger.error(f"WebSocket connection error: {e}", exc_info=True)
                    await asyncio.sleep(5)  # Simple retry delay
                else:
                    break

        logger.info("WebSocket processing stopped")

    async def subscribe(self, topics: Union[str, List[str]], handler) -> None:
        """
        Subscribe to market data topics and set up message handler.

        Args:
            topics: Single topic string or list of topics (e.g., 'kline.5.BTCUSDT')
            handler: PriceHandler instance for processing received messages
        """
        if isinstance(topics, str):
            topics = [topics]

        self.subscriptions.append({
            'topics': topics,
            'handler': handler
        })

        # If we have an active connection, send subscription and hope for the best
        if self.websocket:
            try:
                subscription_msg = {
                    'op': 'subscribe',
                    'args': topics
                }
                await self.websocket.send(json.dumps(subscription_msg))
                logger.info(f"Sent subscription request for {len(topics)} topics")

            except Exception as e:
                logger.error(f"Error during subscription: {e}")


    async def unsubscribe(self, topics: Union[str, List[str]]) -> None:
        """
        Unsubscribe from market data topics.

        Args:
            topics: Single topic string or list of topics to unsubscribe from
        """
        if isinstance(topics, str):
            topics = [topics]

        # Remove subscription
        self.subscriptions = [
            sub for sub in self.subscriptions
            if not set(sub['topics']) == set(topics)
        ]

        # If connected, send unsubscribe message
        if self.websocket:
            try:
                await self.websocket.send(json.dumps({
                    'op': 'unsubscribe',
                    'args': topics
                }))
                logger.info(f"Sent unsubscribe request for {len(topics)} topics")
            except Exception as e:
                logger.error(f"Error during unsubscribe: {e}")

    async def disconnect(self) -> None:
        """
        Disconnect from WebSocket server and clean up resources.

        Cancels message processing task and closes the connection.
        """
        self._running = False
        if self._process_task:
            self._process_task.cancel()
            try:
                await self._process_task
            except asyncio.CancelledError:
                pass

        if self.websocket:
            await self.websocket.close()
            self.websocket = None

        logger.info("WebSocket client disconnected")