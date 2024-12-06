from typing import Set
from os import getenv

# Valid intervals for Bybit API
VALID_INTERVALS: Set[str] = {'1', '3', '5', '15', '30', '60', '120', '240', '360', '720', 'D', 'M', 'W'}

# Interval conversions to minutes
INTERVAL_TO_MINUTES = {
    'D': 1440,    # 24 * 60
    'W': 10080,   # 7 * 24 * 60
    'M': 43200    # 30 * 24 * 60 (approximation)
}

def validate_interval(interval: str) -> str:
    """
    Validate and format interval string.

    Args:
        interval: Interval string (can be minutes or 'D'/'M'/'W')

    Returns:
        Formatted interval string

    Raises:
        ValueError: If interval is invalid
    """
    # If interval is already a valid format, return it
    if interval in VALID_INTERVALS:
        return interval

    try:
        # Convert minutes to valid interval
        minutes = int(interval)
        if str(minutes) in VALID_INTERVALS:
            return str(minutes)
        raise ValueError(f"Invalid interval: {interval}")
    except ValueError:
        raise ValueError(f"Invalid interval: {interval}")


def interval_to_minutes(interval: str) -> int:
    """
    Convert interval string to minutes.

    Args:
        interval: Interval string (can be minutes or 'D'/'M'/'W')

    Returns:
        Number of minutes

    Raises:
        ValueError: If interval is invalid
    """
    # Validate interval first
    validated = validate_interval(interval)

    # Convert special intervals
    if validated in INTERVAL_TO_MINUTES:
        return INTERVAL_TO_MINUTES[validated]

    # For minute-based intervals
    return int(validated)


# Get and validate default interval from environment
try:
    DEFAULT_INTERVAL = validate_interval(getenv('DEFAULT_INTERVAL', '60'))
    DEFAULT_MINUTES = interval_to_minutes(DEFAULT_INTERVAL)
except ValueError as e:
    raise ValueError(f"Invalid DEFAULT_INTERVAL in environment: {e}")
