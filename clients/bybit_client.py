import aiohttp
import time
import asyncio
from typing import Dict, List, Optional, Any
from urllib.parse import urljoin
from utils.logger import logger
from utils.constants import validate_interval


class RateLimiter:
    """Token bucket rate limiter for Bybit API."""

    def __init__(self, rate: int = 600, per: int = 5):
        """
        Initialize rate limiter.

        Args:
            rate: Number of requests allowed per time window
            per: Time window in seconds
        """
        self.rate = rate
        self.per = per
        self.tokens = rate
        self.last_update = time.monotonic()
        self.lock = asyncio.Lock()

    async def acquire(self) -> None:
        """Acquire a token, waiting if necessary."""
        async with self.lock:
            while self.tokens <= 0:
                now = time.monotonic()
                time_passed = now - self.last_update
                self.tokens = min(
                    self.rate,
                    self.tokens + (time_passed * self.rate / self.per)
                )
                self.last_update = now

                if self.tokens <= 0:
                    await asyncio.sleep(self.per / self.rate)

            self.tokens -= 1


class BybitAPIError(Exception):
    """Custom exception for Bybit API errors."""
    pass


class BybitClient:
    """
    An async client for Bybit's HTTP API, focused on market data.
    Includes rate limiting to stay within API limits.
    """

    def __init__(self, testnet: bool = False) -> None:
        """
        Initialize the Bybit API client.

        Args:
            testnet: Whether to use testnet instead of mainnet
        """
        self.base_url = "https://api-testnet.bybit.com" if testnet else "https://api.bybit.com"
        self.rate_limiter = RateLimiter()
        self.session: Optional[aiohttp.ClientSession] = None
        logger.info(f"Initialized Bybit client {'testnet' if testnet else 'mainnet'}")

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        return self.session

    async def close(self) -> None:
        """Close the client session."""
        if self.session and not self.session.closed:
            await self.session.close()
            logger.info("Closed Bybit client session")

    async def _request(self, method: str, path: str, **kwargs) -> Dict[str, Any]:
        """
        Make a rate-limited HTTP request to the Bybit API.

        Args:
            method: HTTP method (GET, POST, etc.)
            path: API endpoint path
            **kwargs: Additional arguments for the request

        Returns:
            API response data

        Raises:
            BybitAPIError: If the API returns an error
        """
        # Acquire rate limit token
        await self.rate_limiter.acquire()

        url = urljoin(self.base_url, path)
        session = await self._get_session()

        try:
            async with session.request(method, url, **kwargs) as response:
                data = await response.json()

                if response.status != 200:
                    error_msg = f"HTTP {response.status}: {data.get('retMsg', 'Unknown error')}"
                    logger.error(f"API request failed: {error_msg}")
                    raise BybitAPIError(error_msg)

                if data.get("retCode") != 0:
                    error_msg = f"API Error {data.get('retCode')}: {data.get('retMsg', 'Unknown error')}"
                    logger.error(f"API request failed: {error_msg}")
                    raise BybitAPIError(error_msg)

                return data.get("result", {})

        except aiohttp.ClientError as e:
            error_msg = f"Request failed: {str(e)}"
            logger.error(error_msg)
            raise BybitAPIError(error_msg)


    async def get_usdt_instruments(self) -> List[str]:
        """
        Get all actively traded USDT perpetual instruments.

        Returns:
            List of symbol names (e.g., ["BTCUSDT", "ETHUSDT", ...])

        Raises:
            BybitAPIError: If the API request fails
        """
        path = "/v5/market/instruments-info"
        params = {
            "category": "linear",
            "status": "Trading"
        }

        data = await self._request("GET", path, params=params)
        symbols = [
            item["symbol"]
            for item in data.get("list", [])
            if item["symbol"].endswith("USDT")
        ]
        logger.info(f"Found {len(symbols)} USDT instruments")
        return symbols


    async def get_klines(self,
                        symbol: str,
                        interval: str,
                        limit: Optional[int] = None,
                        start_time: Optional[int] = None,
                        end_time: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get kline/candlestick data for a symbol.

        Args:
            symbol: Trading pair symbol (e.g., "BTCUSDT")
            interval: Kline interval in minutes or 'D'/'M'/'W'
            limit: Number of results (default: 200, max: 1000)
            start_time: Start timestamp in milliseconds
            end_time: End timestamp in milliseconds

        Returns:
            List of kline data

        Raises:
            BybitAPIError: If the API request fails
            ValueError: If interval is invalid
        """
        path = "/v5/market/kline"
        params = {
            "category": "linear",
            "symbol": symbol,
            "interval": validate_interval(interval)
        }

        if limit is not None:
            params["limit"] = str(min(max(1, limit), 1000))
        if start_time is not None:
            params["start"] = str(start_time)
        if end_time is not None:
            params["end"] = str(end_time)

        data = await self._request("GET", path, params=params)
        klines = [
            {
                "start_time": int(item[0]),
                "open": float(item[1]),
                "high": float(item[2]),
                "low": float(item[3]),
                "close": float(item[4]),
                "volume": float(item[5]),
                "turnover": float(item[6])
            }
            for item in data.get("list", [])
        ]
        logger.info(f"Retrieved {len(klines)} klines for {symbol}")
        return klines


    async def get_tickers(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get 24-hour ticker data for one or all symbols.

        Args:
            symbol: Optional symbol to get data for. If None, gets data for all symbols.

        Returns:
            List of ticker data

        Raises:
            BybitAPIError: If the API request fails
        """
        path = "/v5/market/tickers"
        params = {"category": "linear"}

        if symbol:
            params["symbol"] = symbol

        data = await self._request("GET", path, params=params)
        tickers = [
            {
                "symbol": item["symbol"],
                "last_price": float(item["lastPrice"]),
                "high_24h": float(item["highPrice24h"]),
                "low_24h": float(item["lowPrice24h"]),
                "volume_24h": float(item["volume24h"]),
                "turnover_24h": float(item["turnover24h"]),
                "price_24h_pcnt": float(item["price24hPcnt"])
            }
            for item in data.get("list", [])
            if item["symbol"].endswith("USDT")
        ]
        logger.info(f"Retrieved ticker data for {len(tickers)} symbols")
        return tickers
