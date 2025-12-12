"""
Configuration for PSAR Backtesting System
"""

import os
from pathlib import Path
from datetime import datetime, time
import pytz

# Project root
PROJECT_ROOT = Path(__file__).parent.resolve()

# Scanner location (sibling directory)
SCANNER_DIR = Path(os.environ.get(
    'SCANNER_DIR', 
    PROJECT_ROOT.parent / 'market-psar-scanner'
))

# Data storage
DATA_DIR = PROJECT_ROOT / 'data'
RUNS_DIR = DATA_DIR / 'runs'
SIGNATURES_FILE = DATA_DIR / 'signatures.json'

# Ensure directories exist
DATA_DIR.mkdir(parents=True, exist_ok=True)
RUNS_DIR.mkdir(parents=True, exist_ok=True)

# Market hours (US Eastern)
MARKET_TZ = pytz.timezone('US/Eastern')
MARKET_OPEN = time(9, 30)
MARKET_CLOSE = time(16, 0)


def get_market_status() -> dict:
    """
    Determine current market status and appropriate price type.
    
    Returns:
        dict with:
            - is_open: bool
            - price_type: 'open', 'close', 'previous_close'
            - reference_date: date to use for prices
    """
    now_et = datetime.now(MARKET_TZ)
    current_time = now_et.time()
    current_date = now_et.date()
    
    # Check if weekend
    if now_et.weekday() >= 5:  # Saturday = 5, Sunday = 6
        return {
            'is_open': False,
            'price_type': 'previous_close',
            'reference_date': current_date,
            'description': 'Weekend - using Friday close'
        }
    
    # Before market open
    if current_time < MARKET_OPEN:
        return {
            'is_open': False,
            'price_type': 'previous_close',
            'reference_date': current_date,
            'description': 'Pre-market - using previous close'
        }
    
    # After market close
    if current_time >= MARKET_CLOSE:
        return {
            'is_open': False,
            'price_type': 'close',
            'reference_date': current_date,
            'description': 'After hours - using today close'
        }
    
    # Market is open (intraday)
    return {
        'is_open': True,
        'price_type': 'open',
        'reference_date': current_date,
        'description': 'Market open - using today open'
    }
