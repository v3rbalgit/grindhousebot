## What is GrindhouseBot?
Discord bot that displays live position changes on user's Bybit account and provides real-time price signals depending on chosen strategy.

## How to use GrindhouseBot?
1. Use [this guide](https://realpython.com/how-to-make-a-discord-bot-python/) to create a bot on your Discord account with necessary privileges
2. Create `.env` file in root directory with variables `api_key`, `secret_key` and `discord_bot_token` and corresponding values (found on your Bybit API management page and Discord developer portal)
3. Install the requirements (`pip install -r requirements.txt`)
4. Run the main file (`python3 main.py`)

## What commands does the bot understand?
The bot responds to the following commands:

- **!active** - displays currently open positions on connected Bybit account
- **!listen positions** - starts watching for real-time changes in USDT perpetual contract positions on Bybit
- **!listen signals** - starts watching for real-time buy/sell signals for symbols traded via the USDT perpetual contract
- **!unlisten positions** - stops watching for real-time position changes
- **!unlisten signals** - stops providing real-time buy/sell signals
- **!top winners** - displays daily top performing coins
- **!top losers** - displays daily worst performing coins
- **!clear** - clears the last 200 messages in Discord channel

## How does the bot come up with price signals?
After the bot has been started, the live websocket price data from Bybit is filtered and stored in-memory in a *pandas dataframe*. When it fills up with sufficient data to calculate the RSI values, it will display the coins whose values are above or below certain thresholds. By providing arguments to the `RSIStrategy` constructor you can set what timeframes you want the RSI calculation to be based upon (`interval` - default 60 minutes), the number of intervals to store in-memory (`window` - default 20), the sell signal threshold (`sell` - default 85) and the buy signal threshold (`buy` - default 15). 

## Are there other strategies? Can the bot change strategies on the fly?
There is currently no way to swap strategies on the fly, and there is so far only one strategy - the `RSIStrategy` to provide signals. I have ideas about other strategies, but you are free to help out. I structured the code so it should be simple to get started, and the signals are generated using `pandas_ta` library, so it should be relatively simple to implement and most of the code is documented ;)

## I found a bug, can you help me?
As a self-thought programmer, I cannot guarantee that the code will work 100%. This is a hobby project. I tried my best, but bugs happen and I'm always learning. Raise an issue in this repository or even better, contribute to the code.
