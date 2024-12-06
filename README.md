# GrindhouseBot 🤖

A powerful Discord bot for cryptocurrency trading signals and real-time market monitoring using the Bybit exchange. The bot provides automated technical analysis signals and market insights directly in your Discord channel.

## Features 🌟

- Real-time trading signals using multiple technical analysis strategies
- Live monitoring of USDT perpetual contracts
- Market performance tracking with top gainers and losers
- Efficient in-memory price data management
- Docker support for easy deployment
- Extensible strategy system for custom indicators
- Configurable time intervals for analysis

## Trading Strategies 📈

### RSI Strategy
- Monitors Relative Strength Index (RSI) for overbought/oversold conditions
- Customizable buy/sell thresholds (default: buy at RSI < 30, sell at RSI > 70)
- Uses 14-period RSI calculation
- Requires minimum 15 candles for signal generation

### MACD Strategy
- Tracks Moving Average Convergence Divergence (MACD) crossovers
- Uses standard settings (12/26/9)
- Generates signals on histogram crossovers
- Requires minimum 27 candles for signal generation

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
   ```
4. Create a `.env` file with your credentials:
   ```
   DISCORD_BOT_TOKEN=your_discord_bot_token
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

2. Configure environment variables in `.env`:
   ```
   DISCORD_BOT_TOKEN=your_discord_bot_token
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

- `!listen <strategy>` - Start monitoring for trading signals
  - Available strategies: `rsi`, `macd`
  - Example: `!listen rsi`

- `!unlisten <strategy>` - Stop monitoring a specific strategy
  - Use without strategy to stop all monitoring
  - Example: `!unlisten macd`

- `!top winners` - Display top 5 performing coins in the last 24 hours

- `!top losers` - Display worst 5 performing coins in the last 24 hours

- `!clear <count>` - Clear specified number of messages from the channel
  - Example: `!clear 100`

## Technical Architecture 🏗️

### Core Components

- **Main Bot (`main.py`)**: Handles Discord interactions and command processing
- **Price Handler (`price_handler.py`)**: Manages real-time price data and signal generation
- **Strategies (`strategies.py`)**: Implements trading strategies using technical indicators
- **WebSocket Client (`bybit_ws.py`)**: Maintains real-time connection with Bybit exchange

### Data Flow

1. Bot receives commands via Discord
2. WebSocket connection streams real-time price data
3. Price Handler processes incoming data and maintains price history
4. Strategy classes analyze price data and generate signals
5. Signals are sent back to Discord channel

### Signal Generation Process

1. Price data is collected in real-time for all USDT perpetual pairs
2. Each strategy maintains its own DataFrame with required indicators
3. When new data arrives:
   - DataFrames are updated with the latest prices
   - Technical indicators are recalculated
   - Signals are generated based on strategy conditions
   - New signals are sent to Discord channel

## Contributing 🤝

Contributions are welcome! The bot is designed to be easily extensible, especially for adding new trading strategies.

To add a new strategy:
1. Extend the `SignalStrategy` base class in `strategies.py`
2. Implement the required `min_candles` property and `process` method
3. Add the strategy type to `StrategyType` enum in `models.py`

## Troubleshooting 🔍

Common issues and solutions:

- **WebSocket Connection Issues**: Check your internet connection and Bybit API status
- **Missing Price Data**: Ensure minimum candle requirements are met for your chosen strategy
- **Discord Permission Errors**: Verify bot has proper channel permissions
- **Invalid Interval**: Make sure DEFAULT_INTERVAL in .env is one of the valid values

## Performance Considerations 🚀

- The bot uses efficient in-memory data structures to manage price data
- Historical data is limited by the window size specified in strategies
- Each symbol maintains its own DataFrame to optimize memory usage
- WebSocket connection ensures real-time updates with minimal latency

## License 📄

This project is open source and available under the MIT License.

## Disclaimer ⚠️

This bot is for educational purposes only. Always do your own research and never trade based solely on automated signals. Cryptocurrency trading involves substantial risk of loss.
