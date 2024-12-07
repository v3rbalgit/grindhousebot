import aiohttp
from typing import Optional, Dict, Any
from os import getenv
from utils.logger import logger


class OpenRouterClient:
    """Async client for OpenRouter API."""

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize OpenRouter client.

        Args:
            api_key: OpenRouter API key (optional, defaults to env var)
        """
        self.api_key = api_key or getenv('OPENROUTER_API_KEY', '')
        self.base_url = "https://openrouter.ai/api/v1"

        # Model for chat
        self.chat_model = "google/gemini-flash-1.5-8b"

        # System prompt for chat
        self.chat_prompt = """You are GrindhouseBot's AI assistant, focused on cryptocurrency trading and technical analysis.

Bot Commands and Usage:
1. !listen <strategies> - Start monitoring trading signals
   - Use comma-separated values: !listen rsi,macd
   - Use 'all' for all strategies: !listen all
   - Available strategies:
     * RSI: Momentum-based signals with dynamic confidence
     * MACD: Trend-following signals with histogram analysis
     * Bollinger: Volatility-based signals with trend context
     * Ichimoku: Multi-factor signals with cloud dynamics

2. !unlisten [strategy] - Stop monitoring
   - Stop specific strategy: !unlisten rsi
   - Stop all: !unlisten

3. !interval <value> - Change analysis timeframe
   - Valid intervals:
     * Minutes: 1, 3, 5, 15, 30, 60, 120, 240, 360, 720
     * Daily: 'D' (1440 minutes)
     * Weekly: 'W' (10080 minutes)
     * Monthly: 'M' (43200 minutes)
   - Examples:
     * !interval 240  # 4-hour candles
     * !interval 60   # 1-hour candles
     * !interval D    # Daily candles

4. !top winners/losers - Show best/worst performing coins

5. !chat <question> - Ask about crypto or bot features

6. !clear <count> - Clear messages

Strategy Details:
- RSI Strategy:
  * Base signals on oversold (<30) and overbought (>70)
  * Confidence calculation:
    - 60%: Distance from threshold
    - 40%: Momentum (rate of change)
    - +10% bonus for extreme levels (<20 or >80)
  * Example: "RSI 25" shows oversold condition

- MACD Strategy:
  * Analyzes histogram patterns and divergence
  * Confidence calculation:
    - 50%: Divergence strength
    - 30%: Histogram strength vs recent moves
    - 20%: Trend consistency
  * Example: "MACD Div 1.20%" shows strong divergence

- Bollinger Strategy:
  * Signals based on band penetration and volatility
  * Confidence calculation:
    - 70%: Band penetration (volatility adjusted)
    - 30%: Distance from middle band (trend)
  * Example: "BB 2.50%" shows significant penetration

- Ichimoku Strategy:
  * Cloud-based signals with multiple confirmations
  * Confidence calculation:
    - 45%: Price position vs cloud
    - 35%: TK cross strength
    - 20%: Cloud thickness
  * Example: "Cloud 2.10%" shows strong cloud breakout

Signal Aggregation:
- Minimum confidence threshold: 0.3
- Strategy weights in combined signals:
  * RSI: 32% (strong reversal signals)
  * Ichimoku: 27% (multiple confirmations)
  * MACD: 23% (trend signals)
  * Bollinger: 18% (volatility signals)
- Agreement bonus:
  * Up to 20% for multiple confirming signals
  * Bonus scaled by average signal confidence
- All signals are educational, not financial advice

Keep your responses:
- Concise and direct
- Focused on bot usage and crypto
- Technical but understandable
- Under 200 words
- Support multiple languages when requested

When explaining commands:
- Use specific examples
- Mention required parameters
- Explain expected outcomes
- Note any prerequisites
"""

    async def _make_request(self,
                          messages: list,
                          model: str,
                          temperature: float = 0.7) -> Optional[str]:
        """
        Make a request to OpenRouter API.

        Args:
            messages: List of message dictionaries
            model: Model to use
            temperature: Response temperature (0.0-1.0)

        Returns:
            Generated text if successful, None otherwise
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "HTTP-Referer": "https://github.com/v3rbal/grindhousebot",
            "X-Title": "GrindhouseBot",
            "Content-Type": "application/json"
        }

        data = {
            "model": model,
            "messages": messages,
            "temperature": temperature
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=data
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"API request failed: {error_text}")
                        return None

                    result = await response.json()
                    return result['choices'][0]['message']['content']

        except Exception as e:
            logger.error(f"OpenRouter API error: {str(e)}")
            return None

    async def chat(self, user_message: str) -> str:
        """
        Send chat request to OpenRouter API using the chat model.

        Args:
            user_message: User's question or message

        Returns:
            AI response string

        Raises:
            Exception: If API request fails
        """
        messages = [
            {"role": "system", "content": self.chat_prompt},
            {"role": "user", "content": user_message}
        ]

        response = await self._make_request(
            messages=messages,
            model=self.chat_model,
            temperature=0.7  # Good balance for chat
        )

        if response is None:
            raise Exception("Failed to get chat response")

        return response

    async def check_models(self) -> Dict[str, Any]:
        """
        Get available models and their information.

        Returns:
            Dictionary of model information

        Raises:
            Exception: If API request fails
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "HTTP-Referer": "https://github.com/v3rbal/grindhousebot",
            "X-Title": "GrindhouseBot"
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.base_url}/models",
                    headers=headers
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        raise Exception(f"API request failed: {error_text}")

                    return await response.json()

        except Exception as e:
            logger.error(f"OpenRouter API error: {str(e)}")
            raise
