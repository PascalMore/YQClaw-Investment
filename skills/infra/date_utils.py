# skills/infra/date_utils.py
"""Date utility functions."""

from datetime import date, datetime, timedelta
from typing import List, Optional

try:
    import exchange_calendars as xcals
except ImportError:  # pragma: no cover - fallback path for minimal envs
    xcals = None


# Chinese stock trading days (2026) - basic implementation
# In production, this should be loaded from a config or external calendar
TRADING_DAYS_2026 = set([
    # January 2026
    '2026-01-02', '2026-01-05', '2026-01-06', '2026-01-07', '2026-01-08',
    '2026-01-09', '2026-01-12', '2026-01-13', '2026-01-14', '2026-01-15',
    '2026-01-16', '2026-01-19', '2026-01-20', '2026-01-21', '2026-01-22',
    '2026-01-23', '2026-01-26', '2026-01-27', '2026-01-28', '2026-01-29', '2026-01-30',
    # February 2026
    '2026-02-02', '2026-02-03', '2026-02-04', '2026-02-05', '2026-02-06',
    '2026-02-09', '2026-02-10', '2026-02-11', '2026-02-12', '2026-02-13',
    '2026-02-16', '2026-02-17', '2026-02-18', '2026-02-19', '2026-02-20',
    '2026-02-23', '2026-02-24', '2026-02-25', '2026-02-26', '2026-02-27',
    # March 2026
    '2026-03-02', '2026-03-03', '2026-03-04', '2026-03-05', '2026-03-06',
    '2026-03-09', '2026-03-10', '2026-03-11', '2026-03-12', '2026-03-13',
    '2026-03-16', '2026-03-17', '2026-03-18', '2026-03-19', '2026-03-20',
    '2026-03-23', '2026-03-24', '2026-03-25', '2026-03-26', '2026-03-27', '2026-03-30', '2026-03-31',
    # April 2026
    '2026-04-01', '2026-04-02', '2026-04-03', '2026-04-07', '2026-04-08',
    '2026-04-09', '2026-04-10', '2026-04-13', '2026-04-14', '2026-04-15',
    '2026-04-16', '2026-04-17', '2026-04-20', '2026-04-21', '2026-04-22',
    '2026-04-23', '2026-04-24', '2026-04-27', '2026-04-28', '2026-04-29', '2026-04-30',
    # May 2026
    '2026-05-04', '2026-05-05', '2026-05-06', '2026-05-07', '2026-05-08',
    '2026-05-11', '2026-05-12', '2026-05-13', '2026-05-14', '2026-05-15',
    '2026-05-18', '2026-05-19', '2026-05-20', '2026-05-21', '2026-05-22',
    '2026-05-25', '2026-05-26', '2026-05-27', '2026-05-28', '2026-05-29',
    # June 2026 (2026-06-19 Dragon Boat Festival market holiday)
    '2026-06-01', '2026-06-02', '2026-06-03', '2026-06-04', '2026-06-05',
    '2026-06-08', '2026-06-09', '2026-06-10', '2026-06-11', '2026-06-12',
    '2026-06-15', '2026-06-16', '2026-06-17', '2026-06-18',
    '2026-06-22', '2026-06-23', '2026-06-24', '2026-06-25', '2026-06-26',
    '2026-06-29', '2026-06-30',
])

_CN_CALENDAR = None


def _get_cn_calendar():
    """Return the A-share exchange calendar when exchange_calendars is available."""
    global _CN_CALENDAR
    if xcals is None:
        return None
    if _CN_CALENDAR is None:
        _CN_CALENDAR = xcals.get_calendar('XSHG')
    return _CN_CALENDAR


def _calendar_is_trading_day(d: str) -> Optional[bool]:
    """Check XSHG calendar, returning None when the dynamic calendar cannot answer."""
    calendar = _get_cn_calendar()
    if calendar is None:
        return None
    try:
        return bool(calendar.is_session(d))
    except Exception:
        return None


def is_trading_day(d: str) -> bool:
    """Check if a date is a trading day.
    
    Args:
        d: Date string in YYYY-MM-DD format
    
    Returns:
        bool: True if trading day, False otherwise
    """
    calendar_result = _calendar_is_trading_day(d)
    if calendar_result is not None:
        return calendar_result
    return d in TRADING_DAYS_2026


def get_latest_trading_day(d: str) -> str:
    """Get the latest trading day on or before the given date.
    
    Args:
        d: Date string in YYYY-MM-DD format
    
    Returns:
        str: Latest trading day (YYYY-MM-DD)
    """
    if is_trading_day(d):
        return d
    
    # Search backwards
    dt = parse_date(d)
    for i in range(1, 10):
        check_date = dt - timedelta(days=i)
        check_str = format_date(check_date)
        if is_trading_day(check_str):
            return check_str
    
    return d  # fallback


def get_next_trading_day(d: str) -> str:
    """Get the next trading day after the given date.
    
    Args:
        d: Date string in YYYY-MM-DD format
    
    Returns:
        str: Next trading day (YYYY-MM-DD)
    """
    dt = parse_date(d)
    for i in range(1, 10):
        check_date = dt + timedelta(days=i)
        check_str = format_date(check_date)
        if is_trading_day(check_str):
            return check_str
    
    return d  # fallback


def get_trading_dates(start: str, end: str) -> List[str]:
    """Get list of trading days between start and end dates (inclusive).
    
    Args:
        start: Start date in YYYY-MM-DD format
        end: End date in YYYY-MM-DD format
    
    Returns:
        List[str]: List of trading days
    """
    start_dt = parse_date(start)
    end_dt = parse_date(end)

    calendar = _get_cn_calendar()
    if calendar is not None:
        try:
            sessions = calendar.sessions_in_range(start_dt, end_dt)
            return [format_date(session.date()) for session in sessions]
        except Exception:
            pass
    
    dates = []
    current = start_dt
    while current <= end_dt:
        current_str = format_date(current)
        if is_trading_day(current_str):
            dates.append(current_str)
        current += timedelta(days=1)
    
    return dates


def parse_date(d: str) -> date:
    """Parse date string to date object.
    
    Args:
        d: Date string (supports YYYY-MM-DD, YYYYMMDD, etc.)
    
    Returns:
        date: Parsed date object
    """
    # Handle YYYYMMDD format
    d = d.replace('-', '')
    return datetime.strptime(d, '%Y%m%d').date()


def format_date(d: date, fmt: str = '%Y-%m-%d') -> str:
    """Format date object to string.
    
    Args:
        d: Date object
        fmt: Format string, default '%Y-%m-%d'
    
    Returns:
        str: Formatted date string
    """
    return d.strftime(fmt)
