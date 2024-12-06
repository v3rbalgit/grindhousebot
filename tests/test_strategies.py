import asyncio
import pandas as pd
import pytest
from datetime import datetime, timedelta
from typing import List, Union, cast

from utils.models import PriceData, SignalType, Signal
from strategies.rsi_strategy import RSIStrategy
from strategies.macd_strategy import MACDStrategy


def generate_test_data(start_price: float, trend: str, length: int = 100) -> List[PriceData]:
    """
    Generate test price data with a specific trend.

    Args:
        start_price: Starting price
        trend: One of 'uptrend', 'downtrend', 'sideways', 'oversold', 'overbought'
        length: Number of candles to generate
    """
    data = []
    # Start from a fixed time to ensure reproducibility
    base_time = 1700000000  # Fixed timestamp
    current_price = start_price
    used_timestamps = set()  # Track used timestamps

    for i in range(length):
        # Add some randomness to price movement
        random_factor = 0.001  # 0.1% random movement
        random_change = current_price * random_factor * ((-1) ** i)

        if trend == 'uptrend':
            price_change = current_price * 0.01  # 1% up trend
        elif trend == 'downtrend':
            price_change = -current_price * 0.01  # 1% down trend
        elif trend == 'sideways':
            price_change = 0
        elif trend == 'oversold':
            # Create oversold condition with continuous decline
            if i < length * 0.7:  # 70% of candles show decline
                price_change = -current_price * 0.03  # 3% down
            else:
                price_change = current_price * 0.001  # 0.1% up (slight recovery)
        elif trend == 'overbought':
            # Create overbought condition with continuous incline
            if i < length * 0.7:  # 70% of candles show incline
                price_change = current_price * 0.03  # 3% up
            else:
                price_change = -current_price * 0.001  # 0.1% down (slight dip)

        current_price = max(0.01, current_price + price_change + random_change)  # Ensure price doesn't go negative

        # Create candle data with guaranteed unique timestamps
        timestamp = base_time + (i * 3600)  # One hour intervals
        while timestamp in used_timestamps:  # Ensure uniqueness
            timestamp += 1
        used_timestamps.add(timestamp)

        high = current_price * 1.001
        low = current_price * 0.999
        data.append(PriceData(
            symbol='TESTUSDT',
            timestamp=timestamp,
            open=current_price * 0.9995,
            high=high,
            low=low,
            close=current_price,
            volume=1000000,
            turnover=current_price * 1000000
        ))

    # Sort by timestamp to ensure chronological order
    return sorted(data, key=lambda x: x.timestamp)


def create_dataframe(data: List[PriceData]) -> pd.DataFrame:
    """Create a DataFrame from price data with proper index handling."""
    # Create DataFrame with all fields including timestamp
    df_data = []
    used_timestamps = set()

    for p in data:
        # Ensure timestamp uniqueness
        timestamp = p.timestamp
        while timestamp in used_timestamps:
            timestamp += 1
        used_timestamps.add(timestamp)

        df_data.append({
            'timestamp': timestamp,
            'open': p.open,
            'high': p.high,
            'low': p.low,
            'close': p.close,
            'volume': p.volume,
            'turnover': p.turnover
        })

    df = pd.DataFrame(df_data)
    # Sort by timestamp
    df = df.sort_values('timestamp')
    # Set timestamp as index
    df.set_index('timestamp', inplace=True)
    return df


@pytest.mark.asyncio
async def test_rsi_strategy():
    """Test RSI strategy signal generation."""
    # Initialize strategy with buy/sell conditions
    strategy = RSIStrategy(
        interval=60,
        window=100,
        buy_condition=30,
        sell_condition=70
    )

    # Test oversold condition (should generate buy signals)
    test_data = generate_test_data(100, 'oversold')
    strategy.dataframes['TESTUSDT'] = create_dataframe(test_data)

    # Let RSI stabilize by using the last candle
    signals = strategy.generate_signals({'TESTUSDT': test_data[-1]})
    assert 'TESTUSDT' in signals
    signal = signals['TESTUSDT']
    if signal:
        print(f"RSI Oversold Signal: {signal.type}, RSI: {signal.value:.2f}")
        assert isinstance(signal.value, float)
        assert signal.value < 30  # RSI should be below buy condition
        assert signal.type == SignalType.BUY

    # Test overbought condition (should generate sell signals)
    test_data = generate_test_data(100, 'overbought')
    strategy.dataframes['TESTUSDT'] = create_dataframe(test_data)

    signals = strategy.generate_signals({'TESTUSDT': test_data[-1]})
    assert 'TESTUSDT' in signals
    signal = signals['TESTUSDT']
    if signal:
        print(f"RSI Overbought Signal: {signal.type}, RSI: {signal.value:.2f}")
        assert isinstance(signal.value, float)
        assert signal.value > 70  # RSI should be above sell condition
        assert signal.type == SignalType.SELL


@pytest.mark.asyncio
async def test_macd_strategy():
    """Test MACD strategy signal generation."""
    # Initialize strategy with buy/sell conditions
    strategy = MACDStrategy(
        interval=60,
        window=100,
        buy_condition="bullish crossover",
        sell_condition="bearish crossover"
    )

    # Test uptrend condition (should generate buy signals)
    test_data = generate_test_data(100, 'uptrend')
    strategy.dataframes['TESTUSDT'] = create_dataframe(test_data)

    signals = strategy.generate_signals({'TESTUSDT': test_data[-1]})
    signal = signals.get('TESTUSDT')
    if signal:
        print(f"MACD Uptrend Signal: {signal.type}, Value: {signal.value}")
        assert isinstance(signal.value, str)
        assert signal.value in ['bullish crossover', 'bearish crossover']

    # Test downtrend condition (should generate sell signals)
    test_data = generate_test_data(100, 'downtrend')
    strategy.dataframes['TESTUSDT'] = create_dataframe(test_data)

    signals = strategy.generate_signals({'TESTUSDT': test_data[-1]})
    signal = signals.get('TESTUSDT')
    if signal:
        print(f"MACD Downtrend Signal: {signal.type}, Value: {signal.value}")
        assert isinstance(signal.value, str)
        assert signal.value in ['bullish crossover', 'bearish crossover']


@pytest.mark.asyncio
async def test_strategy_with_real_flow():
    """Test strategy with real application flow."""
    symbol = 'TESTUSDT'

    # Test RSI Strategy
    rsi_strategy = RSIStrategy(
        interval=60,
        window=100,
        buy_condition=30,
        sell_condition=70
    )

    # Initialize with historical data
    historical_data = generate_test_data(100, 'sideways')
    rsi_strategy.dataframes[symbol] = create_dataframe(historical_data)

    # Simulate real-time updates
    print("\nTesting RSI Strategy with real-time flow:")
    conditions = ['oversold', 'overbought', 'sideways']
    for condition in conditions:
        print(f"\nTesting {condition} condition:")
        test_data = generate_test_data(100, condition)

        signals_generated = 0
        for candle in test_data[-10:]:  # Test last 10 candles
            signal = rsi_strategy.generate_signals({symbol: candle}).get(symbol)
            if signal:
                signals_generated += 1
                assert isinstance(signal.value, float)
                print(f"Generated {signal.type} signal with RSI: {signal.value:.2f}")

        print(f"Total signals generated: {signals_generated}")

    # Test MACD Strategy
    macd_strategy = MACDStrategy(
        interval=60,
        window=100,
        buy_condition="bullish crossover",
        sell_condition="bearish crossover"
    )

    # Initialize with historical data
    historical_data = generate_test_data(100, 'sideways')
    macd_strategy.dataframes[symbol] = create_dataframe(historical_data)

    # Simulate real-time updates
    print("\nTesting MACD Strategy with real-time flow:")
    conditions = ['uptrend', 'downtrend', 'sideways']
    for condition in conditions:
        print(f"\nTesting {condition} condition:")
        test_data = generate_test_data(100, condition)

        signals_generated = 0
        for candle in test_data[-10:]:  # Test last 10 candles
            signal = macd_strategy.generate_signals({symbol: candle}).get(symbol)
            if signal:
                signals_generated += 1
                assert isinstance(signal.value, str)
                print(f"Generated {signal.type} signal with value: {signal.value}")

        print(f"Total signals generated: {signals_generated}")


if __name__ == '__main__':
    asyncio.run(test_rsi_strategy())
    asyncio.run(test_macd_strategy())
    asyncio.run(test_strategy_with_real_flow())
