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
        self.model = "mistralai/mistral-7b-instruct"  # Good balance of performance and cost

        # System prompt to focus responses
        self.system_prompt = """You are GrindhouseBot's AI assistant, focused on cryptocurrency trading and technical analysis.

Bot Commands and Usage:
1. !listen <strategies> - Start monitoring trading signals
   - Use comma-separated values: !listen rsi,macd
   - Use 'all' for all strategies: !listen all
   - Available strategies:
     * RSI: Dynamic thresholds, trend confirmation
     * MACD: Enhanced crossover detection
     * Bollinger Bands: Squeeze detection
     * Ichimoku Cloud: Crypto-optimized (20/60/120/30)
     * Harmonic Patterns: Multiple pattern types
     * Volume Profile: Support/resistance levels

2. !unlisten [strategy] - Stop monitoring
   - Stop specific strategy: !unlisten rsi
   - Stop all: !unlisten

3. !top winners/losers - Show best/worst performing coins

4. !chat <question> - Ask about crypto or bot features

5. !clear <count> - Clear messages

Strategy Details:
- RSI Strategy: Uses dynamic thresholds that adapt to volatility, requires 15 candles
- MACD Strategy: Enhanced crossovers with trend confirmation, needs 27 candles
- Bollinger Bands: Detects squeezes and breakouts, needs 20 candles
- Ichimoku Cloud: Optimized for crypto with 20/60/120/30 settings, needs 120 candles
- Harmonic Patterns: Finds Gartley, Butterfly, Bat, Crab patterns, needs 30 candles
- Volume Profile: Analyzes volume distribution, needs 50 candles

Signal Generation:
- Each strategy uses multiple confirmations:
  * Trend analysis
  * Volume confirmation
  * Pattern recognition
  * Dynamic thresholds
- Signals include confidence scores
- All signals are educational, not financial advice

Keep your responses:
- Concise and direct
- Focused on bot usage and crypto
- Technical but understandable
- Under 200 words

When explaining commands:
- Use specific examples
- Mention required parameters
- Explain expected outcomes
- Note any prerequisites

Always include a disclaimer for any market-related responses."""

    async def chat(self, user_message: str) -> str:
        """
        Send chat request to OpenRouter API.

        Args:
            user_message: User's question or message

        Returns:
            AI response string

        Raises:
            Exception: If API request fails
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "HTTP-Referer": "https://github.com/v3rbal/grindhousebot",
            "X-Title": "GrindhouseBot",
            "Content-Type": "application/json"
        }

        data = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": user_message}
            ]
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
                        raise Exception(f"API request failed: {error_text}")

                    result = await response.json()
                    return result['choices'][0]['message']['content']

        except Exception as e:
            logger.error(f"OpenRouter API error: {str(e)}")
            raise

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
