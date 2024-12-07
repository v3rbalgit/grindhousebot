# GrindhouseBot 🤖

A powerful Discord bot for cryptocurrency trading signals and real-time market monitoring using the Bybit exchange. The bot provides automated technical analysis signals, market insights, and AI-powered chat assistance directly in your Discord channel.

## Features 🌟

- Real-time trading signals using multiple technical analysis strategies
- AI-enhanced signal analysis
- Dynamic market analysis with adaptive thresholds
- Live monitoring of USDT perpetual contracts
- Market performance tracking with top gainers and losers
- Multilingual AI chat assistance
- Efficient in-memory price data management
- Docker support for easy deployment
- Extensible strategy system with factory pattern
- Adjustable time intervals for analysis
- Multi-strategy signal monitoring
- Combined confidence scoring system

## Signalling Strategies 📈

### RSI Strategy
- Oversold/Overbought detection
- Confidence based on RSI extremes
- RSI < 30: Buy signal (stronger as RSI decreases)
- RSI > 70: Sell signal (stronger as RSI increases)

### MACD Strategy
- Divergence-based signals
- Uses 5-period average divergence
- Crossover confirmation required
- Confidence based on divergence strength

### Bollinger Bands Strategy
- Band penetration signals
- Confidence based on penetration depth
- Normalized by band width
- Adapts to market volatility

### Ichimoku Strategy
- Cloud position signals
- TK cross confirmation
- Weighted confidence calculation:
  * 40%: Distance from cloud
  * 30%: TK cross strength
  * 30%: Cloud thickness

## Signal Confidence

Signals combine multiple factors:
1. Individual strategy confidence (0.0-1.0)
2. Strategy weights:
   - RSI: 32% (strong reversal signals)
   - Ichimoku: 27% (multiple confirmations)
   - MACD: 23% (trend signals)
   - Bollinger: 18% (volatility signals)

### Strategy-Specific Confidence Scoring

Each strategy uses optimized confidence calculations:

#### Bollinger Bands
- Base confidence from band penetration depth
- Adjusts for current volatility using band width
- Considers distance from middle band for trend context
- Weighted scoring: 70% band penetration + 30% trend context

#### RSI
- Base confidence from distance to extremes
- Includes momentum (rate of change) consideration
- Bonus confidence for extreme levels (RSI < 20 or > 80)
- Weighted scoring: 60% RSI level + 40% momentum, with up to 10% extreme bonus

#### MACD
- Base confidence from divergence strength
- Considers histogram strength vs recent movements
- Includes trend consistency factor
- Weighted scoring: 50% divergence + 30% histogram strength + 20% trend consistency

#### Ichimoku
- Measures cloud and TK cross relative to recent price range
- Considers cloud thickness for trend strength
- Weighted scoring: 45% price position + 35% TK cross strength + 20% cloud strength

### Signal Aggregation

The signal handler implements several optimizations for efficient signal processing:

1. Minimum Confidence Threshold
   - Signals below 0.3 confidence are filtered out
   - Reduces noise and improves signal quality

2. Agreement Bonus
   - Up to 20% bonus for multiple confirming signals
   - Bonus scaled by average confidence of agreeing signals
   - Rewards strong consensus across strategies

3. Dynamic Weight Adjustment
   - Base weights adjusted based on signal strength
   - Normalized to maintain consistent scaling
   - Prioritizes strongest signals in current conditions

[Rest of the README content remains the same...]

## Performance Optimizations 🚀

### Technical Indicators
- Uses pandas_ta for efficient indicator calculations
  * Optimized with Cython for high performance
  * Efficient memory usage for rolling windows
  * Vectorized operations for speed

### Signal Processing
- Numpy-based confidence calculations
- Efficient signal aggregation using vectorized operations
- Pre-calculated lookup tables for weights and templates
- Optimized string formatting for Discord messages

### Memory Management
- Efficient DataFrame management
- Smart window sizes for each strategy
- Minimal data copying in signal processing
- Optimized message batching for Discord

## Installation 🚀

### Standard Installation
1. Clone the repository
2. Create a virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # Linux/Mac
   # or
   .venv\Scripts\activate  # Windows
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   pip install -U git+https://github.com/twopirllc/pandas-ta.git@development
   ```
4. Create a `.env` file with your credentials:
   ```
   DISCORD_BOT_TOKEN=your_discord_bot_token
   OPENROUTER_API_KEY=your_openrouter_api_key
   DEFAULT_INTERVAL=60
   ```

### Docker Installation
1. Build and run using Docker Compose:
   ```bash
   docker compose up --build
   ```

## Setup 🔧

1. Create a Discord bot using the [Discord Developer Portal](https://discord.com/developers/applications)
   - Enable "Message Content Intent" in the bot settings
   - Generate a bot token
   - Add the bot to your server with necessary permissions

2. Get an OpenRouter API key from [OpenRouter](https://openrouter.ai/)
   - Sign up for an account
   - Generate an API key
   - Add the key to your .env file

3. Configure environment variables in `.env`:
   ```
   DISCORD_BOT_TOKEN=your_discord_bot_token
   OPENROUTER_API_KEY=your_openrouter_api_key
   DEFAULT_INTERVAL=60
   ```

### Time Interval Configuration ⏰

The `DEFAULT_INTERVAL` setting in your `.env` file determines the timeframe for price analysis. Valid intervals are:

- Minutes: '1', '3', '5', '15', '30', '60', '120', '240', '360', '720'
- Daily: 'D' (1440 minutes)
- Weekly: 'W' (10080 minutes)
- Monthly: 'M' (43200 minutes)

Choose an interval that matches your trading strategy. For example:
- Short-term trading: Use shorter intervals (1-15 minutes)
- Swing trading: Use medium intervals (60-240 minutes)
- Long-term analysis: Use longer intervals (D/W/M)

## Commands 💬

- `!listen <strategies>` - Start monitoring for trading signals
  - Available strategies: `rsi`, `macd`, `bollinger`, `ichimoku`
  - Use comma-separated values for multiple strategies: `!listen rsi,macd,bollinger`
  - Use `all` to enable all strategies: `!listen all`
  - Examples:
    ```
    !listen rsi                         # Single strategy
    !listen rsi,macd,bollinger         # Multiple strategies
    !listen all                        # All available strategies
    ```

- `!unlisten <strategy>` - Stop monitoring a specific strategy
  - Use without strategy to stop all monitoring
  - Examples:
    ```
    !unlisten rsi      # Stop specific strategy
    !unlisten          # Stop all strategies
    ```

- `!interval <value>` - Change the analysis timeframe
  - Valid intervals:
    * Minutes: 1, 3, 5, 15, 30, 60, 120, 240, 360, 720
    * Special: D (daily), W (weekly), M (monthly)
  - Examples:
    ```
    !interval 240  # Switch to 4-hour candles
    !interval 60   # Switch to 1-hour candles
    !interval D    # Switch to daily candles
    ```

- `!chat <question>` - Ask the bot about crypto trading or its features
  - Multilingual support
  - Get concise answers about:
    * Cryptocurrency markets and trading
    * Bot features and strategies
    * Technical analysis concepts
  - Examples:
    ```
    !chat How does the RSI strategy work?
    !chat What is a Bollinger Band squeeze?
    !chat Explain the Ichimoku cloud settings
    ```

- `!top winners` - Display top 5 performing coins in the last 24 hours

- `!top losers` - Display worst 5 performing coins in the last 24 hours

- `!clear <count>` - Clear specified number of messages from the channel
  - Example: `!clear 100`

## Signal Output Format 📊

The bot provides detailed, actionable trading signals:

```
🎯 High-Confidence Trading Signals

📈 BUY Signals
**BTCUSDT** (0.85)
Price: 43250
RSI 28 | MACD Div 1.20% | BB 2.50%

📉 SELL Signals
**ETHUSDT** (0.92)
Price: 2250
RSI 75 | Cloud 2.10% | BB 1.80%
```

## AI Integration 🤖

The bot uses two specialized AI models:

### Chat Assistance (google/gemini-flash-1.5-8b)
- High throughput (191 tokens/sec)
- 1M context window
- Multilingual support
- Cost: $0.15/1M tokens
- Used for: User interactions and queries

## Technical Architecture 🏗️

### Core Components

- **Main Bot (`main.py`)**: Handles Discord interactions and command processing
- **Command Handler (`command_handler.py`)**: Manages command parsing and execution
- **Price Handler (`price_handler.py`)**: Manages real-time price data and signal generation
- **Strategy Factory (`factory.py`)**: Creates and manages trading strategy instances
- **Base Strategy (`base.py`)**: Provides common interface and functionality for all strategies
- **WebSocket Client (`bybit_ws.py`)**: Maintains real-time connection with Bybit exchange
- **OpenRouter Client (`openrouter_client.py`)**: Handles AI chat functionality

### Strategy System

The bot uses a factory pattern for strategy management:
1. **Base Strategy**: Abstract class defining common interface
   - Market trend analysis
   - Pattern recognition
   - Volume analysis
   - Dynamic threshold calculation

2. **Strategy Factory**: Central point for strategy creation
   - Manages strategy registration
   - Creates strategy instances
   - Handles strategy configuration

3. **Concrete Strategies**: Implement specific analysis methods
   - RSI with dynamic thresholds
   - MACD with enhanced crossover detection
   - Bollinger Bands with squeeze detection
   - Ichimoku Cloud with crypto-optimized settings

### Signal Generation Process

1. Price data is collected in real-time for all USDT perpetual pairs
2. Each strategy maintains its own DataFrame with required indicators
3. When new data arrives:
   - DataFrames are updated with the latest prices
   - Technical indicators are recalculated
   - Market conditions are analyzed:
     * Trend strength
     * Volume confirmation
     * Pattern recognition
     * Dynamic thresholds
   - Signals are generated with confidence scores
   - High-confidence signals are sent to Discord channel

## AI Chat System 🤖

The bot uses OpenRouter's API to provide intelligent responses about:
- Cryptocurrency markets and trading concepts
- Bot features and strategy explanations
- Technical analysis insights

Chat features:
- Focused on crypto/trading topics
- Concise, technical responses
- No financial advice or predictions
- Automatic disclaimers for market-related info
- Response length limited to maintain channel readability

## Contributing 🤝

Contributions are welcome! The bot is designed to be easily extensible, especially for adding new trading strategies.

To add a new strategy:
1. Create a new strategy class extending `SignalStrategy`
2. Implement required methods:
   - `min_candles` property
   - `calculate_indicator` method
   - `analyze_market` method
3. Add strategy type to `StrategyType` enum
4. Register strategy in `StrategyFactory`

## Troubleshooting 🔍

Common issues and solutions:

- **WebSocket Connection Issues**: Check your internet connection and Bybit API status
- **Missing Price Data**: Ensure minimum candle requirements are met for your chosen strategy
- **Discord Permission Errors**: Verify bot has proper channel permissions
- **Invalid Interval**: Make sure DEFAULT_INTERVAL in .env is one of the valid values
- **Strategy Errors**: Check log files for specific error messages

## Performance Considerations 🚀

- Efficient in-memory data structures for price data management
- Strategy-specific window sizes to optimize memory usage
- Factory pattern for efficient strategy instantiation
- WebSocket connection for real-time updates
- Batched signal processing for reduced Discord API calls

## License 📄

This project is open source and available under the MIT License.

## Disclaimer ⚠️

This bot is for educational purposes only. Always do your own research and never trade based solely on automated signals. Cryptocurrency trading involves substantial risk of loss.
